# Databricks notebook source
# DBTITLE 1,Kabinet - Plan Matrix Prices: средняя цена SKU × маркетплейс × месяц
# Kabinet - Plan Matrix Prices (шаг 1, с 15.10.2026)
#
# Таблица «Plan Matrix for Marketplaces» (Google, ведёт аналитик) — план по SKU × маркетплейс × месяц: на вкладке
# маркетплейса (Amazon_ES … TikTok_ES) у каждого месяца три колонки — AVG Price, Units, Revenue. Units заполняет
# менеджер, Revenue = AVG Price × Units считает лист. Этот ноутбук считает AVG Price.
#
# Правило цены (решения владельца 13–14.10.2026, пример — вкладка «Пример Amazon_ES» той же таблицы):
#   1) продано не меньше plan_price_min_units (3) штук за последние plan_price_sales_window_days (90) дней на ЭТОМ
#      маркетплейсе — средневзвешенная фактическая цена: выручка / штуки по цене продажи после скидок продавца
#      (промо и купоны Amazon, скидка продавца ManoMano, скидки продавца TikTok); с НДС — как цены витрины.
#      Заказы Amazon Vine, заказы-замены и строки с ценой после промо ≤ 0 — не продажа;
#   2) продано меньше — цена листинга:
#      Amazon — а) наша действующая цена из SP-API Listings Items (ячейка 1 кладёт её снимком дня в сырьё
#                  dnipro_m.raw_amazon_listing_offers): меньшая из our_price и discounted_price (sale price), если
#                  sale price действует на дату расчёта; только покупаемые листинги (BUYABLE) и предложение для всех
#                  покупателей (audience ALL, не B2B). Отчёт листингов GET_MERCHANT_LISTINGS_ALL_DATA отдаёт только
#                  обычную цену, поэтому он — запас для дат, на которые снимка Listings Items нет (история до 15.10.2026).
#                  У SKU с двумя листингами (FBA и FBM) — меньшая цена: Buy Box держит её (22635000 DE: 54,98 и 69,98 €);
#               б) нет её — средняя цена витрины ScrapingDog за plan_price_listing_window_days (30) дней;
#               в) нет и её — средняя цена Buy Box (SP-API Product Pricing, kabinet_data.buybox_status) за то же окно.
#               Из ScrapingDog в а) и б) берём купон: если в последнем снимке ASIN за окно есть текст купона
#               («Aplicar cupón de 10 %», «… 5,00 €»), цена уменьшается на этот процент или сумму;
#      Leroy Merlin, Carrefour, ManoMano — цена активного оффера из API площадки (скрейпинга по ним нет);
#      цены листинга нет, а продажи были (1–2 шт) — цена продаж, а не пусто;
#   3) SKU сам не продаётся и не выставлен, но входит в набор, который на этом маркетплейсе продаётся или выставлен —
#      пусто, источник kit_only; всё остальное — пусто, источник none.
# Заморозка (plan_price_freeze_day, 15): цена месяца M обновляется каждый день до 15-го числа месяца M−1 включительно
# и с 16-го фиксируется — ценой расчёта «на 15-е». Дальние месяцы получают ту же текущую цену и обновляются до своего
# 15-го. Расчёт «на дату» воспроизводим: продажи, отчёт листингов, снимки витрины и Buy Box берутся по эту дату.
# Не воспроизводим только
# оффер Mirakl — истории офферов нет, поэтому у месяца, замороженного задним числом, цена оффера текущая и это
# написано в note.
#
# Где лежит:
#   kabinet_data.plan_price_daily — история: расчёт «на дату» по каждой паре, строка на день (что было известно);
#   kabinet_data.plan_price_month — цена месяца, frozen = зафиксирована; замороженную строку прогон не меняет.
# Запись в Google-таблицу (ячейка 3) — ТОЛЬКО в свои вкладки avg_<вкладка маркетплейса> (avg_Amazon_ES …
# avg_TikTok_ES, формат согласован с аналитиком 14.10.2026) и только при reorder_params.plan_price_sheet_write = 1.
# Параметр target_sheet = ключ другой таблицы (копии) — пишет туда для показа, флаг для этого не нужен.
# Вкладки аналитика, включая prices_*, не трогаем никогда.
#
# Контроль: где цена SP-API отличается от последнего снимка ScrapingDog больше чем на plan_price_scrape_diff_pct (15 %),
# ячейка печатает число таких пар и первые десять.
#
# Параметры: dry_run=1 — ничего не пишет ни в базу, ни в таблицу (Listings Items только читается), печатает покрытие;
# as_of=ГГГГ-ММ-ДД — «сегодня» для пробы.

# COMMAND ----------

# DBTITLE 1,1. Сырьё: действующая цена Amazon из Listings Items → dnipro_m.raw_amazon_listing_offers
# Снимок дня по всем нашим листингам ES/IT/FR/DE: purchasable_offer как отдаёт Amazon — обычная цена (our_price) и
# sale price (discounted_price) с датами действия, отдельно для всех покупателей (ALL) и B2B. Сырьё — без отбора:
# какая цена «действует», решает расчёт. История копится с первого прогона (15.10.2026), раньше её нет.
import json, time, requests
from datetime import datetime
from zoneinfo import ZoneInfo

dbutils.widgets.text("dry_run", "0")
_DRY1 = dbutils.widgets.get("dry_run").strip() == "1"
_EP, _SELLER = "https://sellingpartnerapi-eu.amazon.com", "A4JU8NB3VJG0K"   # один продавец на весь ЕС (AGENTS.md)
_MPS = {"ES": "A1RKKUPIHCS9HS", "IT": "APJ6JRA9NG5V4", "FR": "A13V1IB3VIYZZH", "DE": "A1PA6795UKMFR9"}
_snap = datetime.now(ZoneInfo("Europe/Kyiv")).date()
LI_ERRORS = []                                    # сбои рынков — в пульс и падение прогона в конце (ячейка 4)

def _sec(k):
    return dbutils.secrets.get("amazon-sp-api", k)
_tok = requests.post("https://api.amazon.com/auth/o2/token", data={
    "grant_type": "refresh_token", "refresh_token": _sec("refresh-token"),
    "client_id": _sec("lwa-app-id"), "client_secret": _sec("lwa-client-secret")}, timeout=30)
_tok.raise_for_status()
_H = {"x-amz-access-token": _tok.json()["access_token"]}

def _page(mp_id, token):
    params = {"marketplaceIds": mp_id, "includedData": "summaries,attributes", "pageSize": 20}
    if token:
        params["pageToken"] = token
    wait = 2.0
    for _ in range(9):
        r = requests.get(f"{_EP}/listings/2021-08-01/items/{_SELLER}", headers=_H, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(wait); wait = min(wait * 2, 60); continue
        if r.status_code >= 400:
            raise RuntimeError(f"searchListingsItems {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("[QUOTA_429] searchListingsItems: квота не освободилась")

def _sched(blocks):
    """[{schedule:[{value_with_tax, start_at, end_at}]}] → первое значение и его даты."""
    for b in blocks or []:
        for sc in b.get("schedule") or []:
            v = sc.get("value_with_tax")
            if v is not None:
                return float(v), sc.get("start_at"), sc.get("end_at")
    return None, None, None

_rows = []
for _cc, _mp in _MPS.items():
    try:
        _tokn, _n = None, 0
        while True:
            _j = _page(_mp, _tokn)
            for it in _j.get("items", []):
                sm = next((x for x in it.get("summaries") or [] if x.get("marketplaceId") == _mp), {})
                for po in (it.get("attributes") or {}).get("purchasable_offer") or []:
                    if po.get("marketplace_id") not in (None, _mp):
                        continue
                    our, _, _ = _sched(po.get("our_price"))
                    disc, d_from, d_to = _sched(po.get("discounted_price"))
                    _rows.append((_snap, _cc, it.get("sku"), sm.get("asin"), ",".join(sm.get("status") or []),
                                  po.get("audience") or "ALL", po.get("currency"), our, disc,
                                  d_from if disc is not None else None, d_to if disc is not None else None))
                _n += 1
            _tokn = (_j.get("pagination") or {}).get("nextToken")
            if not _tokn:
                break
            time.sleep(0.25)                          # 5 запросов в секунду на продавца
        print(f"Listings Items {_cc}: листингов {_n}")
    except Exception as _e:
        LI_ERRORS.append(f"{_cc}: {str(_e)[:200]}")
        print(f"⚠️ Listings Items {_cc}: {_e}")

_cols = ("snapshot_date date, marketplace string, seller_sku string, asin string, status string, audience string, "
         "currency string, our_price double, discounted_price double, discount_start string, discount_end string")
if _DRY1:
    print(f"dry run — сырьё не пишу: строк {len(_rows)}, со скидкой {sum(1 for r in _rows if r[8] is not None)}")
    spark.createDataFrame(_rows, _cols).createOrReplaceTempView("li_offers_dry")
else:
    spark.sql(f"""CREATE TABLE IF NOT EXISTS dnipro_m.dnipro_m.raw_amazon_listing_offers ({_cols}, loaded_at timestamp)
                  COMMENT 'Kabinet - Plan Matrix Prices: purchasable_offer из SP-API Listings Items, снимок дня по рынку'""")
    _done = sorted({r[1] for r in _rows})
    if _done:                                     # снимок дня по рынку переписывается целиком; упавший рынок не трогаем
        spark.createDataFrame(_rows, _cols).createOrReplaceTempView("li_offers_new")
        spark.sql(f"""DELETE FROM dnipro_m.dnipro_m.raw_amazon_listing_offers
                      WHERE snapshot_date = DATE'{_snap}' AND marketplace IN ({", ".join(f"'{c}'" for c in _done)})""")
        spark.sql("""INSERT INTO dnipro_m.dnipro_m.raw_amazon_listing_offers
                     SELECT *, current_timestamp() FROM li_offers_new""")
    print(f"✅ raw_amazon_listing_offers {_snap}: строк {len(_rows)} по {_done}; "
          f"со скидкой {sum(1 for r in _rows if r[8] is not None)}")

# COMMAND ----------

# DBTITLE 1,2. Расчёт цен → plan_price_daily, plan_price_month
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
MIN_UNITS = int(P.get("plan_price_min_units", 3))
FREEZE_DAY = int(P.get("plan_price_freeze_day", 15))
SCRAPE_DIFF = float(P.get("plan_price_scrape_diff_pct", 15))
MONTHS_AHEAD = int(P.get("plan_price_months_ahead", 15))
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
# лимит Sheets — 60 чтений в минуту на сервисный аккаунт, общий с Unified Pricing: повтор при 429 и одно пакетное чтение
from gspread.http_client import BackOffHTTPClient
_gc = gspread.authorize(Credentials.from_service_account_info(
    _info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]), http_client=BackOffHTTPClient)
_sh = _gc.open_by_key(SHEET_KEY)
_batch = _sh.values_batch_get([f"'{t}'!A1:ZZ6" for t in TABS] + [f"'{t}'!A1:B" for t in TABS])["valueRanges"]
SHEET_SKUS, MONTHS, skipped_cells = {}, None, []
for _k, _tab in enumerate(TABS):
    _head, _body = _batch[_k].get("values", []), _batch[_k + len(TABS)].get("values", [])
    _vals = _head + _body[len(_head):]          # шапка во всю ширину (месяцы), дальше — колонки A:B
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

# Месяцы — шапка таблицы плюс не меньше MONTHS_AHEAD вперёд от текущего: новые месяцы появляются сами
MONTHS = sorted(set(MONTHS) | {add_months(date(TODAY.year, TODAY.month, 1), i) for i in range(MONTHS_AHEAD)})

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

# ── Витрина Amazon: снимки ScrapingDog по дням — цена и купон ──
def parse_coupon(text):
    """«Aplicar cupón de 10 %» → ('pct', 10.0); «Applica coupon da 5,00 €» → ('eur', 5.0); иначе None.
    Флаг has_coupon без текста не берём: он стоит у тысяч снимков без купона на странице."""
    t = (text or "").replace("\u00a0", " ")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", t)
    if m:
        return ("pct", float(m.group(1).replace(",", ".")))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*€|€\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        return ("eur", float((m.group(1) or m.group(2)).replace(",", ".")))
    return None

scrape = []                                      # (code, sku, day, price)
coupon_obs = []                                  # (code, sku, fetched_at, купон или None) — последний снимок решает
for r in spark.sql(f"""
        SELECT marketplace, asin, fetched_at, to_date(from_utc_timestamp(fetched_at, 'Europe/Madrid')) AS d,
               display_price, regexp_extract(raw, '"coupon_text": *"([^"]*)"', 1) AS coupon_text
        FROM dnipro_m.dnipro_m.raw_amazon_listing_snapshots
        WHERE ok AND fetched_at >= DATE'{EARLIEST}' AND marketplace IN ('es', 'it', 'fr', 'de')""").collect():
    code = "AMZ-" + r.marketplace.upper()
    cp = parse_coupon(r.coupon_text)
    for s in asin_skus.get((code, r.asin), ()):
        if r.display_price and r.display_price > 0:
            scrape.append((code, s, r.d, float(r.display_price)))
        coupon_obs.append((code, s, r.fetched_at, r.d, cp))

# ── Наша цена листинга Amazon из SP-API: отчёт листингов по дням, только активные листинги ──
AMZ_REPORT = {"Spain (ES)": "AMZ-ES", "Italy (IT)": "AMZ-IT", "France (FR)": "AMZ-FR", "Germany (DE)": "AMZ-DE"}
spapi = defaultdict(lambda: defaultdict(list))   # code → report_date → [(sku, price)]
for r in spark.sql(f"""
        SELECT marketplace_name, report_date, seller_sku, price
        FROM dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data
        WHERE status = 'Active' AND price > 0 AND report_date >= DATE'{EARLIEST}'
          AND marketplace_name IN ({", ".join(f"'{k}'" for k in AMZ_REPORT)})""").collect():
    code = AMZ_REPORT[r.marketplace_name]
    spapi[code][r.report_date].append((listing_sku.get((code, r.seller_sku)) or norm(r.seller_sku), float(r.price)))

# ── Действующая цена Amazon из Listings Items (сырьё ячейки 1): снимки по дням, покупаемые листинги, для всех ──
li = defaultdict(lambda: defaultdict(list))      # code → snapshot_date → [(sku, our_price, sale, sale_from, sale_to)]
_li_src = ("li_offers_dry" if DRY and spark.catalog.tableExists("li_offers_dry")
           else "dnipro_m.dnipro_m.raw_amazon_listing_offers")
if _li_src == "li_offers_dry" or spark.catalog.tableExists(_li_src):
    for r in spark.sql(f"""
            SELECT snapshot_date, marketplace, seller_sku, our_price, discounted_price,
                   to_date(from_utc_timestamp(to_timestamp(discount_start), 'Europe/Madrid')) AS d_from,
                   to_date(from_utc_timestamp(to_timestamp(discount_end), 'Europe/Madrid')) AS d_to
            FROM {_li_src}
            WHERE audience = 'ALL' AND status LIKE '%BUYABLE%' AND our_price > 0
              AND snapshot_date >= DATE'{EARLIEST}'""").collect():
        code = "AMZ-" + r.marketplace
        li[code][r.snapshot_date].append((listing_sku.get((code, r.seller_sku)) or norm(r.seller_sku),
                                          float(r.our_price), r.discounted_price, r.d_from, r.d_to))

# ── Buy Box (SP-API Product Pricing): цена Buy Box, а нет её — наша цена в ответе ──
buybox = []                                      # (code, sku, day, price)
for mk, asin, d, bb, ours in q("""
        SELECT marketplace, asin, (checked_at AT TIME ZONE 'Europe/Madrid')::date, buybox_price, our_price
        FROM kabinet_data.buybox_status
        WHERE marketplace IN ('ES', 'IT', 'FR', 'DE') AND coalesce(buybox_price, our_price) > 0
          AND checked_at >= %s""", (EARLIEST,)):
    for s in asin_skus.get(("AMZ-" + mk, asin), ()):
        buybox.append(("AMZ-" + mk, s, d, float(bb if bb else ours)))

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
    scr, bbx = defaultdict(list), defaultdict(list)
    for code, s, d, p in scrape:
        if l_from <= d <= as_of:
            scr[(code, s)].append(p)
    for code, s, d, p in buybox:
        if l_from <= d <= as_of:
            bbx[(code, s)].append(p)
    lip, lip_info = defaultdict(list), {}        # Listings Items: снимок на дату (не старше 3 дней) → действующая цена
    for code, by_day in li.items():
        days = [d for d in by_day if as_of - timedelta(days=3) <= d <= as_of]
        if days:
            dd = max(days)
            for s, our, sale, f, t in by_day[dd]:
                live = sale is not None and sale > 0 and (f is None or f <= as_of) and (t is None or t >= as_of)
                lip[(code, s)].append(min(our, sale) if live else our)
                if live and sale < our:
                    lip_info[(code, s)] = f"sale price {sale:.2f} (обычная {our:.2f}) {f or '…'}–{t or '…'}"
            lip_info[("date", code)] = dd
    # Даты без снимка Listings Items (история до 15.10.2026): обычная цена из отчёта, но скидка, чьё расписание
    # покрывает дату расчёта, видна и в более позднем снимке — Amazon хранит последнее расписание sale price.
    # 84515000 ES на 15.09: отчёт 169,95 €, а скидка 129,99 € шла 03.09–30.09. Берём самый ранний снимок после даты.
    sched = {}
    for code, by_day in li.items():
        later = sorted(d for d in by_day if d > as_of)
        if later:
            for s, our, sale, f, t in by_day[later[0]]:
                if sale is not None and sale > 0 and f is not None and t is not None and f <= as_of <= t:
                    sched[(code, s)] = min(sale, sched.get((code, s), sale))
                    lip_info[("sched", code, s)] = f"{f:%d.%m}–{t:%d.%m}, из снимка Listings Items {later[0]:%d.%m}"
    cpn = {}                                     # (code, sku) → купон последнего снимка за окно
    for code, s, ts, d, cp in sorted(coupon_obs, key=lambda x: x[2]):
        if l_from <= d <= as_of:
            cpn[(code, s)] = cp
    sp = defaultdict(list)                       # отчёт листингов: последний на дату расчёта по каждому рынку
    sp_date = {}
    for code, by_day in spapi.items():
        days = [d for d in by_day if d <= as_of]
        if days:
            sp_date[code] = max(days)
            for s, p in by_day[sp_date[code]]:
                sp[(code, s)].append(p)
    def with_coupon(price, k):
        cp = cpn.get(k)
        if not cp:
            return price, None
        new = price * (1 - cp[1] / 100) if cp[0] == "pct" else price - cp[1]
        if new <= 0:
            return price, None
        return new, f"купон {cp[1]:g}{' %' if cp[0] == 'pct' else ' €'}"
    active = {k for k in agg if agg[k][1] > 0} | set(listed) | set(sp) | set(lip) | set(offers)
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
            sold = units > 0 and rev > 0
            few = f"продано {units} шт < {MIN_UNITS}; " if sold else ""
            if sold and units >= MIN_UNITS:
                out[k] = (round(rev / units, 2), "sales", units, round(rev, 2), None, f"{s_from}…{as_of}")
            elif lip.get(k) or sp.get(k):
                if lip.get(k):
                    base, n = min(lip[k]), len(lip[k])
                    how = f"Listings Items {lip_info[('date', code)]}" + (f", {lip_info[k]}" if k in lip_info else "")
                else:                                # снимка Listings Items на эту дату нет — обычная цена из отчёта
                    base, n, how = min(sp[k]), len(sp[k]), f"отчёт листингов {sp_date[code]} (без sale price)"
                    if sched.get(k) and sched[k] < base:
                        how = (f"отчёт листингов {sp_date[code]} {base:.2f}, sale price {sched[k]:.2f} по расписанию "
                               + lip_info[("sched", code, k[1])])
                        base = sched[k]
                p, cn = with_coupon(base, k)
                out[k] = (round(p, 2), "sp_api", units or None, round(rev, 2) if sold else None, n,
                          few + how + (f", {cn}" if cn else ""))
            elif scr.get(k):
                p, cn = with_coupon(sum(scr[k]) / len(scr[k]), k)
                out[k] = (round(p, 2), "scrape", units or None, round(rev, 2) if sold else None, len(scr[k]),
                          few + f"{l_from}…{as_of}" + (f", {cn}" if cn else ""))
            elif bbx.get(k):
                out[k] = (round(sum(bbx[k]) / len(bbx[k]), 2), "buybox", units or None,
                          round(rev, 2) if sold else None, len(bbx[k]), few + f"{l_from}…{as_of}")
            elif offers.get(k):
                out[k] = (round(sum(offers[k]) / len(offers[k]), 2), "offer", units or None,
                          round(rev, 2) if sold else None, len(offers[k]),
                          few + ("оффер на дату расчёта недоступен — взят текущий" if backfill else "текущий оффер"))
            elif sold:                           # меньше порога, но цены листинга нет — цена продаж лучше пустоты
                out[k] = (round(rev / units, 2), "sales", units, round(rev, 2), None,
                          few + f"цены листинга нет; {s_from}…{as_of}")
            elif k in listed:
                out[k] = (None, "listed_no_price", None, None, None, f"нет цены листинга, витрины и Buy Box за {l_from}…{as_of}")
            elif in_kit.get(k):
                out[k] = (None, "kit_only", None, None, None, "в наборах: " + ", ".join(sorted(in_kit[k])[:5]))
            else:
                out[k] = (None, "none", None, None, None, None)
    return out

calcs = {d: compute(d) for d in AS_OF}

# ── Покрытие по вкладкам (на сегодня) ──
_today = calcs[TODAY]
print("вкладка | SKU | из продаж | SP-API | скрейп | Buy Box | оффер | выставлен без цены | только в наборах | пусто"
      " | с купоном")
for tab, code in TABS.items():
    c = defaultdict(int)
    for s in SHEET_SKUS[tab]:
        v = _today[(code, s)]
        c[v[1]] += 1
        c["coupon"] += bool(v[5] and "купон" in v[5])
    print(f"{tab} | {len(SHEET_SKUS[tab])} | {c['sales']} | {c['sp_api']} | {c['scrape']} | {c['buybox']} | "
          f"{c['offer']} | {c['listed_no_price']} | {c['kit_only']} | {c['none']} | {c['coupon']}")
# ── Контроль: цена SP-API против последнего снимка ScrapingDog за окно ──
_last_scr = {}
for code, s, d, p in sorted(scrape, key=lambda x: x[2]):
    if TODAY - timedelta(days=LIST_DAYS - 1) <= d <= TODAY:
        _last_scr[(code, s)] = (p, d)
_cmp = [(code, s, v[0], _last_scr[(code, s)][0], _last_scr[(code, s)][1], v[5])
        for (code, s), v in _today.items() if v[1] == "sp_api" and (code, s) in _last_scr]
_far = sorted([c for c in _cmp if abs(c[3] / c[2] - 1) * 100 > SCRAPE_DIFF], key=lambda c: -abs(c[3] / c[2] - 1))
print(f"контроль SP-API ↔ ScrapingDog: сравнимых пар {len(_cmp)}, расходятся больше {SCRAPE_DIFF:g} %: {len(_far)}")
for code, s, p_sp, p_scr, d_scr, note in _far[:10]:
    print(f"   {s} {code}: SP-API {p_sp:.2f} · ScrapingDog {p_scr:.2f} ({d_scr}) · {(p_scr / p_sp - 1) * 100:+.0f} % · {note}")
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

# DBTITLE 1,3. Вкладки avg_<маркетплейс> в таблице (только при plan_price_sheet_write = 1 или в копию)
# Вкладка на маркетплейс: avg_Amazon_ES, …, avg_TikTok_ES. Строки — те же, что на вкладке аналитика, и на ТЕХ ЖЕ номерах
# строк (данные с 4-й), чтобы формула вида =avg_Amazon_ES!C4 брала свою строку. Колонки: Name, SKU, месяцы
# «October 2026» … — каждый месяц из plan_price_month (не меньше plan_price_months_ahead вперёд).
# Ячейка — цена месяца с НДС, 2 знака; пусто — цены нет. Текста в ячейках цены нет: замороженный месяц — серый фон,
# источник — цвет шрифта (легенда — заметкой к A1 и строкой 2 шапки).
# Проверка перед записью: цен на вкладке стало меньше прошлой записи больше чем на plan_price_sheet_guard_drop_pct,
# или не осталось ни одной — вкладку НЕ перезаписываем, заводим тревогу и шлём в бот. Сбой отправки — прогон падает
# после пульса.
import json, requests
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg2
import gspread
from google.oauth2.service_account import Credentials
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("dry_run", "0")
dbutils.widgets.text("target_sheet", "")
_DRY = dbutils.widgets.get("dry_run").strip() == "1"
_SRC_KEY = "1fA4Kla_IJ5LAlj07z69ya6TwE0MU7aYOa6fuTeOC0GM"          # таблица аналитика: отсюда только читаем строки
_TARGET = dbutils.widgets.get("target_sheet").strip() or _SRC_KEY
_TAB_OF = {"AMZ-ES": "Amazon_ES", "AMZ-IT": "Amazon_IT", "AMZ-FR": "Amazon_FR", "AMZ-DE": "Amazon_DE",
           "LM-ES": "LM_ES", "MM-ES": "MM_ES", "MM-FR": "MM_FR", "CF-ES": "CF_ES", "TTS-ES": "TikTok_ES"}
_rgb = lambda h: {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}
# цвет шрифта по источнику; продажи меньше порога (цены листинга нет) — отдельным цветом, их видно
_COLOR = {"sales": "000000", "sales_few": "7f6000", "sp_api": "1155cc", "scrape": "8e24aa", "buybox": "e65100",
          "offer": "38761d"}
_LEGEND = ("Цена месяца с НДС, € (2 знака). Пусто — цены нет.\n"
           "Серый фон — месяц заморожен (цена на 15-е число прошлого месяца).\n"
           "Цвет шрифта — источник: чёрный — продажи за 90 дней (от 3 шт); коричневый — продажи 1–2 шт, цены листинга нет; "
           "синий — наша цена листинга Amazon (SP-API, со скидкой и купоном); фиолетовый — витрина ScrapingDog; "
           "оранжевый — Buy Box; зелёный — оффер площадки (Leroy Merlin, ManoMano, Carrefour).\n"
           "Строки и их порядок берутся с вкладки маркетплейса при каждой записи. Брать цену лучше по SKU, а не по номеру "
           "строки: =IFERROR(INDEX(avg_Amazon_ES!C:C; MATCH($B4; avg_Amazon_ES!$B:$B; 0)); \"\").\n"
           "Считает Кабинет (Kabinet - Plan Matrix Prices), не редактировать вручную — перезаписывается каждый день.")
SHEET_ERRORS = []                                 # сбои отправки тревоги — прогон падает после пульса (ячейка 4)

_wc2 = WorkspaceClient()
_pg2 = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                        dbname="databricks_postgres", user=_wc2.current_user.me().user_name, sslmode="require",
                        password=_wc2.postgres.generate_database_credential(
                            endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
_c2 = _pg2.cursor()
_c2.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key IN ('plan_price_sheet_write', "
            "'plan_price_sheet_guard_drop_pct')")
_P2 = {k: float(v) for k, v in _c2.fetchall()}
_WRITE = _P2.get("plan_price_sheet_write", 0) == 1
_DROP = _P2.get("plan_price_sheet_guard_drop_pct", 30)
_to_source = _TARGET == _SRC_KEY

if _DRY or (_to_source and not _WRITE):
    print("вкладки avg_*: пропуск — " + ("dry run" if _DRY else "plan_price_sheet_write = 0 (ждёт решения владельца)"))
else:
    _c2.execute("""SELECT m.marketplace, m.sku, m.month, m.price, m.source, m.frozen, m.calc_date, d.note, d.computed_at
                   FROM kabinet_data.plan_price_month m
                   JOIN kabinet_data.plan_price_daily d USING (calc_date, marketplace, sku)""")
    _pm = {}
    _months = set()
    for mk, sku, m, price, src, fr, cd, dnote, comp in _c2.fetchall():
        # заметка к ячейке — только там, где цена не «на дату»: оффер Mirakl у месяца, замороженного задним числом
        cnote = (f"цена на {comp.astimezone(ZoneInfo('Europe/Kyiv')):%d.%m}, истории офферов нет"
                 if dnote and "оффер на дату расчёта недоступен" in dnote else None)
        _pm[(mk, sku, m)] = (price, src, fr, cd, cnote)
        _months.add(m)
    _c2.execute("""SELECT d.marketplace, d.sku FROM kabinet_data.plan_price_daily d
                   WHERE d.calc_date = (SELECT max(calc_date) FROM kabinet_data.plan_price_daily)
                     AND d.source = 'sales' AND d.note LIKE 'продано %'""")
    _few = set(_c2.fetchall())                    # «продажи 1–2 шт без листинга» — по последнему расчёту
    _months = sorted(_months)
    _frozen_m = {m for m in _months if all(v[2] for (mk, s, mm), v in _pm.items() if mm == m)}

    _info2 = json.loads(dbutils.secrets.get("kabinet-external", "google-sa-json"), strict=False)
    from gspread.http_client import BackOffHTTPClient   # повтор при 429: лимит чтений общий с Unified Pricing
    _gc2 = gspread.authorize(Credentials.from_service_account_info(
        _info2, scopes=["https://www.googleapis.com/auth/spreadsheets"]), http_client=BackOffHTTPClient)
    _src = _gc2.open_by_key(_SRC_KEY)             # только чтение строк
    _dst = _gc2.open_by_key(_TARGET)
    # строки всех вкладок — одним пакетным чтением, список листов копии/таблицы — одним запросом
    _rows_of = dict(zip(_TAB_OF.values(), (v.get("values", []) for v in _src.values_batch_get(
        [f"'{t}'!A1:B" for t in _TAB_OF.values()])["valueRanges"])))
    _ws_by = {w.title: w for w in _dst.worksheets()}
    _norm = lambda c: __import__("re").sub(r"^(\d{7})(?!\d)", r"0\1",
                                           __import__("re").sub(r"[-_]+$", "", str(c or "").strip()))
    _hdr_fmt = {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}
    _grey = _rgb("d9d9d9")
    _alerts, _written = [], []
    for mk, tab in _TAB_OF.items():
        vals = _rows_of[tab]
        n_rows = max(len(vals), 4)
        name_of = {i: (r[0] if len(r) > 0 else "", r[1] if len(r) > 1 else "") for i, r in enumerate(vals)}
        # сетка: строка 1 — Name, SKU, месяцы; строка 2 — «заморожен / до 15.MM»; строка 3 — пусто; дальше — как у неё
        grid = []
        head = [{"userEnteredValue": {"stringValue": "Name"}, "userEnteredFormat": _hdr_fmt,
                 "note": _LEGEND},
                {"userEnteredValue": {"stringValue": "SKU"}, "userEnteredFormat": _hdr_fmt}]
        sub = [{}, {}]
        for m in _months:
            fr = m in _frozen_m
            f = dict(_hdr_fmt, **({"backgroundColor": _grey} if fr else {}))
            head.append({"userEnteredValue": {"stringValue": m.strftime("%B %Y")}, "userEnteredFormat": f})
            prev = m.replace(day=1) - __import__("datetime").timedelta(days=1)
            sub.append({"userEnteredValue": {"stringValue": "заморожен" if fr else f"до 15.{prev:%m}"},
                        "userEnteredFormat": {"horizontalAlignment": "CENTER", "textFormat": {"italic": True},
                                              **({"backgroundColor": _grey} if fr else {})}})
        grid += [head, sub, []]
        n_prices = 0
        for i in range(3, n_rows):
            name, sku_cell = name_of.get(i, ("", ""))
            row = [{"userEnteredValue": {"stringValue": name}} if name else {},
                   {"userEnteredValue": {"stringValue": sku_cell}} if sku_cell else {}]
            sku = _norm(sku_cell)
            for m in _months:
                v = _pm.get((mk, sku, m)) if sku_cell else None
                cell = {"userEnteredFormat": {"backgroundColor": _grey}} if m in _frozen_m else {}
                if v and v[0] is not None:
                    src = "sales_few" if (v[1] == "sales" and (mk, sku) in _few and not v[2]) else v[1]
                    cell = {"userEnteredValue": {"numberValue": round(float(v[0]), 2)},
                            "userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"},
                                                  "textFormat": {"foregroundColor": _rgb(_COLOR.get(src, "000000"))},
                                                  **({"backgroundColor": _grey} if m in _frozen_m else {})}}
                    if v[4]:
                        cell["note"] = v[4]
                    n_prices += 1
                row.append(cell)
            grid.append(row)
        # проверка перед записью — против прошлой удачной записи в ЭТУ таблицу
        _c2.execute("""SELECT n_prices FROM kabinet_data.plan_price_sheet_log
                       WHERE target_sheet = %s AND tab = %s AND status = 'written' ORDER BY written_at DESC LIMIT 1""",
                    (_TARGET, "avg_" + tab))
        _prev = (_c2.fetchone() or [None])[0]
        if _prev and (n_prices == 0 or n_prices < _prev * (1 - _DROP / 100)):
            _why = f"цен {n_prices} против {_prev} в прошлой записи (порог −{_DROP:g} %)"
            _alerts.append(f"avg_{tab}: {_why}")
            with _pg2, _pg2.cursor() as _c:
                _c.execute("""INSERT INTO kabinet_data.plan_price_sheet_log (target_sheet, tab, n_rows, n_prices, status, note)
                              VALUES (%s, %s, %s, %s, 'skipped', %s)""", (_TARGET, "avg_" + tab, n_rows, n_prices, _why))
            print(f"⛔ avg_{tab}: не перезаписываю — {_why}")
            continue
        ws = _ws_by.get("avg_" + tab) or _dst.add_worksheet("avg_" + tab, rows=n_rows, cols=2 + len(_months))
        ws.resize(rows=n_rows, cols=2 + len(_months))     # лишние строки и колонки прошлой записи уходят
        reqs = [{"updateCells": {"range": {"sheetId": ws.id, "startRowIndex": r0, "endRowIndex": min(r0 + 300, n_rows),
                                           "startColumnIndex": 0, "endColumnIndex": 2 + len(_months)},
                                 "rows": [{"values": rw} for rw in grid[r0:r0 + 300]],
                                 "fields": "userEnteredValue,userEnteredFormat,note"}}
                for r0 in range(0, n_rows, 300)]
        reqs.append({"updateSheetProperties": {"properties": {"sheetId": ws.id, "gridProperties": {
            "frozenRowCount": 3, "frozenColumnCount": 2}}, "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}})
        _dst.batch_update({"requests": reqs})
        with _pg2, _pg2.cursor() as _c:
            _c.execute("""INSERT INTO kabinet_data.plan_price_sheet_log (target_sheet, tab, n_rows, n_prices, status, note)
                          VALUES (%s, %s, %s, %s, 'written', %s)""",
                       (_TARGET, "avg_" + tab, n_rows, n_prices, f"месяцы {_months[0]:%m.%Y}–{_months[-1]:%m.%Y}"))
        _written.append(f"avg_{tab} {n_prices}")
    print(f"✅ {'таблица аналитика' if _to_source else 'копия ' + _TARGET}: " + ", ".join(_written))

    # тревога: одна на прогон; закрывается сама, когда все вкладки записаны
    _TOKEN = "[PLANPRICE:" + ("таблица" if _to_source else _TARGET[:12]) + "]"
    with _pg2, _pg2.cursor() as _c:
        _c.execute("""SELECT id FROM kabinet_data.incidents WHERE incident_type = 'plan_price_sheet_guard'
                      AND status <> 'resolved' AND message LIKE %s""", (_TOKEN + "%",))
        _open = [r[0] for r in _c.fetchall()]
        if _alerts:
            _msg = (f"{_TOKEN} Plan Matrix: средние цены НЕ перезаписаны во вкладках " + "; ".join(_alerts)
                    + ". В таблице остались цены прошлой записи.")
            if _open:
                _c.execute("UPDATE kabinet_data.incidents SET message = %s WHERE id = ANY(%s)", (_msg, _open))
            else:
                _c.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, source)
                              VALUES ('plan_price_sheet_guard', 'high', %s, 'open', 'watchdog')""", (_msg,))
                try:
                    _r = requests.post(
                        f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                        json={"chat_id": dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"),
                              "text": "🟠 <b>Plan Matrix: цены не перезаписаны</b>\n"
                                      + _msg.replace(_TOKEN + " ", "").replace("&", "&amp;").replace("<", "&lt;"),
                              "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=30)
                    if not _r.ok:
                        SHEET_ERRORS.append(f"бот {_r.status_code}: {_r.text[:150]}")
                except Exception as _e:
                    SHEET_ERRORS.append(f"бот: {type(_e).__name__}: {str(_e)[:150]}")
        elif _open:
            _c.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                          resolved_by = 'watchdog-autoclose: вкладки avg_* записаны' WHERE id = ANY(%s)""", (_open,))
_pg2.close()

# COMMAND ----------

# DBTITLE 1,4. Пульс
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
# Сбой Listings Items по рынку не останавливает расчёт (цена берётся из отчёта листингов), но прогон обязан упасть —
# после пульса, чтобы «джоба зелёная» не прятала, что sale price по рынку не обновилась
if globals().get("LI_ERRORS") or globals().get("SHEET_ERRORS"):
    raise RuntimeError("; ".join([f"Listings Items: {e}" for e in globals().get("LI_ERRORS") or []]
                                 + [f"тревога Plan Matrix: {e}" for e in globals().get("SHEET_ERRORS") or []]))
