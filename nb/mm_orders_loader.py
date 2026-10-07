# Databricks notebook source
# DBTITLE 1,ManoMano Orders Loader (ES/FR)
# Kabinet - MM Orders Loader
# Загружает заказы ManoMano (ES/FR) → UC (MERGE) → Lakebase (UPSERT)
# По образцу LM Orders Loader. Ключи только из secrets.

import os, json, time, datetime
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import psycopg2

from databricks.sdk import WorkspaceClient
import databricks.sdk
from packaging.version import Version
assert Version(databricks.sdk.version.__version__) >= Version("0.118.0")

# ─── Config from secrets ───
API_KEY = dbutils.secrets.get("manomano", "api-key")
THIRDPARTY_NAME = dbutils.secrets.get("manomano", "thirdparty-name")
CONTRACT_ES = dbutils.secrets.get("manomano", "contract_id_es")
CONTRACT_FR = dbutils.secrets.get("manomano", "contract_id_fr")

CONTRACTS = {"ES": CONTRACT_ES, "FR": CONTRACT_FR}
BASE_URL = "https://partnersapi.manomano.com"
MAX_PAGES = 500
REQUEST_TIMEOUT = 20

# ─── HTTP session with retries ───
def make_session():
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["GET"], raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

# ─── Fetch all orders ───
def fetch_manomano_orders(session):
    headers = {"x-api-key": API_KEY, "Accept": "application/json",
               "x-thirdparty-name": THIRDPARTY_NAME}
    orders_list = []
    lines_list = []

    for country, contract_id in CONTRACTS.items():
        page = 1
        print(f"🔄 [ManoMano {country}] Fetching orders...")
        while page <= MAX_PAGES:
            params = {"seller_contract_id": contract_id, "limit": 50, "page": page}
            try:
                res = session.get(f"{BASE_URL}/orders/v1/orders",
                                  headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            except Exception as e:
                print(f"  ⚠️ Network error p.{page}: {e}")
                time.sleep(5); page += 1; continue

            if res.status_code == 429:
                wait = int(res.headers.get("Retry-After", 60))
                print(f"  ⏳ 429, waiting {wait}s"); time.sleep(wait); continue
            if res.status_code != 200:
                print(f"  ❌ {res.status_code}: {res.text[:200]}")
                break

            data = res.json()
            content = data.get("content", [])
            if not content:
                break

            for order in content:
                order_ref = order.get("order_reference", "")
                created_at = order.get("created_at", "")
                status = order.get("status", "")
                is_mmf = order.get("is_mmf", False)
                shipping = (order.get("addresses") or {}).get("shipping") or {}

                # ─── Discounts (amount/currency dicts) ───
                def _amt(v):
                    if isinstance(v, dict): return float(v.get("amount", 0) or 0)
                    if isinstance(v, (int, float)): return float(v)
                    try: return float(str(v).replace(",", "."))
                    except: return 0.0
                mm_disc = round(_amt(order.get("manomano_discount")), 2)
                sell_disc = round(_amt(order.get("seller_discount")), 2)
                ship_disc = round(_amt(order.get("shipping_discount")), 2)
                tot_disc = round(_amt(order.get("total_discount")), 2)
                # ─── VAT block ───
                vat_block = order.get("vat") or {}
                is_b2b = bool(vat_block.get("is_b2b", False))
                vat_liability = (vat_block.get("vat_liability") or "")[:50]
                intraco_vat = (vat_block.get("intraco_vat_number") or "")[:50]
                invoice_fiscal = (vat_block.get("invoice_fiscal_number") or "")[:50]
                is_prof = bool(order.get("is_professional", False))  # deprecated, use is_b2b

                orders_list.append({
                    "order_ref": order_ref, "country": country,
                    "created_at": created_at, "status": status,
                    "is_mmf": is_mmf,
                    "destination_city": shipping.get("city", ""),
                    "zip_code": shipping.get("zipcode", ""),
                    "manomano_discount": mm_disc,
                    "seller_discount": sell_disc,
                    "shipping_discount": ship_disc,
                    "total_discount": tot_disc,
                    "is_b2b": is_b2b,
                    "vat_liability": vat_liability,
                    "intraco_vat_number": intraco_vat,
                    "is_professional": is_prof,
                    "invoice_fiscal_number": invoice_fiscal,
                })

                for p in order.get("products", []):
                    qty = int(p.get("quantity", 1) or 1)
                    # MM prices are objects: {"amount": 58.46, "currency": "EUR"}
                    def _amt(v):
                        if isinstance(v, dict): return float(v.get("amount", 0) or 0)
                        if isinstance(v, (int, float)): return float(v)
                        try: return float(str(v).replace(",", "."))
                        except: return 0.0
                    unit_price = _amt(p.get("price"))
                    total_price = _amt(p.get("total_price"))
                    if total_price == 0 and qty > 0:
                        total_price = round(qty * unit_price, 2)
                    # --- ex-VAT, VAT rate, shipping, carrier прямо из API ---
                    unit_price_ex_vat = round(_amt(p.get("price_excluding_vat")), 2)
                    raw_vat = p.get("vat_rate")
                    vat_rate = float(raw_vat) if raw_vat is not None else ({"ES": 21.0, "FR": 20.0}.get(country, 21.0))
                    shipping_price = round(_amt(p.get("shipping_price")), 2)
                    carrier = (p.get("carrier") or "")[:100]
                    lines_list.append({
                        "order_ref": order_ref, "country": country,
                        "sku": p.get("seller_sku", "N/A"),
                        "title": (p.get("product_title") or p.get("title", ""))[:500],
                        "quantity": qty,
                        "unit_price": round(unit_price, 2),
                        "total_price": round(total_price, 2),
                        "unit_price_ex_vat": unit_price_ex_vat,
                        "vat_rate": vat_rate,
                        "shipping_price": shipping_price,
                        "carrier": carrier,
                        "order_date": created_at[:10] if created_at else None,
                        "order_status": status,
                    })

            pagination = data.get("pagination", {})
            total_pages = pagination.get("pages", 1)
            print(f"  p.{page}/{total_pages} | orders={len(orders_list)} lines={len(lines_list)}")
            if page >= total_pages:
                break
            page += 1

    return orders_list, lines_list

# ─── Run ───
session = make_session()
orders, lines = fetch_manomano_orders(session)
print(f"\n✅ Fetched: {len(orders)} orders, {len(lines)} lines")

# ─── Raw preview (первые 2 заказа) ───
if orders:
    print("\n═══ RAW PREVIEW (orders[:2]) ═══")
    for i, o in enumerate(orders[:2]):
        print(f"\n── Order {i+1}: {o['order_ref']} ({o['country']}) ──")
        print(f"  status={o['status']}, is_mmf={o['is_mmf']}, is_prof={o['is_professional']}, is_b2b={o['is_b2b']}")
        print(f"  discounts: mm={o['manomano_discount']}, seller={o['seller_discount']}, ship={o['shipping_discount']}, total={o['total_discount']}")
        print(f"  vat: liability={o['vat_liability']}, intraco={o['intraco_vat_number']}, fiscal={o['invoice_fiscal_number']}")
if lines:
    print(f"\n═══ RAW PREVIEW (lines[:3]) ═══")
    for i, l in enumerate(lines[:3]):
        print(f"  {l['order_ref']} | {l['sku']} | qty={l['quantity']} | €{l['unit_price']} | ex_vat=€{l['unit_price_ex_vat']} | ship=€{l['shipping_price']}")

# COMMAND ----------

# DBTITLE 1,MERGE into UC + Sync to Lakebase
# ─── Cell 2: MERGE в UC + Sync в Lakebase ───
from pyspark.sql import Row
from pyspark.sql.functions import current_timestamp, lit

now_ts = datetime.datetime.now(ZoneInfo("Europe/Kyiv"))

# ─── UC MERGE: orders ───
if orders:
    df_orders = spark.createDataFrame([Row(**o) for o in orders])
    df_orders = df_orders.withColumn("loaded_at", current_timestamp())
    df_orders.createOrReplaceTempView("_mm_orders_stage")
    spark.sql("""
        MERGE INTO dnipro_m.kabinet_data.raw_mm_orders t
        USING _mm_orders_stage s ON t.order_ref = s.order_ref
        WHEN MATCHED THEN UPDATE SET
            status = s.status, is_mmf = s.is_mmf,
            destination_city = s.destination_city, zip_code = s.zip_code,
            manomano_discount = s.manomano_discount, seller_discount = s.seller_discount,
            shipping_discount = s.shipping_discount, total_discount = s.total_discount,
            is_b2b = s.is_b2b, vat_liability = s.vat_liability,
            intraco_vat_number = s.intraco_vat_number, is_professional = s.is_professional,
            invoice_fiscal_number = s.invoice_fiscal_number, loaded_at = s.loaded_at
        WHEN NOT MATCHED THEN INSERT
            (order_ref, country, created_at, status, is_mmf, destination_city, zip_code,
             manomano_discount, seller_discount, shipping_discount, total_discount,
             is_b2b, vat_liability, intraco_vat_number, is_professional, invoice_fiscal_number, loaded_at)
            VALUES (s.order_ref, s.country, s.created_at, s.status, s.is_mmf, s.destination_city, s.zip_code,
             s.manomano_discount, s.seller_discount, s.shipping_discount, s.total_discount,
             s.is_b2b, s.vat_liability, s.intraco_vat_number, s.is_professional, s.invoice_fiscal_number, s.loaded_at)
    """)
    print(f"✅ UC raw_mm_orders: MERGED {len(orders)} rows")

# ─── UC MERGE: order_lines ───
if lines:
    df_lines = spark.createDataFrame([Row(**l) for l in lines])
    df_lines = df_lines.withColumn("loaded_at", current_timestamp())
    df_lines.createOrReplaceTempView("_mm_lines_stage")
    spark.sql("""
        MERGE INTO dnipro_m.kabinet_data.raw_mm_order_lines t
        USING _mm_lines_stage s
            ON t.order_ref = s.order_ref AND t.sku = s.sku AND t.country = s.country
        WHEN MATCHED THEN UPDATE SET
            title = s.title, quantity = s.quantity,
            unit_price = s.unit_price, total_price = s.total_price,
            unit_price_ex_vat = s.unit_price_ex_vat, vat_rate = s.vat_rate,
            shipping_price = s.shipping_price, carrier = s.carrier,
            order_date = CAST(s.order_date AS DATE), order_status = s.order_status,
            loaded_at = s.loaded_at
        WHEN NOT MATCHED THEN INSERT (
            order_ref, sku, country, title, quantity,
            unit_price, total_price, unit_price_ex_vat, vat_rate,
            shipping_price, carrier, order_date, order_status, loaded_at)
        VALUES (
            s.order_ref, s.sku, s.country, s.title, s.quantity,
            s.unit_price, s.total_price, s.unit_price_ex_vat, s.vat_rate,
            s.shipping_price, s.carrier, CAST(s.order_date AS DATE), s.order_status, s.loaded_at)
    """)
    print(f"✅ UC raw_mm_order_lines: MERGED {len(lines)} rows")

# ─── Lakebase UPSERT ───
w = WorkspaceClient()
cred = w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres",
    user="v.tereshyn@dniprom.com", password=cred.token, sslmode="require")
pg.autocommit = True
cur = pg.cursor()

# Orders upsert
for o in orders:
    cur.execute("""
        INSERT INTO kabinet_data.raw_mm_orders
            (order_ref, country, created_at, status, is_mmf, destination_city, zip_code,
             manomano_discount, seller_discount, shipping_discount, total_discount,
             is_b2b, vat_liability, intraco_vat_number, is_professional, invoice_fiscal_number)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (order_ref) DO UPDATE SET
            status = EXCLUDED.status, is_mmf = EXCLUDED.is_mmf,
            destination_city = EXCLUDED.destination_city,
            zip_code = EXCLUDED.zip_code,
            manomano_discount = EXCLUDED.manomano_discount,
            seller_discount = EXCLUDED.seller_discount,
            shipping_discount = EXCLUDED.shipping_discount,
            total_discount = EXCLUDED.total_discount,
            is_b2b = EXCLUDED.is_b2b,
            vat_liability = EXCLUDED.vat_liability,
            intraco_vat_number = EXCLUDED.intraco_vat_number,
            is_professional = EXCLUDED.is_professional,
            invoice_fiscal_number = EXCLUDED.invoice_fiscal_number,
            loaded_at = NOW()
    """, (o["order_ref"], o["country"], o["created_at"] or None,
          o["status"], o["is_mmf"], o["destination_city"], o["zip_code"],
          o.get("manomano_discount"), o.get("seller_discount"),
          o.get("shipping_discount"), o.get("total_discount"),
          o.get("is_b2b"), o.get("vat_liability"),
          o.get("intraco_vat_number"), o.get("is_professional"),
          o.get("invoice_fiscal_number")))

# Lines upsert (all fields incl. ex-VAT, carrier, shipping)
for l in lines:
    cur.execute("""
        INSERT INTO kabinet_data.raw_mm_order_lines
            (order_ref, sku, country, title, quantity, unit_price, total_price,
             unit_price_ex_vat, vat_rate, shipping_price, carrier,
             order_date, order_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (order_ref, sku, country) DO UPDATE SET
            title = EXCLUDED.title, quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price, total_price = EXCLUDED.total_price,
            unit_price_ex_vat = EXCLUDED.unit_price_ex_vat, vat_rate = EXCLUDED.vat_rate,
            shipping_price = EXCLUDED.shipping_price, carrier = EXCLUDED.carrier,
            order_date = EXCLUDED.order_date, order_status = EXCLUDED.order_status,
            loaded_at = NOW()
    """, (l["order_ref"], l["sku"], l["country"], l["title"],
          l["quantity"], l["unit_price"], l["total_price"],
          l.get("unit_price_ex_vat"), l.get("vat_rate"),
          l.get("shipping_price"), l.get("carrier"),
          l.get("order_date"), l.get("order_status")))

cur.close(); pg.close()
print(f"✅ Lakebase: {len(orders)} orders + {len(lines)} lines synced")
print(f"\n🏁 MM Orders Loader завершён: {now_ts:%Y-%m-%d %H:%M} Kyiv")

# COMMAND ----------

# DBTITLE 1,Upsert economics_summary (ex-VAT from API + commission from raw_mm_commissions)
# ─── Cell 3: Aggregate into economics_summary ───
# Idempotent by PK (sales_date, marketplace, norm_sku)
# Комиссия ManoMano — из dnipro_m.raw_mm_commissions (таблица Дарины, раз в неделю): строка на
# позицию заказа (reference + sellerSku), commissionVatExcl; REFUND идёт со знаком минус и
# уменьшает комиссию того же заказа. До 18.09.2026 комиссии здесь не было вовсе —
# net_proceeds равнялся продажам, маржа по MM была завышена на ~11 % выручки.
# Как у Leroy Merlin: комиссия площадки и есть все комиссии — total_fees = commission_fee.
import re

VAT_RATES = {"ES": 0.21, "FR": 0.20}

def normalize_sku(sku):
    s = str(sku).strip()
    s = re.sub(r'^S[0-9]+_', '', s)       # strip S2_/S3_ prefix
    s = re.sub(r'[\s-]+[A-D]$', '', s)    # strip trailing -A/-B/-C/-D
    s = re.sub(r'\s+\d+$', '', s)         # strip trailing space+digits
    return s

# Build order lookup: order_ref → (created_at, status, country)
order_map = {o["order_ref"]: o for o in orders}

# Aggregate by (date, marketplace, norm_sku)
from collections import defaultdict
agg = defaultdict(lambda: {"units": 0, "rev_ex_vat": 0.0, "product_name": "", "lines": []})

for l in lines:
    o = order_map.get(l["order_ref"])
    if not o or o["status"] == "REFUNDED":
        continue
    created = str(o.get("created_at", ""))[:10]
    if not created or created < "2020":
        continue
    country = l["country"]
    marketplace = f"MM_{country}"
    norm = normalize_sku(l["sku"])
    # Prefer API ex-VAT; fall back to calculation if missing
    price_ex = l.get("unit_price_ex_vat") or round(l["unit_price"] / (1 + VAT_RATES.get(country, 0.21)), 2)
    qty = l["quantity"]

    key = (created, marketplace, norm)
    agg[key]["units"] += qty
    agg[key]["rev_ex_vat"] += round(price_ex * qty, 2)
    agg[key]["lines"].append((str(l["sku"]), qty))   # исходный SKU — для себестоимости по цепочке Amazon
    if not agg[key]["product_name"]:
        agg[key]["product_name"] = l.get("title", "")[:60]

print(f"📊 Aggregated: {len(agg)} unique (date, marketplace, sku) combos")

# ─── Комиссии: (reference, norm_sku) → сумма commissionVatExcl по всем типам операций ───
comm_by_line = {}
for r in spark.sql("""SELECT reference, sellerSku, country, SUM(commissionVatExcl) AS c
                      FROM dnipro_m.dnipro_m.raw_mm_commissions GROUP BY 1, 2, 3""").collect():
    comm_by_line[(r.reference, normalize_sku(r.sellerSku))] = float(r.c or 0)
fees = defaultdict(float); lines_with_fee = lines_total = 0
for l in lines:
    o = order_map.get(l["order_ref"])
    if not o or o["status"] == "REFUNDED": continue
    created = str(o.get("created_at", ""))[:10]
    if not created or created < "2020": continue
    lines_total += 1
    c = comm_by_line.get((l["order_ref"], normalize_sku(l["sku"])))
    if c is None: continue
    fees[(created, f"MM_{l['country']}", normalize_sku(l["sku"]))] += round(c, 2); lines_with_fee += 1
print(f"💶 Комиссии: найдены для {lines_with_fee} из {lines_total} строк заказов, всего {sum(fees.values()):.2f} €")

# ─── COGS считается ниже, после подключения к Lakebase: общая цепочка sku_cogs_current ───
if lines_total and lines_with_fee < lines_total * 0.9:
    print(f"⚠️ у {lines_total - lines_with_fee} строк комиссии нет — таблица Дарины отстаёт (она недельная), по ним total_fees = 0")

# Upsert into economics_summary via same PG connection pattern
w2 = WorkspaceClient()
cred2 = w2.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg2 = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres",
    user="v.tereshyn@dniprom.com", password=cred2.token, sslmode="require")
pg2.autocommit = True
cur2 = pg2.cursor()
cur2.execute("ALTER TABLE kabinet_data.economics_summary ADD COLUMN IF NOT EXISTS cogs_source text")

# ─── COGS (с 05.10.2026): общая цепочка, как у Amazon, LM и Carrefour — kabinet_data.sku_cogs_current (пишет
# Economics Loader). Прежняя своя цепочка здесь не раскладывала набор на состав, а ключ normalize_sku срезает
# вариант -A…-D: набор получал цену одиночного товара, и себестоимость MM_ES в сверке с Дариной была −21 %.
# Теперь — по каждой строке заказа: исходный SKU → ключ функции базы sku_cogs_key (сперва полный код набора,
# потом приведённый правилом Amazon) × количество; у ключа строки — сумма на штуки. Нет цены хоть у одной
# строки — у ключа её нет тоже: половина себестоимости хуже пустой.
_raw = sorted({sku for v in agg.values() for sku, _ in v["lines"]})
cur2.execute("""SELECT s.raw, c.cogs, c.cogs_source
                FROM unnest(%s::text[]) AS s(raw)
                LEFT JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.sku_cogs_key(s.raw)""", (_raw,))
_cogs_by_raw = {r[0]: (float(r[1]), r[2]) if r[1] is not None else None for r in cur2.fetchall()}
for v in agg.values():
    _parts = [(_cogs_by_raw.get(sku), q) for sku, q in v["lines"]]
    if v["units"] > 0 and _parts and all(c is not None for c, _ in _parts):
        v["cogs"] = round(sum(c[0] * q for c, q in _parts) / v["units"], 4)
        v["cogs_source"] = "odoo" if any(c[1] == "odoo" for c, _ in _parts) else "amazon"
    else:
        v["cogs"], v["cogs_source"] = None, None
print(f"📦 COGS MM: есть у {sum(1 for v in agg.values() if v['cogs'] is not None)} ключей из {len(agg)} (общая цепочка sku_cogs_current)")

upsert_sql = """
    INSERT INTO kabinet_data.economics_summary
        (sales_date, marketplace, norm_sku, product_name,
         units_ordered, units_refunded, net_units_sold,
         ordered_product_sales, net_product_sales, total_fees,
         net_proceeds_total, net_proceeds_per_unit,
         currency_code, updated_at, cogs, commission_fee, cogs_source)
    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, 'EUR', NOW(), %s, %s, %s)
    ON CONFLICT (sales_date, marketplace, norm_sku) DO UPDATE SET
        units_ordered = EXCLUDED.units_ordered,
        net_units_sold = EXCLUDED.net_units_sold,
        ordered_product_sales = EXCLUDED.ordered_product_sales,
        net_product_sales = EXCLUDED.net_product_sales,
        total_fees = EXCLUDED.total_fees,
        net_proceeds_total = EXCLUDED.net_proceeds_total,
        net_proceeds_per_unit = EXCLUDED.net_proceeds_per_unit,
        commission_fee = EXCLUDED.commission_fee,
        cogs = EXCLUDED.cogs,
        cogs_source = EXCLUDED.cogs_source,
        updated_at = NOW()
"""

count = 0
for (sd, mp, sku), v in agg.items():
    units = v["units"]
    rev = v["rev_ex_vat"]
    fee = round(fees.get((sd, mp, sku), 0.0), 2)
    net = round(rev - fee, 2)
    per_unit = round(net / units, 2) if units > 0 else 0
    cur2.execute(upsert_sql, (
        sd, mp, sku, v["product_name"][:100],
        units, units, rev, rev, fee, net, per_unit, v["cogs"], fee, v["cogs_source"]
    ))
    count += 1


# ── Строки, которых в сборке больше нет, надо УДАЛИТЬ, а не оставить как есть ──
# Upsert обновляет только те ключи, что пришли. Отменённый заказ из сборки выпадает — и строка,
# записанная до отмены, остаётся навсегда. Ровно так CF_ES показывал лишние 28,09 € за 12.09:
# заказ 76283905-A отменили, фильтр по статусу его больше не пропускает, но строка от 13.09
# уже лежала в витрине и перезаписать её стало нечем. Поэтому после upsert чистим окно,
# которое этот прогон реально покрывает, от ключей, которых в сборке нет.
_days = sorted({sd for (sd, _, _) in agg})
if _days:
    _keys = [(sd, mp, sku) for (sd, mp, sku) in agg]
    cur2.execute("""
        DELETE FROM kabinet_data.economics_summary e
        WHERE e.marketplace = ANY(%s)
          AND e.sales_date BETWEEN %s AND %s
          AND NOT EXISTS (
              SELECT 1 FROM unnest(%s::date[], %s::text[], %s::text[]) AS k(d, m, s)
              WHERE k.d = e.sales_date AND k.m = e.marketplace AND k.s = e.norm_sku)
    """, (sorted({mp for (_, mp, _) in agg}), _days[0], _days[-1],
          [k[0] for k in _keys], [k[1] for k in _keys], [k[2] for k in _keys]))
    print(f"🧹 удалено строк, которых больше нет в сборке: {cur2.rowcount} "
          f"(окно {_days[0]} — {_days[-1]})")

cur2.close(); pg2.close()

print(f"✅ economics_summary: upserted {count} rows (MM, commission from raw_mm_commissions)")

# ── Heartbeat ──
try:
    from databricks.sdk import WorkspaceClient as _WC
    _cred_hb = _WC().postgres.generate_database_credential(
        endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    _pg_hb = psycopg2.connect(
        host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
        port=5432, dbname="databricks_postgres",
        user="v.tereshyn@dniprom.com", password=_cred_hb.token, sslmode="require")
    with _pg_hb.cursor() as _cur:
        _note = f"{count} econ rows, {len(orders)} orders, {len(lines)} lines"
        _cur.execute("""
            INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
            VALUES ('Kabinet - MM Orders Loader', NOW(), %s, 26)
            ON CONFLICT (job_name)
            DO UPDATE SET last_success_at = NOW(), note = EXCLUDED.note
        """, (_note,))
        _pg_hb.commit()
    _pg_hb.close()
    print("💓 Heartbeat: Kabinet - MM Orders Loader")
except Exception as e:
    print(f"⚠️ Heartbeat failed: {e}")