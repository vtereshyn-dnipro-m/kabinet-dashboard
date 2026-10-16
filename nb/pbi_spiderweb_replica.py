# Databricks notebook source
# DBTITLE 1,Kabinet - Power BI Replica: витрина Power BI → Lakebase
# Kabinet - Power BI Replica (с 08.10.2026, решение владельца: Кабинет показывает ТЕ ЖЕ цифры, что Power BI)
#
# Power BI «Marketplaces Report» читает витрину dnipro_m.dnipro_m.v_all_marketplaces_spiderweb_report в режиме Import,
# и его карточки — прямые суммы её колонок (DAX почти нет, только Average Basket Depth). Страницы Кабинета ходят
# только в Lakebase, поэтому витрина копируется сюда — в kabinet_data.pbi_spiderweb_report — целиком, одной
# транзакцией: удалить всё и записать заново. Частичной записи быть не может, иначе Кабинет показал бы половину месяца.
#
# Строка — день × рынок × SKU. В витрине их больше (у SKU бывает два ASIN), суммы при схлопывании не меняются.
# Строки, где все числа нулевые, не копируются: витрина плотная (200 тыс. строк, из них с числами около 28 тыс.).
# Код рынка — тот же, что в экономике Кабинета (ES, GB, LM, MM_ES, CF_ES, WP_ES…), чтобы фильтры и подписи
# страниц работали без второго словаря.
#
# Запуск (с 14.10.2026, решение владельца): по ЗАПИСИ в таблицу Amazon витрины dnipro_m.dnipro_m.raw_amazon_spiderweb_report
# (её пересобирает джоба Дарины около 10:20; запуск через 5 минут тишины) — Кабинет обновляется раньше экрана Power BI,
# который тянет витрину около 10:35–11:45. Дальше — задачей в джобе сверки в 13:00 (сверка сначала обновляет реплику) и
# запускалкой `Kabinet - Power BI Replica (16:45)`: подхватить дневные заказы Leroy Merlin, ManoMano и Carrefour (у них
# витрина считается на лету из наших таблиц). До 14.10 было расписание 12:45 / 16:45, и с ~10:20 до 12:45 Кабинет
# показывал вчерашнюю сборку Amazon, а Power BI — уже сегодняшнюю.
#
# Защита от неполной сборки (14.10.2026, решение владельца). 13.10 витрина Amazon собралась неполной (Испания 2,5 тыс.
# вместо 13 тыс. €, Бельгии и Британии нет), и реплика скопировала её молча. Теперь перед заменой новая витрина
# сравнивается с текущей репликой по ОДНИМ И ТЕМ ЖЕ дням (последние pbi_guard_days дней, 14, что есть в обеих) по каждому
# рынку: продажи с НДС упали больше чем на pbi_guard_drop_pct % или рынок пропал (при прежней сумме от
# pbi_guard_min_eur) — реплику НЕ заменяем, оставляем прежнюю (продажи, заказы и справочник — все три, чтобы они не
# разошлись между собой); на страницах плашка «Данные Amazon в источнике неполные», в бот — тревога (инцидент pbi_source_incomplete),
# сверка 1:1 пишет «источник неполный», а не «расхождение». Решение и время сборки витрины (DESCRIBE HISTORY) ложатся
# в kabinet_data.pbi_replica_meta — его читают страницы и паспорт данных.

# COMMAND ----------

# DBTITLE 1,1. Витрина → kabinet_data.pbi_spiderweb_report (с защитой от неполной сборки)
import psycopg2, psycopg2.extras, requests


def tg_to_subscribers(text):
    """Копия тревоги подписчикам бота (kabinet_data.telegram_subscribers, status = 'active': /start в
    @kabinet_dm_alerts_bot и разрешение владельца). Основной чат (владелец) шлёт вызывающий код как раньше и он
    подписан всегда. Подписчикам — лучшим усилием: не дошло — причины в ответе, прогон из-за них не падает."""
    import psycopg2 as _tg_pg, requests as _tg_rq
    from databricks.sdk import WorkspaceClient as _TgWC
    try:
        _tg_w = _TgWC()
        _tg_c = _tg_pg.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                               dbname="databricks_postgres", user=_tg_w.current_user.me().user_name, sslmode="require",
                               password=_tg_w.postgres.generate_database_credential(
                                   endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
        try:
            with _tg_c.cursor() as _tg_cur:
                _tg_cur.execute("SELECT chat_id FROM kabinet_data.telegram_subscribers WHERE status = 'active'")
                _tg_subs = [str(r[0]) for r in _tg_cur.fetchall()]
        finally:
            _tg_c.close()
    except Exception as e:
        return [f"подписчики не прочитались: {type(e).__name__}: {str(e)[:120]}"]
    _tg_main = str(dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")).strip()
    _tg_tok = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")
    _tg_errs = []
    for _tg_chat in _tg_subs:
        if _tg_chat == _tg_main:
            continue
        try:
            _tg_r = _tg_rq.post(f"https://api.telegram.org/bot{_tg_tok}/sendMessage",
                                json={"chat_id": _tg_chat, "text": text[:4000], "parse_mode": "HTML",
                                      "disable_web_page_preview": True}, timeout=30)
            if not _tg_r.ok:
                _tg_errs.append(f"подписчик {_tg_chat}: {_tg_r.status_code} {_tg_r.text[:100]}")
        except Exception as e:
            _tg_errs.append(f"подписчик {_tg_chat}: {type(e).__name__}")
    return _tg_errs


from databricks.sdk import WorkspaceClient

VIEW = "dnipro_m.dnipro_m.v_all_marketplaces_spiderweb_report"
AMZ_TABLE = "dnipro_m.dnipro_m.raw_amazon_spiderweb_report"
# площадка и страна витрины → код рынка Кабинета (как в экономике)
AMAZON = {"Spain": "ES", "Italy": "IT", "France": "FR", "Germany": "DE", "Belgium": "BE", "Netherlands": "NL",
          "United Kingdom": "GB", "Sweden": "SE", "Poland": "PL", "Ireland": "IE"}
OTHER = {("Leroy Merlin", "Spain"): "LM", ("ManoMano", "Spain"): "MM_ES", ("ManoMano", "France"): "MM_FR",
         ("ManoMano", "ES_B2B"): "MMB_ES", ("ManoMano Pro", "Spain"): "MMB_ES", ("ManoMano Pro", "ES_B2B"): "MMB_ES",
         ("Carrefour", "Spain"): "CF_ES", ("Wallapop", "Spain"): "WP_ES", ("Website", "Spain"): "WEB_ES"}
# колонки витрины в порядке таблицы; paidUnits / paidSales — в Postgres без кавычек регистр имени теряется
NUM = ["units_sold", "sales_vat_incl", "sales_vat_excl", "tax_amount", "commission_fee_vat_excl",
       "cancel_commission_vat_excl", "cogs_total", "shipping_cost_total", "packing_cost_total", "expenses",
       "quantity_refund", "refund_total_vat_incl", "refund_total_vat_excl", "refunds_commissions_vat_excl",
       "expenses_refund", "cogs_refund", "shipping_cost_refund", "reimbursment", "impressions", "clicks", "spend",
       "paidUnits", "paidSales", "profit", "contribution_profit"]
COLS = [c.lower().replace("paidunits", "paid_units").replace("paidsales", "paid_sales") for c in NUM]
INCIDENT_TOKEN = "[PBISRC:витрина Power BI]"


def code_of(mk, country):
    """Код рынка Кабинета; незнакомая пара не теряется, а получает свой код и называется в пульсе."""
    if mk == "Amazon" and country in AMAZON:
        return AMAZON[country]
    return OTHER.get((mk, country)) or f"?{mk}/{country}"


agg = ", ".join(f"sum(CAST(`{c}` AS double)) AS `{c}`" for c in NUM)
nonzero = " OR ".join(f"sum(CAST(`{c}` AS double)) <> 0" for c in NUM)
src = spark.sql(f"""
    SELECT date, marketplace, country, sku, {agg}
    FROM {VIEW}
    GROUP BY date, marketplace, country, sku
    HAVING {nonzero}""").collect()
if not src:
    # пустая витрина при живом источнике — поломка чтения, а не «продаж нет»: реплику не трогаем
    raise RuntimeError(f"{VIEW} не отдала ни одной строки — реплику не переписываю")

rows, unknown = {}, set()
for r in src:
    code = code_of(r["marketplace"], r["country"])
    if code.startswith("?"):
        unknown.add(code)
    key = (r["date"], code, r["sku"] or "")
    vals = [float(r[c] or 0.0) for c in NUM]
    if key in rows:      # две пары «площадка + страна» на один код (ManoMano Pro) — складываем
        rows[key][2] = [a + b for a, b in zip(rows[key][2], vals)]
    else:
        rows[key] = [r["marketplace"], r["country"], vals]
out = [(d, code, sku, mk, ctry, *vals) for (d, code, sku), (mk, ctry, vals) in rows.items()]

# время сборки витрины Amazon — последняя запись в её таблицу; его показывают страницы («Как в Power BI на …»)
try:
    SOURCE_BUILT_AT = spark.sql(f"DESCRIBE HISTORY {AMZ_TABLE} LIMIT 1").collect()[0]["timestamp"]
except Exception as e:
    SOURCE_BUILT_AT = None
    print(f"⚠️ история {AMZ_TABLE} не прочиталась: {type(e).__name__}: {str(e)[:160]}")

# до скольки экран Power BI обычно успевает подтянуть витрину — ОЦЕНКА по журналу доступа: медиана последнего захода
# Power BI за день по 14 прошедшим дням (его обновление ходит под учёткой владельца витрины драйвером PowerBI).
# Страницы пишут «В Power BI цифры обновятся до ~ЧЧ:ММ — до этого там могут быть вчерашние». Не прочиталось — без оценки.
try:
    _m = spark.sql("""
        SELECT percentile_approx(m, 0.5) AS m FROM (
          SELECT event_date, max(hour(from_utc_timestamp(event_time, 'Europe/Kyiv')) * 60
                                 + minute(from_utc_timestamp(event_time, 'Europe/Kyiv'))) AS m
          FROM system.access.audit
          WHERE event_date >= current_date() - 14 AND event_date < current_date()
            AND user_agent RLIKE 'PowerBI' AND action_name = 'tokenLogin'
          GROUP BY event_date)""").collect()[0]["m"]
    PBI_REFRESH_UNTIL = f"{int(_m) // 60:02d}:{int(_m) % 60:02d}" if _m is not None else None
except Exception as e:
    PBI_REFRESH_UNTIL = None
    print(f"⚠️ журнал доступа не прочитался: {type(e).__name__}: {str(e)[:160]}")

_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")

# ── защита: новая витрина против текущей реплики по одним и тем же дням, по каждому рынку ──
GUARD = []                             # [(рынок, было, стало, «упал на N %» / «пропал»)]
with pg, pg.cursor() as cur:
    cur.execute("""SELECT key, value FROM kabinet_data.reorder_params
                   WHERE key IN ('pbi_guard_drop_pct', 'pbi_guard_min_eur', 'pbi_guard_days')""")
    _gp = {k: float(v) for k, v in cur.fetchall()}
    G_DROP = _gp.get("pbi_guard_drop_pct", 30.0)
    G_MIN = _gp.get("pbi_guard_min_eur", 50.0)
    G_DAYS = int(_gp.get("pbi_guard_days", 14))
    cur.execute("SELECT max(date) FROM kabinet_data.pbi_spiderweb_report")
    _old_max = cur.fetchone()[0]
    if _old_max is not None:                       # первая загрузка — сравнивать не с чем
        _to = min(_old_max, max(k[0] for k in rows))
        cur.execute("""SELECT marketplace, sum(sales_vat_incl)::float FROM kabinet_data.pbi_spiderweb_report
                       WHERE date > %s::date - %s AND date <= %s GROUP BY 1""", (_to, G_DAYS, _to))
        _old = dict(cur.fetchall())
        _new = {}
        for (d, code, sku), (mk, ctry, vals) in rows.items():
            if d <= _to and (_to - d).days < G_DAYS:
                _new[code] = _new.get(code, 0.0) + vals[NUM.index("sales_vat_incl")]
        for code, was in sorted(_old.items(), key=lambda x: -x[1]):
            if was < G_MIN:
                continue
            now_ = _new.get(code, 0.0)
            if now_ <= 0.005:
                GUARD.append((code, was, now_, "пропал"))
            elif now_ < was * (1 - G_DROP / 100):
                GUARD.append((code, was, now_, f"упал на {(1 - now_ / was) * 100:.0f} %"))
KEPT = bool(GUARD)
GUARD_DETAIL = "; ".join(f"{c}: было {w:,.0f} €, стало {n:,.0f} € — {why}".replace(",", " ") for c, w, n, why in GUARD)

with pg, pg.cursor() as cur:
    if KEPT:
        # витрина неполная: реплику не трогаем, на страницах остаются цифры прошлой полной замены
        cur.execute("SELECT max(loaded_at) FROM kabinet_data.pbi_replica_meta WHERE status = 'replaced'")
        _shown = cur.fetchone()[0]
        cur.execute("""INSERT INTO kabinet_data.pbi_replica_meta
                           (status, source_built_at, shown_as_of, detail, window_days, pbi_refresh_until)
                       VALUES ('kept', %s, %s, %s, %s, %s)""",
                    (SOURCE_BUILT_AT, _shown, GUARD_DETAIL, G_DAYS, PBI_REFRESH_UNTIL))
    else:
        # одна транзакция: удалить всё и записать заново — у витрины меняется и история (тарифы доставки, возвраты)
        cur.execute("DELETE FROM kabinet_data.pbi_spiderweb_report WHERE true")
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO kabinet_data.pbi_spiderweb_report
                (date, marketplace, sku, pbi_marketplace, pbi_country, {', '.join(COLS)})
            VALUES %s""", out, page_size=2000)
        cur.execute("""INSERT INTO kabinet_data.pbi_replica_meta
                           (status, source_built_at, shown_as_of, detail, window_days, pbi_refresh_until)
                       VALUES ('replaced', %s, now(), NULL, %s, %s)""", (SOURCE_BUILT_AT, G_DAYS, PBI_REFRESH_UNTIL))

# ── тревога: открыть один раз и сразу в бот; обновлять текст, пока висит; закрыть, когда витрина снова полная ──
SEND_ERR = None
with pg, pg.cursor() as cur:
    cur.execute("""SELECT id FROM kabinet_data.incidents WHERE incident_type = 'pbi_source_incomplete'
                   AND status <> 'resolved' AND message LIKE %s""", (INCIDENT_TOKEN + "%",))
    _open = [r[0] for r in cur.fetchall()]
    _built = f" (сборка {SOURCE_BUILT_AT:%d.%m %H:%M} UTC)" if SOURCE_BUILT_AT else ""
    _msg = (f"{INCIDENT_TOKEN} Витрина Power BI собралась неполной{_built} — реплику Кабинета НЕ заменяю, на страницах "
            f"прежние цифры. {GUARD_DETAIL}")
    if KEPT and _open:
        cur.execute("UPDATE kabinet_data.incidents SET message = %s WHERE id = ANY(%s)", (_msg, _open))
    elif KEPT:
        cur.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, source)
                       VALUES ('pbi_source_incomplete', 'high', %s, 'open', 'watchdog')""", (_msg,))
        # основной чат (владелец) — как раньше: не ушло → прогон падает после пульса; копия — подписчикам бота тревог
        _chats = [("основной", dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"))]
        _text = ("🔴 <b>Витрина Power BI неполная</b>\n"
                 + _msg.replace(INCIDENT_TOKEN + " ", "").replace("&", "&amp;").replace("<", "&lt;"))
        _errs = {}
        for _who, _chat in _chats:
            try:
                _r = requests.post(
                    f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                    json={"chat_id": _chat, "text": _text, "parse_mode": "HTML", "disable_web_page_preview": True},
                    timeout=30)
                if not _r.ok:
                    _errs[_who] = f"{_r.status_code}: {_r.text[:150]}"
            except Exception as e:
                _errs[_who] = f"{type(e).__name__}: {str(e)[:150]}"
        SEND_ERR = _errs.get("основной")       # не ушло в основной чат — прогон падает после пульса
        _sub = tg_to_subscribers(_text)
        if _sub:
            cur.execute("""UPDATE kabinet_data.incidents SET message = message || %s
                           WHERE incident_type = 'pbi_source_incomplete' AND status <> 'resolved'""",
                        (" Подписчикам не ушло: " + "; ".join(_sub)[:200],))
        if SEND_ERR:
            cur.execute("""UPDATE kabinet_data.incidents SET message = message || %s
                           WHERE incident_type = 'pbi_source_incomplete' AND status <> 'resolved'""",
                        (f" В бот сразу не ушло: {SEND_ERR}",))
    elif _open:
        cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                       resolved_by = 'watchdog-autoclose: витрина снова полная, реплика заменена'
                       WHERE id = ANY(%s)""", (_open,))
pg.close()

_by = {}
for (d, code, sku), (mk, ctry, vals) in rows.items():
    _by[code] = _by.get(code, 0.0) + vals[NUM.index("sales_vat_incl")]
REPLICA_NOTE = ((f"ВИТРИНА НЕПОЛНАЯ — реплика не заменена ({GUARD_DETAIL})" if KEPT else
                 f"строк {len(out)} по {min(k[0] for k in rows)}–{max(k[0] for k in rows)}")
                + (f"; сборка витрины Amazon {SOURCE_BUILT_AT:%d.%m %H:%M} UTC" if SOURCE_BUILT_AT else "")
                + (f"; незнакомые рынки витрины: {', '.join(sorted(unknown))}" if unknown else "")
                + (f"; тревога в бот НЕ ушла: {SEND_ERR}" if SEND_ERR else ""))
print("⛔" if KEPT else "✅", REPLICA_NOTE)
print("   продажи с НДС в витрине: " + ", ".join(f"{k} {v:,.0f}" for k, v in sorted(_by.items(), key=lambda x: -x[1])))

# COMMAND ----------

# DBTITLE 1,2. Заказы → kabinet_data.pbi_orders_report
# Вторая таблица модели Power BI: строка на заказ. Из неё его карточки Orders Count (число строк), Average Order Value
# (сумма order_total_amount_eur / число строк) и Average Basket Depth (среднее unique_sku_ordered). Связана в модели
# с продажами только через календарь (дата × страна × площадка), поэтому разреза по категории и SKU у заказов нет.
# Ячейка 1 оставила прежнюю реплику (витрина неполная) — заказы тоже не трогаем, иначе разойдутся с продажами.
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

ORDERS_VIEW = "dnipro_m.dnipro_m.v_all_marketplaces_orders_enriched"
AMAZON = {"Spain": "ES", "Italy": "IT", "France": "FR", "Germany": "DE", "Belgium": "BE", "Netherlands": "NL",
          "United Kingdom": "GB", "Sweden": "SE", "Poland": "PL", "Ireland": "IE"}
OTHER = {("Leroy Merlin", "Spain"): "LM", ("ManoMano", "Spain"): "MM_ES", ("ManoMano", "France"): "MM_FR",
         ("ManoMano", "ES_B2B"): "MMB_ES", ("ManoMano Pro", "Spain"): "MMB_ES", ("ManoMano Pro", "ES_B2B"): "MMB_ES",
         ("Carrefour", "Spain"): "CF_ES", ("Wallapop", "Spain"): "WP_ES", ("Website", "Spain"): "WEB_ES"}


def code_of(mk, country):
    if mk == "Amazon" and country in AMAZON:
        return AMAZON[country]
    return OTHER.get((mk, country)) or f"?{mk}/{country}"


_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")
with pg.cursor() as cur:
    cur.execute("""SELECT status FROM kabinet_data.pbi_replica_meta
                   WHERE loaded_at > now() - interval '30 minutes' ORDER BY loaded_at DESC LIMIT 1""")
    _st = cur.fetchone()
pg.rollback()
if _st and _st[0] == "kept":
    ORDERS_NOTE = "заказы не заменены — витрина неполная"
else:
    src = spark.sql(f"""SELECT source, order_id, purchase_date, marketplace, country,
                               CAST(order_total_amount_eur AS double) AS amt, CAST(items_quantity_ordered AS double) AS items,
                               CAST(unique_sku_ordered AS bigint) AS uniq
                        FROM {ORDERS_VIEW}""").collect()
    if not src:
        raise RuntimeError(f"{ORDERS_VIEW} не отдала ни одной строки — заказы не переписываю")
    orows = {}
    for r in src:
        # ключ витрины — заказ внутри источника; повтор (если появится) не множит заказ, а заменяет строку
        orows[(r["source"], r["order_id"])] = (r["order_id"], r["source"], r["purchase_date"],
                                               code_of(r["marketplace"], r["country"]), r["marketplace"], r["country"],
                                               r["amt"], r["items"], r["uniq"])
    with pg, pg.cursor() as cur:
        cur.execute("DELETE FROM kabinet_data.pbi_orders_report WHERE true")
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.pbi_orders_report
                (order_id, source, purchase_date, marketplace, pbi_marketplace, pbi_country,
                 order_total_amount_eur, items_quantity_ordered, unique_sku_ordered)
            VALUES %s""", list(orows.values()), page_size=2000)
    ORDERS_NOTE = f"заказов {len(orows)}" + (f" (повторов в витрине {len(src) - len(orows)})" if len(src) != len(orows) else "")
pg.close()
print("✅", ORDERS_NOTE)

# COMMAND ----------

# DBTITLE 1,3. Категории и названия SKU → kabinet_data.pbi_sku_categories
# Справочник Power BI: название и три уровня категорий по SKU. У SKU без кода в дереве ERP витрина ставит название
# «Need to Name» и категорию «Set» — копируем как есть, иначе разрез по категориям разошёлся бы с Power BI.
# Витрина неполная (ячейка 1 оставила прежнюю реплику) — справочник тоже не трогаем.
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

CAT_VIEW = "dnipro_m.dnipro_m.v_sku_names_categories"
_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")
with pg.cursor() as cur:
    cur.execute("""SELECT status FROM kabinet_data.pbi_replica_meta
                   WHERE loaded_at > now() - interval '30 minutes' ORDER BY loaded_at DESC LIMIT 1""")
    _st = cur.fetchone()
pg.rollback()
if _st and _st[0] == "kept":
    CATS_NOTE = "справочник не заменён — витрина неполная"
else:
    src = spark.sql(f"""SELECT sku, name_en, name_ukr, category_level1_en, category_level2_en, category_level3_en,
                               category_level1_ukr, category_level2_ukr, category_level3_ukr
                        FROM {CAT_VIEW} WHERE sku IS NOT NULL""").collect()
    if not src:
        raise RuntimeError(f"{CAT_VIEW} не отдала ни одной строки — справочник не переписываю")
    cats = {r["sku"]: tuple(r) for r in src}
    with pg, pg.cursor() as cur:
        cur.execute("DELETE FROM kabinet_data.pbi_sku_categories WHERE true")
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.pbi_sku_categories
                (sku, name_en, name_ukr, category_level1_en, category_level2_en, category_level3_en,
                 category_level1_ukr, category_level2_ukr, category_level3_ukr)
            VALUES %s""", list(cats.values()), page_size=1000)
    CATS_NOTE = f"SKU в справочнике {len(cats)}"
pg.close()
print("✅", CATS_NOTE)

# COMMAND ----------

# DBTITLE 1,4. Пульс
# Последней операцией, безусловно: «ячейки доработали до конца», а не «всё внутри было без замечаний»
import psycopg2
from databricks.sdk import WorkspaceClient
_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
_pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                       port=5432, dbname="databricks_postgres",
                       user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")
_parts = [globals().get(k) for k in ("REPLICA_NOTE", "ORDERS_NOTE", "CATS_NOTE")]
# ячейку пульса могли запустить отдельно — тогда заметок нет
_note = "; ".join(p for p in _parts if p) or "реплика витрины Power BI"
with _pg, _pg.cursor() as _c:
    _c.execute("""
        INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
        VALUES ('Kabinet - Power BI Replica', now(), %s, 26)
        ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (_note,))
_pg.close()
print("💓 Kabinet - Power BI Replica")
# тревогу «витрина неполная» не доставили в бот — молчание канала должно быть красным: падаем после пульса
if globals().get("SEND_ERR"):
    raise RuntimeError(f"тревога «витрина Power BI неполная» не ушла в бот: {SEND_ERR}")
