# Databricks notebook source
# DBTITLE 1,Kabinet - Plan Matrix Prices: средняя цена SKU × маркетплейс × месяц
# Kabinet - Plan Matrix Prices (шаг 1, с 15.10.2026)
#
# Таблица «Plan Matrix for Marketplaces» (Google, ведёт аналитик) — план по SKU × маркетплейс × месяц: на вкладке
# маркетплейса (Amazon_ES … TikTok_ES) у каждого месяца три колонки — AVG Price, Units, Revenue. Units заполняет
# менеджер, Revenue = AVG Price × Units считает лист. Этот ноутбук считает AVG Price.
#
# Правило цены (решение владельца 13–14.10.2026, пример — вкладка «Пример Amazon_ES» той же таблицы):
#   1) были продажи за последние N дней (reorder_params.plan_price_sales_window_days, 90) на ЭТОМ маркетплейсе —
#      средневзвешенная фактическая цена: выручка / штуки по цене продажи после скидок продавца (промо и купоны
#      Amazon, скидка продавца ManoMano, скидки продавца TikTok); с НДС — как цены на витрине и в вкладках prices_*;
#   2) продаж нет, но SKU выставлен — средняя цена витрины за N дней (plan_price_listing_window_days, 30):
#      Amazon — снимки ScrapingDog (raw_amazon_listing_snapshots.display_price, ASIN → SKU через
#      product_entity_listings, листинг Active); Leroy Merlin, Carrefour, ManoMano — цена активного оффера из API
#      площадки (скрейпинга по ним нет; так же берёт цены и сама таблица на вкладках prices_*);
#   3) SKU сам не продаётся и не выставлен, но входит в набор, который на этом маркетплейсе продаётся или выставлен —
#      пусто, источник kit_only; всё остальное — пусто, источник none.
# Заморозка (plan_price_freeze_day, 15): цена месяца M обновляется каждый день до 15-го числа месяца M−1 включительно
# и с 16-го фиксируется — ценой расчёта «на 15-е». Дальние месяцы получают ту же текущую цену и обновляются до своего
# 15-го. Расчёт «на дату» воспроизводим: продажи и снимки витрины берутся по эту дату. Не воспроизводим только
# оффер Mirakl — истории офферов нет, поэтому у месяца, замороженного задним числом, цена оффера текущая и это
# написано в note.
#
# Где лежит:
#   kabinet_data.plan_price_daily — история: расчёт «на дату» по каждой паре, строка на день (что было известно);
#   kabinet_data.plan_price_month — цена месяца, frozen = зафиксирована; замороженную строку прогон не меняет.
# Запись в Google-таблицу (ячейка 2) — ТОЛЬКО в свою вкладку avg_price и только при
# reorder_params.plan_price_sheet_write = 1 (по умолчанию 0: в таблицу ничего не пишем до решения владельца).
# Вкладки аналитика не трогаем никогда.
#
# Параметры: dry_run=1 — ничего не пишет ни в базу, ни в таблицу, печатает покрытие; as_of=ГГГГ-ММ-ДД — «сегодня»
# для пробы.

# COMMAND ----------

# DBTITLE 1,1. Расчёт цен → plan_price_daily, plan_price_month
import json, re, calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import psycopg2, psycopg2.extras
import gspread
from google.oauth2.service_account import Credentials
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("dry_run", "0")
dbutils.widgets.text("as_of", "")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
TODAY = (date.fromisoformat(dbutils.widgets.get("as_of").strip()) if dbutils.widgets.get("as_of").strip()
         else datetime.now(ZoneInfo("Europe/Kyiv")).date())

SHEET_KEY = "1fA4Kla_IJ5LAlj07z69ya6TwE0MU7aYOa6fuTeOC0GM"   # Plan Matrix for Marketplaces
# вкладка таблицы → код маркетплейса в справочнике (marketplaces_new.code)
TABS = {"Amazon_ES": "AMZ-ES", "Amazon_IT": "AMZ-IT", "Amazon_FR": "AMZ-FR", "Amazon_DE": "AMZ-DE",
        "LM_ES": "LM-ES", "MM_ES": "MM-ES", "MM_FR": "MM-FR", "CF_ES": "CF-ES", "TikTok_ES": "TTS-ES"}
AMZ_CHANNEL = {"Amazon.es": "AMZ-ES", "Amazon.it": "AMZ-IT", "Amazon.fr": "AMZ-FR", "Amazon.de": "AMZ-DE"}

_wc = WorkspaceClient()
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                      dbname="databricks_postgres", user=_wc.current_user.me().user_name, sslmode="require",
                      password=_wc.postgres.generate_database_credential(
                          endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
cur = pg.cursor()

def q(sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()

cur.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'plan_price_%'")
P = {k: float(v) for k, v in cur.fetchall()}
SALES_DAYS = int(P.get("plan_price_sales_window_days", 90))
LIST_DAYS = int(P.get("plan_price_listing_window_days", 30))
MIN_UNITS = int(P.get("plan_price_min_units", 1))
FREEZE_DAY = int(P.get("plan_price_freeze_day", 15))
print(f"сегодня {TODAY}; окно продаж {SALES_DAYS} дн, витрины {LIST_DAYS} дн, минимум {MIN_UNITS} шт, "
      f"заморозка после {FREEZE_DAY}-го" + ("; DRY RUN — без записи" if DRY else ""))

def norm(s):
    """Ключ SKU: хвосты -FBA/-FBM и «_»/«-» в конце снимаются, потерянный ведущий ноль возвращается.
    Вариант (-A, -B, -1) и префикс набора (S2_) остаются: это другие товары, не базовый код."""
    s = re.sub(r"\s+", " ", str(s or "").strip())
    s = re.sub(r"(?i)-FB[AM]\b.*$", "", s)
    s = re.sub(r"[-_]+$", "", s)
    return re.sub(r"^(\d{7})(?!\d)", r"0\1", s)

# ── Таблица: SKU и месяцы (только чтение) ──
_info = json.loads(dbutils.secrets.get("kabinet-external", "google-sa-json"), strict=False)
_gc = gspread.authorize(Credentials.from_service_account_info(
    _info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]))
_sh = _gc.open_by_key(SHEET_KEY)
SHEET_SKUS, MONTHS, skipped_cells = {}, None, []
for _tab in TABS:
    _vals = _sh.worksheet(_tab).get_all_values()
    _hdr = next(i for i, r in enumerate(_vals[:6]) if len(r) > 1 and r[1].strip().upper() == "SKU")
    _m = [datetime.strptime(c.strip(), "%B %Y").date() for c in _vals[_hdr - 1] if c.strip()]
    MONTHS = sorted(set(MONTHS or []) | set(_m))
    _skus = []
    for r in _vals[_hdr + 1:]:
        c = r[1].strip() if len(r) > 1 else ""
        if not c:
            continue
        if not re.match(r"^(S\d*_)?\d{7,8}", c):      # в колонке SKU бывает название вместо кода
            skipped_cells.append((_tab, c)); continue
        _skus.append(norm(c))
    SHEET_SKUS[_tab] = sorted(set(_skus))
ALL_SKUS = sorted({s for v in SHEET_SKUS.values() for s in v})
print(f"таблица: {len(ALL_SKUS)} SKU, месяцы {MONTHS[0]:%m.%Y}–{MONTHS[-1]:%m.%Y}; не код в колонке SKU: "
      f"{len({c for _, c in skipped_cells})} ({', '.join(sorted({c for _, c in skipped_cells})[:4])})")

def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)

def freeze_date(month):                 # месяц M фиксируется ценой расчёта на FREEZE_DAY-е число месяца M−1
    prev = add_months(month, -1)
    return date(prev.year, prev.month, min(FREEZE_DAY, calendar.monthrange(prev.year, prev.month)[1]))

# Какие даты расчёта нужны: сегодня и «на 15-е» для месяцев, которые пора заморозить, а замороженной строки ещё нет
frozen_have = set() if DRY else {(r[0], r[1], r[2]) for r in q(
    "SELECT marketplace, sku, month FROM kabinet_data.plan_price_month WHERE frozen")}
due = [m for m in MONTHS if TODAY > freeze_date(m)]
need_freeze = [m for m in due if any((TABS[t], s, m) not in frozen_have for t in TABS for s in SHEET_SKUS[t])]
have_daily = set() if DRY else {r[0] for r in q(
    "SELECT DISTINCT calc_date FROM kabinet_data.plan_price_daily WHERE calc_date = ANY(%s)",
    ([freeze_date(m) for m in need_freeze],))}
AS_OF = sorted({TODAY} | {freeze_date(m) for m in need_freeze if freeze_date(m) not in have_daily})
EARLIEST = min(AS_OF) - timedelta(days=max(SALES_DAYS, LIST_DAYS) + 1)
print(f"к заморозке: {[f'{m:%m.%Y}' for m in need_freeze]}; считаю на даты {[str(d) for d in AS_OF]}")

# ── Справочник листингов: seller SKU → SKU, активные листинги ──
listing_sku = {}                                 # (маркетплейс, seller_sku) → sku
asin_skus = defaultdict(set)                     # (маркетплейс, ASIN) → активные SKU
listed = set()                                   # (маркетплейс, sku) — SKU выставлен
for code, seller_sku, sku, peid, st in q("""
        SELECT m.code, l.seller_sku, l.sku, l.peid, l.listing_status
        FROM kabinet_data.product_entity_listings l JOIN kabinet_data.marketplaces_new m ON m.id = l.marketplace_id"""):
    k = norm(sku)
    listing_sku[(code, seller_sku)] = k
    if code.startswith("AMZ-") and (st or "") == "Active":
        asin_skus[(code, peid)].add(k)
        listed.add((code, k))

# ── Продажи: (маркетплейс, sku, дата) → [выручка с НДС после скидок продавца, штуки] ──
sales = []                                       # (code, sku, day, revenue, units)
# Amazon: позиции заказов (цена строки − промо-скидка, с НДС); отменённые и без цены (Pending) — не продажа.
# Не продажа и заказы программы Vine (промо vine.enrollment… списывает всю цену: единица бесплатно рецензенту — у
# 84279000 ES шесть таких строк из семи давали «среднюю цену» 8,99 € при цене 62,95 €), и заказы-замены (без цены).
_amz = spark.sql(f"""
    WITH o AS (
        SELECT amazon_order_id, sales_channel, order_status, coalesce(is_replacement_order, false) AS repl,
               to_date(from_utc_timestamp(purchase_date, 'Europe/Madrid')) AS d,
               row_number() OVER (PARTITION BY amazon_order_id ORDER BY last_update_date DESC) AS rn
        FROM dnipro_m.dnipro_m.raw_amazon_seller_central_get_orders
        WHERE purchase_date >= DATE'{EARLIEST}'),
    i AS (
        SELECT amazon_order_id, seller_sku, quantity_ordered AS qty, item_price_amount AS price,
               coalesce(promotion_discount_amount, 0) AS promo, coalesce(promotion_ids, '') AS promo_ids,
               row_number() OVER (PARTITION BY order_item_id ORDER BY _loaded_at DESC) AS rn
        FROM dnipro_m.dnipro_m.raw_amazon_seller_central_get_order_items)
    SELECT o.sales_channel, o.d, i.seller_sku, i.qty, i.price, i.promo
    FROM o JOIN i ON i.amazon_order_id = o.amazon_order_id AND i.rn = 1
    WHERE o.rn = 1 AND o.order_status <> 'Canceled' AND NOT o.repl AND i.price IS NOT NULL AND i.qty > 0
      AND lower(i.promo_ids) NOT LIKE '%vine.%' AND i.price - i.promo > 0""").collect()
for r in _amz:
    code = AMZ_CHANNEL.get(r.sales_channel)
    if code:
        sales.append((code, listing_sku.get((code, r.seller_sku)) or norm(r.seller_sku), r.d,
                      float(r.price) - float(r.promo), int(r.qty)))
# Leroy Merlin: строка заказа уже со скидкой; возвраты и ещё не принятые — не продажа (как у витрины Power BI)
for sku, d, price, qty in q("""
        SELECT l.shop_sku, o.created_date::date, l.price, l.quantity
        FROM kabinet_data.raw_lm_order_lines l JOIN kabinet_data.raw_lm_orders o USING (order_id)
        WHERE o.created_date::date >= %s AND l.quantity > 0
          AND l.order_line_state NOT IN ('REFUNDED', 'CANCELED', 'REFUSED', 'WAITING_ACCEPTANCE')""", (EARLIEST,)):
    sales.append(("LM-ES", listing_sku.get(("LM-ES", sku)) or norm(sku), d, float(price or 0), int(qty)))
# ManoMano: скидка продавца лежит на заказе — раскладываем на строки пропорционально их сумме;
# скидку, которую оплачивает сама площадка (manomano_discount), не вычитаем: цена продажи у нас от неё не меняется
for country, sku, d, total, qty, base, disc in q("""
        SELECT l.country, l.sku, l.order_date, l.total_price, l.quantity,
               sum(l.total_price) OVER (PARTITION BY l.order_ref, l.country) AS base,
               coalesce(o.seller_discount, 0) AS disc
        FROM kabinet_data.raw_mm_order_lines l
        LEFT JOIN kabinet_data.raw_mm_orders o ON o.order_ref = l.order_ref AND o.country = l.country
        WHERE l.order_date >= %s AND l.country IN ('ES', 'FR') AND l.quantity > 0
          AND upper(coalesce(l.order_status, '')) NOT IN ('CANCELED', 'REFUSED', 'REFUNDED', 'REFUNDING')""",
        (EARLIEST,)):
    code = "MM-" + country
    rev = float(total or 0) - (float(disc) * float(total or 0) / float(base) if base else 0.0)
    sales.append((code, listing_sku.get((code, sku)) or norm(sku), d, rev, int(qty)))
# Carrefour: цена строки уже с действующим промо
for sku, d, total, qty in q("""
        SELECT sku, order_date, total_price, quantity FROM kabinet_data.raw_cf_order_lines
        WHERE order_date >= %s AND quantity > 0
          AND upper(coalesce(order_status, '')) NOT IN ('CANCELED', 'REFUSED', 'WAITING_ACCEPTANCE')""", (EARLIEST,)):
    sales.append(("CF-ES", listing_sku.get(("CF-ES", sku)) or norm(sku), d, float(total or 0), int(qty)))
# TikTok Shop: расчёты площадки, цена до скидок минус скидка продавца
for r in spark.sql(f"""
        SELECT seller_sku, order_created_date AS d, sum(subtotal_before_discounts - coalesce(seller_discounts, 0)) AS rev,
               sum(quantity) AS qty
        FROM dnipro_m.dnipro_m.raw_tiktok_order_details
        WHERE lower(type) = 'order' AND country = 'ES' AND order_created_date >= DATE'{EARLIEST}'
        GROUP BY 1, 2 HAVING sum(quantity) > 0""").collect():
    sales.append(("TTS-ES", norm(r.seller_sku), r.d, float(r.rev or 0), int(r.qty)))

# ── Витрина Amazon: снимки ScrapingDog по дням ──
scrape = []                                      # (code, sku, day, price)
for r in spark.sql(f"""
        SELECT marketplace, asin, to_date(from_utc_timestamp(fetched_at, 'Europe/Madrid')) AS d, display_price
        FROM dnipro_m.dnipro_m.raw_amazon_listing_snapshots
        WHERE ok AND display_price > 0 AND fetched_at >= DATE'{EARLIEST}'
          AND marketplace IN ('es', 'it', 'fr', 'de')""").collect():
    code = "AMZ-" + r.marketplace.upper()
    for s in asin_skus.get((code, r.asin), ()):
        scrape.append((code, s, r.d, float(r.display_price)))

# ── Офферы Mirakl: текущая цена активного оффера (истории офферов нет) ──
offers = defaultdict(list)                       # (code, sku) → цены
for sku, price in q("SELECT shop_sku, price FROM kabinet_data.raw_lm_offers WHERE active AND price > 0"):
    offers[("LM-ES", norm(sku))].append(float(price))
for sku, price, disc, d_from, d_to in q("""
        SELECT shop_sku, price, discount_price, discount_start, discount_end FROM kabinet_data.raw_cf_offers
        WHERE active AND price > 0"""):
    # у Carrefour промо лежит в discount_price и действует только внутри своего окна
    live = disc and (d_from is None or d_from.date() <= TODAY) and (d_to is None or d_to.date() >= TODAY)
    offers[("CF-ES", norm(sku))].append(float(disc if live else price))
for sku, mk, price in q("""
        SELECT sku, marketplace_code, price FROM kabinet_data.raw_mm_offers
        WHERE offer_is_online AND price > 0 AND marketplace_code IN ('MM-ES', 'MM-FR')
          AND snapshot_date = (SELECT max(snapshot_date) FROM kabinet_data.raw_mm_offers)"""):
    offers[(mk, norm(sku))].append(float(price))

# ── Наборы: набор (composite) → базовые компоненты ──
kit_parts = defaultdict(set)
for comp, base in q("SELECT composite_sku, base_sku FROM kabinet_data.sku_composition"):
    kit_parts[norm(comp)].add(norm(base))

def compute(as_of):
    """Цена «на дату» по каждой паре вкладка × SKU листа: только данные по эту дату включительно."""
    s_from, l_from = as_of - timedelta(days=SALES_DAYS - 1), as_of - timedelta(days=LIST_DAYS - 1)
    agg = defaultdict(lambda: [0.0, 0])
    for code, s, d, rev, qty in sales:
        if s_from <= d <= as_of:
            agg[(code, s)][0] += rev; agg[(code, s)][1] += qty
    scr = defaultdict(list)
    for code, s, d, p in scrape:
        if l_from <= d <= as_of:
            scr[(code, s)].append(p)
    active = {k for k in agg if agg[k][1] > 0} | set(listed) | set(offers)
    in_kit = defaultdict(set)                    # (code, компонент) — набор с ним продаётся или выставлен
    for code, s in active:
        for b in kit_parts.get(s, ()):
            in_kit[(code, b)].add(s)
    backfill = as_of < TODAY
    out = {}
    for tab, code in TABS.items():
        for s in SHEET_SKUS[tab]:
            k = (code, s)
            rev, units = agg.get(k, (0.0, 0))
            if units >= MIN_UNITS and rev > 0:
                out[k] = (round(rev / units, 2), "sales", units, round(rev, 2), None, f"{s_from}…{as_of}")
            elif scr.get(k):
                out[k] = (round(sum(scr[k]) / len(scr[k]), 2), "scrape", units or None, None, len(scr[k]),
                          f"{l_from}…{as_of}")
            elif offers.get(k):
                out[k] = (round(sum(offers[k]) / len(offers[k]), 2), "offer", units or None, None, len(offers[k]),
                          "оффер на дату расчёта недоступен — взят текущий" if backfill else None)
            elif k in listed:
                out[k] = (None, "listed_no_price", None, None, None, f"снимков витрины за {l_from}…{as_of} нет")
            elif in_kit.get(k):
                out[k] = (None, "kit_only", None, None, None, "в наборах: " + ", ".join(sorted(in_kit[k])[:5]))
            else:
                out[k] = (None, "none", None, None, None, None)
    return out

calcs = {d: compute(d) for d in AS_OF}

# ── Покрытие по вкладкам (на сегодня) ──
_today = calcs[TODAY]
print("вкладка | SKU | из продаж | из витрины (скрейп / оффер) | выставлен без цены | только в наборах | пусто")
for tab, code in TABS.items():
    c = defaultdict(int)
    for s in SHEET_SKUS[tab]:
        c[_today[(code, s)][1]] += 1
    print(f"{tab} | {len(SHEET_SKUS[tab])} | {c['sales']} | {c['scrape'] + c['offer']} "
          f"({c['scrape']} / {c['offer']}) | {c['listed_no_price']} | {c['kit_only']} | {c['none']}")
for d in AS_OF:
    if d != TODAY:
        n = sum(1 for v in calcs[d].values() if v[0] is not None)
        print(f"на {d}: с ценой {n} пар (для заморозки)")

# ── Запись ──
if not DRY:
    daily_rows = [(d, code, s, *v) for d, res in calcs.items() for (code, s), v in res.items()]
    month_rows = []
    for m in MONTHS:
        fd = freeze_date(m)
        frozen = TODAY > fd
        src_date = fd if frozen else TODAY
        for (code, s) in _today:
            if frozen and (code, s, m) in frozen_have:
                continue
            month_rows.append((code, s, m, src_date, frozen))
    with pg:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.plan_price_daily
                (calc_date, marketplace, sku, price, source, units, revenue, n_obs, note, computed_at)
            VALUES %s
            ON CONFLICT (calc_date, marketplace, sku) DO UPDATE SET
                price = EXCLUDED.price, source = EXCLUDED.source, units = EXCLUDED.units, revenue = EXCLUDED.revenue,
                n_obs = EXCLUDED.n_obs, note = EXCLUDED.note, computed_at = now()""",
            daily_rows, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, now())", page_size=2000)
        # месяц берёт цену из дневного расчёта на свою дату: сегодня — для незамороженных, «на 15-е» — для замороженных.
        # Замороженную строку не перезаписывает никто: условие WHERE NOT frozen в самом UPSERT.
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.plan_price_month AS pm
                (marketplace, sku, month, price, source, calc_date, frozen, frozen_at, updated_at)
            SELECT v.marketplace, v.sku, v.month::date, d.price, d.source, v.calc_date::date, v.frozen,
                   CASE WHEN v.frozen THEN now() END, now()
            FROM (VALUES %s) AS v(marketplace, sku, month, calc_date, frozen)
            JOIN kabinet_data.plan_price_daily d
              ON d.calc_date = v.calc_date::date AND d.marketplace = v.marketplace AND d.sku = v.sku
            ON CONFLICT (marketplace, sku, month) DO UPDATE SET
                price = EXCLUDED.price, source = EXCLUDED.source, calc_date = EXCLUDED.calc_date,
                frozen = EXCLUDED.frozen, frozen_at = EXCLUDED.frozen_at, updated_at = now()
            WHERE NOT pm.frozen""",
            month_rows, template="(%s, %s, %s, %s, %s)", page_size=2000)
    print(f"✅ записано: дневных {len(daily_rows)}, помесячных {len(month_rows)} "
          f"(из них к заморозке {sum(1 for r in month_rows if r[4])})")
pg.close()

# COMMAND ----------

# DBTITLE 1,2. Вкладка avg_price в таблице (только при plan_price_sheet_write = 1)
# Пишем только в СВОЮ вкладку avg_price: строка на SKU × вкладка × месяц. Вкладки аналитика не трогаем — если цена
# нужна в AVG Price, лист подтягивает её формулой из avg_price (MAXIFS по SKU, вкладке и месяцу).
# Пустые пары (source = none: SKU на маркетплейсе не продаётся и не выставлен) не пишем — лист меньше в разы.
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg2
import gspread
from google.oauth2.service_account import Credentials
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("dry_run", "0")
_DRY = dbutils.widgets.get("dry_run").strip() == "1"
_SHEET_KEY = "1fA4Kla_IJ5LAlj07z69ya6TwE0MU7aYOa6fuTeOC0GM"
_TAB_OF = {"AMZ-ES": "Amazon_ES", "AMZ-IT": "Amazon_IT", "AMZ-FR": "Amazon_FR", "AMZ-DE": "Amazon_DE",
           "LM-ES": "LM_ES", "MM-ES": "MM_ES", "MM-FR": "MM_FR", "CF-ES": "CF_ES", "TTS-ES": "TikTok_ES"}
_SRC = {"sales": "sales", "scrape": "scrape", "offer": "offer", "listed_no_price": "listed, no price",
        "kit_only": "kits only"}

_wc2 = WorkspaceClient()
_pg2 = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                        dbname="databricks_postgres", user=_wc2.current_user.me().user_name, sslmode="require",
                        password=_wc2.postgres.generate_database_credential(
                            endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
_c2 = _pg2.cursor()
_c2.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'plan_price_sheet_write'")
_r = _c2.fetchone()
_WRITE = bool(_r and float(_r[0]) == 1)
if _DRY or not _WRITE:
    print("вкладка avg_price: пропуск — " + ("dry run" if _DRY else "plan_price_sheet_write = 0 (ждёт решения владельца)"))
else:
    _c2.execute("""
        SELECT sku, marketplace, month, price, source, calc_date, frozen FROM kabinet_data.plan_price_month
        WHERE source <> 'none' ORDER BY marketplace, sku, month""")
    _rows = _c2.fetchall()
    _now = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M")
    _out = [["sku", "tab", "month", "avg_price", "source", "price_date", "frozen", "month_start", "updated"]]
    for sku, mk, m, price, src, cd, fr in _rows:
        _out.append([sku, _TAB_OF.get(mk, mk), m.strftime("%B %Y"), float(price) if price is not None else "",
                     _SRC.get(src, src), cd.isoformat(), "yes" if fr else "no", m.isoformat(), _now])
    _info2 = json.loads(dbutils.secrets.get("kabinet-external", "google-sa-json"), strict=False)
    _gc2 = gspread.authorize(Credentials.from_service_account_info(
        _info2, scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    _sh2 = _gc2.open_by_key(_SHEET_KEY)
    try:
        _ws = _sh2.worksheet("avg_price")
    except gspread.WorksheetNotFound:
        _ws = _sh2.add_worksheet("avg_price", rows=len(_out) + 100, cols=len(_out[0]))
    if _ws.row_count < len(_out):
        _ws.add_rows(len(_out) - _ws.row_count + 100)
    _ws.batch_clear(["A:I"])                     # только своя вкладка
    # SKU — текстом (raw): иначе лист съест ведущий ноль у 08455000 и формула MAXIFS не найдёт строку
    _ws.update(_out, "A1", raw=True)
    print(f"✅ avg_price: {len(_out) - 1} строк")
_pg2.close()

# COMMAND ----------

# DBTITLE 1,3. Пульс
# Последней операцией, безусловно: «ячейки доработали до конца», а не «всё внутри было без замечаний»
import psycopg2
from databricks.sdk import WorkspaceClient
dbutils.widgets.text("dry_run", "0")
if dbutils.widgets.get("dry_run").strip() == "1":
    print("dry run — пульс не пишу")
else:
    _wc3 = WorkspaceClient()
    _pg3 = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_wc3.current_user.me().user_name, sslmode="require",
                            password=_wc3.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
    with _pg3, _pg3.cursor() as _c3:
        _c3.execute("""
            INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
            VALUES ('Kabinet - Plan Matrix Prices', now(), 'средняя цена Plan Matrix', 26)
            ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""")
    _pg3.close()
    print("💓 Kabinet - Plan Matrix Prices")
