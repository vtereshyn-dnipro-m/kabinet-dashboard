# Databricks notebook source
# DBTITLE 1,Kabinet - Odoo Channels Loader: Wallapop и сайт
# Kabinet - Odoo Channels Loader (с 08.10.2026)
#
# Продажи Wallapop и сайта приходят в Odoo командами продаж «Wallapop» и «Website». Сырьё — таблица
# dnipro_m.raw_odoo_sales (загрузчик Odoo, 10:11 Kyiv, перечитывает последние 30 дней). Здесь:
#   1) реплика строк этих двух команд в Lakebase — kabinet_data.raw_odoo_channel_sales (страницы читают только
#      Lakebase; первоисточник остаётся в dnipro_m);
#   2) строки экономики WP_ES и WEB_ES в kabinet_data.economics_summary.
#
# Правила — те же, что у витрины продаж для Power BI (raw_odoo_sales_fees_cogs_es), чтобы «все каналы» сходились:
#   * в продажи идут только заказы в состоянии 'sale' (отменённые и черновики — нет);
#   * товар — строка с артикулом; строка без артикула — доставка, её оплату покупателем не считаем;
#   * скидка WooCommerce (строки woo_discount) разносится по товарам заказа пропорционально их сумме без НДС.
#     У нас она идёт не в комиссии, а в «промо и прочие удержания» (разница между выручкой и выплатой), как промо
#     Amazon: это скидка покупателю, а не сбор площадки. Строки заказа задваиваются в самом Odoo (две строки одного
#     товара по штуке) — итог заказа это подтверждает, поэтому их не схлопываем.
# Себестоимость — общая цепочка sku_cogs_current (как у Mirakl), упаковка и доставка — ячейка 11 Economics Loader
# (WP_ES и WEB_ES там в списке каналов с доставкой на все штуки по тарифу ES).
# Строки WP_ES и WEB_ES принадлежат только этому загрузчику: он пересоздаёт их целиком одной транзакцией.

# COMMAND ----------

# DBTITLE 1,1. Реплика строк Wallapop и сайта → kabinet_data.raw_odoo_channel_sales
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

CHANNELS = {"Wallapop": "WP_ES", "Website": "WEB_ES"}   # команда продаж Odoo → код рынка экономики

_wc = WorkspaceClient()
_cred = _wc.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user="v.tereshyn@dniprom.com", password=_cred.token, sslmode="require")

teams = ", ".join(f"'{t_}'" for t_ in CHANNELS)
raw = spark.sql(f"""
    SELECT order_number, sales_team, order_state, CAST(date_order_madrid AS DATE) AS order_date, date_order_madrid,
           NULLIF(trim(sku), '') AS sku, product_title, qty, price_unit, price_subtotal, price_total, order_amount_total
    FROM dnipro_m.dnipro_m.raw_odoo_sales
    WHERE sales_team IN ({teams})""").collect()
rows = [(r.order_number, i, r.sales_team, CHANNELS[r.sales_team], r.order_state, r.order_date, r.date_order_madrid,
         r.sku, (r.product_title or "")[:300], r.qty, r.price_unit, r.price_subtotal, r.price_total, r.order_amount_total)
        for i, r in enumerate(raw)]
if not rows:
    # пустая выборка при живом источнике — не «продаж нет», а поломка чтения: реплику не трогаем
    raise RuntimeError("raw_odoo_sales не отдала ни одной строки Wallapop и сайта — реплику не переписываю")
with pg, pg.cursor() as cur:
    # срез переписывается целиком: строк сотни, а у строки Odoo нет своего id — сравнивать по ключу нечем
    cur.execute("DELETE FROM kabinet_data.raw_odoo_channel_sales")
    psycopg2.extras.execute_values(cur, """
        INSERT INTO kabinet_data.raw_odoo_channel_sales
            (order_number, line_no, sales_team, marketplace, order_state, order_date, date_order_madrid, sku,
             product_title, qty, price_unit, price_subtotal, price_total, order_amount_total)
        VALUES %s""", rows, page_size=1000)
pg.close()
by_team = {}
for r in raw:
    by_team[(r.sales_team, r.order_state)] = by_team.get((r.sales_team, r.order_state), 0) + 1
print(f"✅ реплика: {len(rows)} строк — " + ", ".join(f"{k[0]}/{k[1]} {v}" for k, v in sorted(by_team.items())))

# COMMAND ----------

# DBTITLE 1,2. Экономика WP_ES и WEB_ES → kabinet_data.economics_summary
import re
from collections import defaultdict
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

_wc = WorkspaceClient()
_cred = _wc.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres",
                      user="v.tereshyn@dniprom.com", password=_cred.token, sslmode="require")
cur = pg.cursor()

def norm_sku(s):
    """Ключ строки экономики: код как есть, без хвоста «_» и с потерянным ведущим нулём — то же, что у Mirakl."""
    s = re.sub(r"_+$", "", str(s).strip())
    return re.sub(r"^(\d{7})(?!\d)", r"0\1", s)

# Экономика остальных каналов начинается с первого дня Data Kiosk (15.05.2026). Раньше него Wallapop и сайт не
# пишем: иначе годовой период показал бы выручку сайта за 2025 рядом с пустым Amazon, и доли каналов врали бы
cur.execute("SELECT min(sales_date) FROM kabinet_data.economics_summary WHERE marketplace = 'ES'")
START = cur.fetchone()[0]

cur.execute("""
    SELECT order_number, marketplace, order_date, sku, product_title, qty::float, price_subtotal::float
    FROM kabinet_data.raw_odoo_channel_sales
    WHERE order_state = 'sale' AND order_date >= %s""", (START,))
lines = cur.fetchall()

# скидка WooCommerce по заказу → товарам заказа пропорционально их сумме без НДС (так её разносит и витрина Power BI)
disc, base = defaultdict(float), defaultdict(float)
for o, mk, d, sku, title, qty, sub in lines:
    if sku == "woo_discount":
        disc[o] += -(sub or 0.0)
    elif sku:
        base[o] += sub or 0.0

agg = defaultdict(lambda: {"units": 0.0, "rev": 0.0, "disc": 0.0, "name": "", "lines": []})
for o, mk, d, sku, title, qty, sub in lines:
    if not sku or sku == "woo_discount":
        continue
    k = (d, mk, norm_sku(sku))
    a = agg[k]
    a["units"] += qty or 0.0
    a["rev"] += sub or 0.0
    if base[o] > 0:
        a["disc"] += disc[o] * (sub or 0.0) / base[o]
    a["lines"].append((sku, qty or 0.0))
    if not a["name"]:
        a["name"] = re.sub(r"^\[[^\]]*\]\s*", "", title or "")[:100]

# себестоимость — общая цепочка, по каждой строке заказа; нет цены хоть у одной — у ключа её нет
_raw = sorted({s for a in agg.values() for s, _ in a["lines"]})
cur.execute("""SELECT s.raw, c.cogs, c.cogs_source FROM unnest(%s::text[]) AS s(raw)
               LEFT JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.sku_cogs_key(s.raw)""", (_raw,))
cogs_of = {r[0]: (float(r[1]), r[2]) if r[1] is not None else None for r in cur.fetchall()}

out = []
for (d, mk, ns), a in agg.items():
    units = int(round(a["units"]))
    parts = [(cogs_of.get(s), q) for s, q in a["lines"]]
    cogs = src = None
    if a["units"] > 0 and all(c is not None for c, _ in parts):
        cogs = round(sum(c[0] * q for c, q in parts) / a["units"], 4)
        src = "odoo" if any(c[1] == "odoo" for c, _ in parts) else "amazon"
    rev = round(a["rev"], 2)
    net = round(a["rev"] - a["disc"], 2)
    out.append((d, mk, ns, a["name"], units, 0, units, rev, rev, 0.0, net,
                round(net / units, 2) if units else 0.0, "EUR", cogs, None, src))

with pg:   # одна транзакция: строки WP_ES и WEB_ES принадлежат только этому загрузчику
    cur.execute("DELETE FROM kabinet_data.economics_summary WHERE marketplace = ANY(%s)", (list(CHANNELS.values()),))
    n_del = cur.rowcount
    psycopg2.extras.execute_values(cur, """
        INSERT INTO kabinet_data.economics_summary
            (sales_date, marketplace, norm_sku, product_name, units_ordered, units_refunded, net_units_sold,
             ordered_product_sales, net_product_sales, total_fees, net_proceeds_total, net_proceeds_per_unit,
             currency_code, updated_at, cogs, commission_fee, cogs_source)
        VALUES %s""", out,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s)", page_size=500)
pg.close()
_by = defaultdict(lambda: [0, 0.0])
for r in out:
    _by[r[1]][0] += r[4]; _by[r[1]][1] += r[7]
print(f"✅ экономика: удалено {n_del}, записано {len(out)} строк с {START}: "
      + ", ".join(f"{k} {v[0]} шт / {v[1]:.2f} €" for k, v in sorted(_by.items()))
      + f"; без себестоимости {sum(1 for r in out if r[13] is None)}")

# COMMAND ----------

# DBTITLE 1,3. Пульс
# Последней операцией, безусловно: «ячейки доработали до конца», а не «всё внутри было без замечаний»
import psycopg2
from databricks.sdk import WorkspaceClient
_cred = WorkspaceClient().postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
_pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                       port=5432, dbname="databricks_postgres",
                       user="v.tereshyn@dniprom.com", password=_cred.token, sslmode="require")
with _pg, _pg.cursor() as _c:
    _c.execute("""
        INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
        VALUES ('Kabinet - Odoo Channels Loader', now(), 'Wallapop и сайт из Odoo', 26)
        ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""")
_pg.close()
print("💓 Kabinet - Odoo Channels Loader")
