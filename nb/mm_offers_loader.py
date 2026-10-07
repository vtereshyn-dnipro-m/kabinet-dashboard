# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,pip install + restart (guarded)
# ═════════════════════════════════════════════════════════════════
# Kabinet — ManoMano Offers Loader
# Endpoint: GET /api/v1/offer-information/offers (Partners API)
# Контракты: ES 41477561, FR 41878496
# Квота: 200 req/h/IP — при ~4 запросах не актуальна
# ═════════════════════════════════════════════════════════════════
import subprocess, sys, importlib.metadata as _md

_need = False
try:
    import psycopg2
    from packaging.version import Version
    if Version(_md.version("databricks-sdk")) < Version("0.118.0"):
        _need = True
except (ImportError, _md.PackageNotFoundError):
    _need = True

if _need:
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                          "psycopg2-binary", "databricks-sdk>=0.118.0", "-q"])
    dbutils.library.restartPython()
else:
    print(f"⏭️ deps OK (sdk=={_md.version('databricks-sdk')})")

# COMMAND ----------

# DBTITLE 1,Setup + DDL + Config
import psycopg2, psycopg2.extras
import json, requests, time
from databricks.sdk import WorkspaceClient
from datetime import datetime, timezone, date
import pyspark.sql.functions as F
from pyspark.sql.types import *

w = WorkspaceClient()
cred = w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg_conn = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres",
    user="v.tereshyn@dniprom.com", password=cred.token, sslmode="require")
pg_cur = pg_conn.cursor()
print("✅ Lakebase connected")

# ─── DDL: Lakebase ───
pg_cur.execute("""
    CREATE TABLE IF NOT EXISTS kabinet_data.raw_mm_offers (
        sku                 TEXT NOT NULL,
        marketplace_code    TEXT NOT NULL,
        contract_id         TEXT,
        price               NUMERIC(12,2),
        stock               INTEGER DEFAULT 0,
        status              TEXT,
        errors              JSONB DEFAULT '[]',
        id_me               BIGINT,
        id_me_link          TEXT,
        carrier_grid        JSONB,
        shipping_time       JSONB,
        offer_is_online     BOOLEAN,
        frozen_price        BOOLEAN,
        frozen_retail_price BOOLEAN,
        frozen_stock        BOOLEAN,
        snapshot_date       DATE NOT NULL,
        loaded_at           TIMESTAMPTZ DEFAULT now(),
        raw                 JSONB,
        CONSTRAINT pk_raw_mm_offers PRIMARY KEY (sku, marketplace_code)
    )
""")
pg_conn.commit()
print("✅ Lakebase raw_mm_offers ready")

# ─── DDL: UC Delta ───
spark.sql("""
    CREATE TABLE IF NOT EXISTS dnipro_m.kabinet_data.raw_mm_offers (
        sku                 STRING NOT NULL,
        marketplace_code    STRING NOT NULL,
        contract_id         STRING,
        price               DECIMAL(12,2),
        stock               INT,
        status              STRING,
        errors              STRING,
        id_me               BIGINT,
        id_me_link          STRING,
        carrier_grid        STRING,
        shipping_time       STRING,
        offer_is_online     BOOLEAN,
        frozen_price        BOOLEAN,
        frozen_retail_price BOOLEAN,
        frozen_stock        BOOLEAN,
        snapshot_date       DATE,
        loaded_at           TIMESTAMP,
        raw                 STRING
    )
    COMMENT 'ManoMano offers from Partners API. PK: sku + marketplace_code (latest state).'
""")
print("✅ UC raw_mm_offers ready")

# ─── Config ───
BASE_URL = "https://partnersapi.manomano.com"
API_KEY  = dbutils.secrets.get("manomano", "api-key")
TPN      = dbutils.secrets.get("manomano", "thirdparty-name")
HEADERS  = {"x-api-key": API_KEY, "x-thirdparty-name": TPN, "Accept": "application/json"}

CONTRACTS = [
    {"marketplace_code": "MM-ES", "contract_id": "41477561"},
    {"marketplace_code": "MM-FR", "contract_id": "41878496"},
]
TODAY = date.today()
print(f"✅ Config: {len(CONTRACTS)} contracts, snapshot_date={TODAY}")

# COMMAND ----------

# DBTITLE 1,Fetch all offers (ES + FR, online + offline)
# ═════════════════════════════════════════════════════════════════
# Fetch all offers from Partners API (paginated, both contracts)
# Rate limit: 200 req/h — ~8 requests total (online+offline × 2 contracts)
# ═════════════════════════════════════════════════════════════════

def fetch_offers(contract_id, offer_online, page_size=100):
    """Fetch offers for a contract. offer_online: 'true' or 'false'."""
    offers = []
    page = 1
    while True:
        r = requests.get(
            f"{BASE_URL}/api/v1/offer-information/offers",
            headers=HEADERS,
            params={"seller_contract_id": contract_id, "offer_online": offer_online,
                    "page": page, "limit": page_size},
            timeout=60)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60))
            print(f"  ⚠️ 429 rate limit, waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        batch = data.get("content", [])
        offers += batch
        pag = data.get("pagination", {})
        total = pag.get("items", 0)
        pages = pag.get("pages", 1)
        print(f"  page {page}/{pages}: +{len(batch)} (total {total})")
        if page >= pages or not batch:
            break
        page += 1
        time.sleep(0.5)  # courtesy pause
    return offers

def fetch_all_offers(contract_id):
    """Fetch BOTH online and offline offers. Sets are disjoint (no overlap)."""
    print("  ── online offers:")
    online = fetch_offers(contract_id, "true")
    print("  ── offline offers:")
    offline = fetch_offers(contract_id, "false")
    return online + offline

def parse_offer(o, marketplace_code, contract_id):
    """Parse raw API offer dict into a flat row tuple."""
    return (
        o["sku"],
        marketplace_code,
        contract_id,
        o.get("price"),
        o.get("stock", 0),
        o.get("status"),
        json.dumps(o.get("errors", []), ensure_ascii=False),
        o.get("id_me"),
        o.get("id_me_link"),
        json.dumps(o.get("carrier_grid", {}), ensure_ascii=False),
        json.dumps(o.get("shipping_time_carrier_grid", {}), ensure_ascii=False),
        o.get("offer_is_online"),
        o.get("frozen_price"),
        o.get("frozen_retail_price"),
        o.get("frozen_stock"),
        str(TODAY),
        datetime.now(timezone.utc).isoformat(),
        json.dumps(o, ensure_ascii=False),
    )

# ─── Fetch both contracts ───
all_rows = []
for c in CONTRACTS:
    code, cid = c["marketplace_code"], c["contract_id"]
    print(f"\n{'='*50}")
    print(f"  {code} (contract {cid})")
    print(f"{'='*50}")
    raw_offers = fetch_all_offers(cid)
    rows = [parse_offer(o, code, cid) for o in raw_offers]
    all_rows += rows
    # Stats
    online = sum(1 for o in raw_offers if o.get("offer_is_online"))
    in_stock = sum(1 for o in raw_offers if (o.get("stock") or 0) > 0)
    errors = sum(1 for o in raw_offers if o.get("errors"))
    print(f"  ✅ {len(raw_offers)} offers: {online} online, {in_stock} in-stock, {errors} with errors")

print(f"\n📊 Total: {len(all_rows)} offers across {len(CONTRACTS)} contracts")

# COMMAND ----------

# DBTITLE 1,UC MERGE + Lakebase UPSERT + stock_local
# ═════════════════════════════════════════════════════════════════
# 1. UC MERGE  2. Lakebase UPSERT  3. stock_local (channel=ManoMano)
# ═════════════════════════════════════════════════════════════════

# ─── 1. UC MERGE ───
schema = StructType([
    StructField("sku", StringType(), False),
    StructField("marketplace_code", StringType(), False),
    StructField("contract_id", StringType()),
    StructField("price", StringType()),
    StructField("stock", IntegerType()),
    StructField("status", StringType()),
    StructField("errors", StringType()),
    StructField("id_me", LongType()),
    StructField("id_me_link", StringType()),
    StructField("carrier_grid", StringType()),
    StructField("shipping_time", StringType()),
    StructField("offer_is_online", BooleanType()),
    StructField("frozen_price", BooleanType()),
    StructField("frozen_retail_price", BooleanType()),
    StructField("frozen_stock", BooleanType()),
    StructField("snapshot_date", StringType()),
    StructField("loaded_at", StringType()),
    StructField("raw", StringType()),
])
df = spark.createDataFrame(all_rows, schema=schema)
df = (df
    .withColumn("price", F.col("price").cast("decimal(12,2)"))
    .withColumn("snapshot_date", F.to_date("snapshot_date"))
    .withColumn("loaded_at", F.to_timestamp("loaded_at"))
)
df.createOrReplaceTempView("_mm_offers_staging")

spark.sql("""
    MERGE INTO dnipro_m.kabinet_data.raw_mm_offers t
    USING _mm_offers_staging s ON t.sku = s.sku AND t.marketplace_code = s.marketplace_code
    WHEN MATCHED THEN UPDATE SET
        contract_id = s.contract_id, price = s.price, stock = s.stock,
        status = s.status, errors = s.errors, id_me = s.id_me,
        id_me_link = s.id_me_link, carrier_grid = s.carrier_grid,
        shipping_time = s.shipping_time, offer_is_online = s.offer_is_online,
        frozen_price = s.frozen_price, frozen_retail_price = s.frozen_retail_price,
        frozen_stock = s.frozen_stock, snapshot_date = s.snapshot_date,
        loaded_at = s.loaded_at, raw = s.raw
    WHEN NOT MATCHED THEN INSERT
        (sku, marketplace_code, contract_id, price, stock, status, errors,
         id_me, id_me_link, carrier_grid, shipping_time, offer_is_online,
         frozen_price, frozen_retail_price, frozen_stock, snapshot_date, loaded_at, raw)
        VALUES
        (s.sku, s.marketplace_code, s.contract_id, s.price, s.stock, s.status, s.errors,
         s.id_me, s.id_me_link, s.carrier_grid, s.shipping_time, s.offer_is_online,
         s.frozen_price, s.frozen_retail_price, s.frozen_stock, s.snapshot_date, s.loaded_at, s.raw)
""")
print(f"✅ UC MERGE: {len(all_rows)} offers")

# ─── 2. Lakebase UPSERT (raw_mm_offers) ───
try: pg_conn.close()
except: pass
cred = w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg_conn = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres",
    user="v.tereshyn@dniprom.com", password=cred.token, sslmode="require")
pg_cur = pg_conn.cursor()

lb_rows = [
    (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10],
     r[11], r[12], r[13], r[14], str(TODAY), r[17])
    for r in all_rows
]
psycopg2.extras.execute_values(pg_cur, """
    INSERT INTO kabinet_data.raw_mm_offers
        (sku, marketplace_code, contract_id, price, stock, status, errors,
         id_me, id_me_link, carrier_grid, shipping_time,
         offer_is_online, frozen_price, frozen_retail_price, frozen_stock,
         snapshot_date, raw)
    VALUES %s
    ON CONFLICT (sku, marketplace_code) DO UPDATE SET
        contract_id = EXCLUDED.contract_id, price = EXCLUDED.price,
        stock = EXCLUDED.stock, status = EXCLUDED.status, errors = EXCLUDED.errors,
        id_me = EXCLUDED.id_me, id_me_link = EXCLUDED.id_me_link,
        carrier_grid = EXCLUDED.carrier_grid, shipping_time = EXCLUDED.shipping_time,
        offer_is_online = EXCLUDED.offer_is_online,
        frozen_price = EXCLUDED.frozen_price, frozen_retail_price = EXCLUDED.frozen_retail_price,
        frozen_stock = EXCLUDED.frozen_stock,
        snapshot_date = EXCLUDED.snapshot_date, loaded_at = NOW(), raw = EXCLUDED.raw
""", lb_rows, page_size=200)
pg_conn.commit()
print(f"✅ Lakebase raw_mm_offers: {len(lb_rows)} upserted")

# ─── 3. stock_local (channel='ManoMano') ───
# PK: (snapshot_date, sku, location, channel)
MARKETPLACE_MAP = {"MM-ES": ("ManoMano ES", "ES"), "MM-FR": ("ManoMano FR", "FR")}

stock_rows = []
for r in all_rows:
    sku, mcode = r[0], r[1]
    stock_qty = r[4] or 0
    wh_name, wh_country = MARKETPLACE_MAP[mcode]
    stock_rows.append((
        str(TODAY), sku, None, None, wh_name, wh_country,
        "available", "ok", stock_qty, "ok",
        "manomano-offers", wh_name, "ManoMano"
    ))

pg_cur.execute("DELETE FROM kabinet_data.stock_local WHERE source='manomano-offers' AND channel='ManoMano' AND snapshot_date=CURRENT_DATE")
psycopg2.extras.execute_values(pg_cur, """
    INSERT INTO kabinet_data.stock_local
        (snapshot_date, sku, asin, product_name, warehouse_name, warehouse_country,
         availability_status, quality_status, quantity, sync_status,
         source, location, channel)
    VALUES %s
""", stock_rows, page_size=200)
pg_conn.commit()
print(f"✅ stock_local: {len(stock_rows)} rows (channel='ManoMano')")

# ─── Stats ───
for c in CONTRACTS:
    code = c["marketplace_code"]
    subset = [r for r in all_rows if r[1] == code]
    in_stock = sum(1 for r in subset if (r[4] or 0) > 0)
    online = sum(1 for r in subset if r[11])
    errs = sum(1 for r in subset if r[6] != '[]')
    print(f"\n📊 {code}: {len(subset)} offers, {in_stock} in-stock, {online} online, {errs} errors")

# COMMAND ----------

# DBTITLE 1,Heartbeat
# ═════════════════════════════════════════════════════════════════
# Heartbeat — system_pulse для Watchdog
# ═════════════════════════════════════════════════════════════════
parts = []
for c in CONTRACTS:
    code = c["marketplace_code"]
    cnt = sum(1 for r in all_rows if r[1] == code)
    stk = sum(1 for r in all_rows if r[1] == code and (r[4] or 0) > 0)
    parts.append(f"{code}={cnt}/{stk}stk")
summary = ", ".join(parts)

try:
    from databricks.sdk import WorkspaceClient
    import psycopg2
    _hb_w = WorkspaceClient()
    _hb_cred = _hb_w.postgres.generate_database_credential(
        endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    _hb_conn = psycopg2.connect(
        host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
        port=5432, dbname="databricks_postgres",
        user="v.tereshyn@dniprom.com", password=_hb_cred.token, sslmode="require")
    _hb_conn.autocommit = True
    _hb_cur = _hb_conn.cursor()
    _hb_cur.execute("""
        INSERT INTO kabinet_data.system_pulse
            (job_name, last_success_at, note, expected_interval_hours)
        VALUES ('MM Offers Loader', NOW(), %s, 26)
        ON CONFLICT (job_name) DO UPDATE
            SET last_success_at = NOW(), note = EXCLUDED.note
    """, (summary,))
    _hb_cur.close()
    _hb_conn.close()
    print(f"✅ Heartbeat: {summary}")
except Exception as _hb_e:
    print(f"⚠️ Heartbeat failed: {_hb_e}")

dbutils.notebook.exit(summary)