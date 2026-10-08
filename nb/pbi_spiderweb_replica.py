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
# Расписание — 12:45 и 16:45 Kyiv: после пересчёта Amazon в витрине (10:50) и загрузчиков Mirakl и Odoo, до сверки
# в 13:00 (она сравнивает реплику с живой витриной — расхождение больше 1 € значит, что Кабинет показывает не то,
# что Power BI), и второй раз после вечернего прогона Leroy Merlin (15:30).

# COMMAND ----------

# DBTITLE 1,1. Витрина → kabinet_data.pbi_spiderweb_report
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

VIEW = "dnipro_m.dnipro_m.v_all_marketplaces_spiderweb_report"
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

_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")
with pg, pg.cursor() as cur:
    # одна транзакция: удалить всё и записать заново — у витрины меняется и история (тарифы доставки, возвраты)
    cur.execute("DELETE FROM kabinet_data.pbi_spiderweb_report")
    psycopg2.extras.execute_values(cur, f"""
        INSERT INTO kabinet_data.pbi_spiderweb_report
            (date, marketplace, sku, pbi_marketplace, pbi_country, {', '.join(COLS)})
        VALUES %s""", out, page_size=2000)
pg.close()

_by = {}
for (d, code, sku), (mk, ctry, vals) in rows.items():
    _by[code] = _by.get(code, 0.0) + vals[NUM.index("sales_vat_incl")]
REPLICA_NOTE = (f"строк {len(out)} по {min(k[0] for k in rows)}–{max(k[0] for k in rows)}"
                + (f"; незнакомые рынки витрины: {', '.join(sorted(unknown))}" if unknown else ""))
print("✅", REPLICA_NOTE)
print("   продажи с НДС: " + ", ".join(f"{k} {v:,.0f}" for k, v in sorted(_by.items(), key=lambda x: -x[1])))

# COMMAND ----------

# DBTITLE 1,2. Пульс
# Последней операцией, безусловно: «ячейки доработали до конца», а не «всё внутри было без замечаний»
import psycopg2
from databricks.sdk import WorkspaceClient
_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
_pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                       port=5432, dbname="databricks_postgres",
                       user=_w.current_user.me().user_name, password=_cred.token, sslmode="require")
try:
    _note = REPLICA_NOTE
except NameError:      # ячейку пульса запустили отдельно
    _note = "реплика витрины Power BI"
with _pg, _pg.cursor() as _c:
    _c.execute("""
        INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
        VALUES ('Kabinet - Power BI Replica', now(), %s, 26)
        ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (_note,))
_pg.close()
print("💓 Kabinet - Power BI Replica")
