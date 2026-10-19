# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Config + Auth
# ═══════════════════════════════════════════════════════════════
# KABINET — RETURNS LOADER
# FBA + MFN returns, all 8 EU marketplaces.
# Incremental: looks back LOOKBACK_DAYS from last loaded date.
# Target: dnipro_m.kabinet_data.raw_amazon_returns
# Credentials: secret scope amazon-sp-api (no hardcode).
# ═══════════════════════════════════════════════════════════════
import requests, gzip, io, csv, time, json
from datetime import datetime, timedelta, timezone, date as _date
import pyspark.sql.functions as F
from pyspark.sql.types import *

# ─── Config ───
LOOKBACK_DAYS = 14        # Overlap window for late-arriving returns
INITIAL_DAYS = 90         # First load: 90 days of history
SP_API_EU = "https://sellingpartnerapi-eu.amazon.com"


# ── рынки Amazon — из справочника, не из кода (21.09.2026). Новая страна появляется здесь, как только заведена
#    в kabinet_data.marketplaces_new (platform AMZ, is_active, amazon_id) — с нужным флагом sync_*/monitor_listings.
#    До этого списки были зашиты в каждом ноутбуке и расходились: в трёх лежал несуществующий id Польши A1C3SOZBER6LPF.
def _amz_markets(flag_sql="TRUE"):
    """[(CC, amazon_id, legacy)], например ('GB', 'A1F83G8C2ARO7P', 'co.uk'); flag_sql — условие по колонкам справочника."""
    from databricks.sdk import WorkspaceClient as _WC
    import psycopg2 as _pg
    _w = _WC()
    _c = _pg.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432, dbname="databricks_postgres",
                     user=_w.current_user.me().user_name, sslmode="require",
                     password=_w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
    try:
        _cur = _c.cursor()
        _cur.execute(f"""SELECT upper(country_alpha2), amazon_id, lower(legacy_code) FROM kabinet_data.marketplaces_new
                         WHERE platform_short = 'AMZ' AND is_active AND amazon_id IS NOT NULL AND ({flag_sql}) ORDER BY code""")
        return [tuple(r) for r in _cur.fetchall()]
    finally:
        _c.close()
MARKETPLACES = {cc: mid for cc, mid, _lg in _amz_markets("sync_economics")}   # было 8 зашитых, PL с неверным id
print(f"рынки из справочника: {list(MARKETPLACES)}")

# ─── Auth (from secret scope, per project conventions) ───
LWA_APP_ID    = dbutils.secrets.get("amazon-sp-api", "lwa-app-id")
LWA_SECRET    = dbutils.secrets.get("amazon-sp-api", "lwa-client-secret")
REFRESH_TOKEN = dbutils.secrets.get("amazon-sp-api", "refresh-token")

_token_cache = {"token": None, "expires": 0}

def get_access_token():
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires"] - 60:
        return _token_cache["token"]
    r = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": LWA_APP_ID,
        "client_secret": LWA_SECRET,
    })
    r.raise_for_status()
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]

print("✅ Config loaded, 8 marketplaces")

# COMMAND ----------

# DBTITLE 1,DDL + Incremental bounds
# ─── DDL: unified returns table ───
spark.sql("""
    CREATE TABLE IF NOT EXISTS dnipro_m.kabinet_data.raw_amazon_returns (
        order_id            STRING NOT NULL,
        marketplace         STRING NOT NULL,
        return_date         DATE,
        order_date          DATE,
        sku                 STRING,
        asin                STRING,
        product_name        STRING,
        quantity            INT,
        return_reason       STRING,
        return_status       STRING,
        disposition         STRING,
        fulfillment_type    STRING COMMENT 'FBA or MFN',
        a_to_z_claim        STRING,
        is_prime            STRING,
        label_type          STRING,
        refunded_amount     DOUBLE,
        currency_code       STRING,
        customer_comments   STRING,
        raw_source          STRING COMMENT 'report type used',
        loaded_at           TIMESTAMP
    )
    USING DELTA
    COMMENT 'Unified FBA+MFN returns, all EU marketplaces. Loader: Kabinet - Returns Loader.'
""")
print("✅ dnipro_m.kabinet_data.raw_amazon_returns ready")

# ─── Determine incremental bounds ───
try:
    last_loaded = spark.sql("""
        SELECT MAX(return_date) FROM dnipro_m.kabinet_data.raw_amazon_returns
    """).collect()[0][0]
except:
    last_loaded = None

if last_loaded:
    start_date = last_loaded - timedelta(days=LOOKBACK_DAYS)
    print(f"🔄 Incremental: from {start_date} (last_loaded={last_loaded}, lookback={LOOKBACK_DAYS}d)")
else:
    start_date = _date.today() - timedelta(days=INITIAL_DAYS)
    print(f"🆕 Initial load: from {start_date} ({INITIAL_DAYS} days)")

end_date = _date.today()
print(f"   Range: {start_date} → {end_date}")

# COMMAND ----------

# DBTITLE 1,Fetch reports (FBA + MFN, all marketplaces)
# ─── Report fetching engine ───

def request_report(report_type, marketplace_id, start, end):
    """Request a report and return report_id."""
    # createReport — одна квота на аккаунт (см. CLAUDE.md): на 429 ждём по минуте, до 40 минут,
    # потом падаем с маркером [QUOTA_429] — сторож заведёт инцидент квоты, а не поломки
    for attempt in range(40):
        token = get_access_token()
        r = requests.post(
            f"{SP_API_EU}/reports/2021-06-30/reports",
            headers={"x-amz-access-token": token, "Content-Type": "application/json"},
            json={
                "reportType": report_type,
                "marketplaceIds": [marketplace_id],
                "dataStartTime": f"{start}T00:00:00Z",
                "dataEndTime": f"{end}T23:59:59Z",
            }
        )
        if r.status_code == 429:
            time.sleep(60); continue
        r.raise_for_status()
        return r.json()["reportId"]
    raise RuntimeError(f"[QUOTA_429] 40 попыток по 60 с, всё 429: createReport {report_type} {marketplace_id}")


def wait_for_report(report_id, max_wait=300):
    """Poll until DONE, return document_id or None."""
    token = get_access_token()
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = requests.get(
            f"{SP_API_EU}/reports/2021-06-30/reports/{report_id}",
            headers={"x-amz-access-token": token}
        )
        r.raise_for_status()
        info = r.json()
        status = info["processingStatus"]
        if status == "DONE":
            return info["reportDocumentId"]
        if status in ("CANCELLED", "FATAL"):
            return None
        time.sleep(15)
    return None


def download_report(doc_id):
    """Download and decompress report content."""
    token = get_access_token()
    r = requests.get(
        f"{SP_API_EU}/reports/2021-06-30/documents/{doc_id}",
        headers={"x-amz-access-token": token}
    )
    r.raise_for_status()
    doc = r.json()
    r2 = requests.get(doc["url"])
    r2.raise_for_status()
    if doc.get("compressionAlgorithm") == "GZIP":
        return gzip.decompress(r2.content).decode("utf-8", errors="replace")
    return r2.content.decode("utf-8", errors="replace")


def parse_fba_returns(content, mp_code):
    """Parse FBA returns TSV into list of dicts."""
    rows = []
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for r in reader:
        rows.append({
            "order_id": r.get("order-id", "").strip(),
            "marketplace": mp_code,
            "return_date": r.get("return-date", "")[:10] or None,
            "order_date": None,
            "sku": r.get("sku"),
            "asin": r.get("asin"),
            "product_name": (r.get("product-name") or "")[:200],
            "quantity": int(r.get("quantity") or 0),
            "return_reason": r.get("reason"),
            "return_status": r.get("status"),
            "disposition": r.get("detailed-disposition"),
            "fulfillment_type": "FBA",
            "a_to_z_claim": None,
            "is_prime": None,
            "label_type": None,
            "refunded_amount": None,
            "currency_code": None,
            "customer_comments": (r.get("customer-comments") or "")[:500],
            "raw_source": "GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA",
        })
    return rows


def parse_mfn_returns(content, mp_code):
    """Parse MFN returns TSV into list of dicts."""
    rows = []
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for r in reader:
        # Parse date formats like "05-Aug-2026" or "2026-08-05"
        order_dt = r.get("Order date", "").strip()
        return_dt = r.get("Return request date", "").strip()
        try:
            order_dt = datetime.strptime(order_dt, "%d-%b-%Y").strftime("%Y-%m-%d") if order_dt and "-" in order_dt and len(order_dt) > 8 else order_dt[:10]
        except:
            order_dt = order_dt[:10] if order_dt else None
        try:
            return_dt = datetime.strptime(return_dt, "%d-%b-%Y").strftime("%Y-%m-%d") if return_dt and "-" in return_dt and len(return_dt) > 8 else return_dt[:10]
        except:
            return_dt = return_dt[:10] if return_dt else None

        refund = r.get("Refund amount") or r.get("Refunded Amount")
        try:
            refund = float(refund) if refund else None
        except:
            refund = None

        rows.append({
            "order_id": r.get("Order ID", "").strip(),
            "marketplace": mp_code,
            "return_date": return_dt,
            "order_date": order_dt,
            "sku": r.get("Merchant SKU") or r.get("merchant-sku"),
            "asin": r.get("ASIN"),
            "product_name": (r.get("Item Name") or r.get("product-name") or "")[:200],
            "quantity": int(r.get("Quantity") or r.get("quantity") or 1),
            "return_reason": r.get("Return reason") or r.get("Reason"),
            "return_status": r.get("Return request status"),
            "disposition": r.get("Resolution"),
            "fulfillment_type": "MFN",
            "a_to_z_claim": r.get("A-to-Z Claim") or r.get("A-to-z Claim"),
            "is_prime": r.get("Is prime") or r.get("Is Prime"),
            "label_type": r.get("Label type"),
            "refunded_amount": refund,
            "currency_code": r.get("Currency code"),
            "customer_comments": None,
            "raw_source": "GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE",
        })
    return rows


# ─── Main fetch loop ───
# FBA Pan-EU: один запрос (отчёт возвращает все EU-возвраты независимо от MP в запросе).
# MFN: по-маркетплейсно (продавец выполняет сам, привязка к MP точная).
# Marketplace для FBA резолвится по orders (Cell 4).
all_returns = []

# 1️⃣ FBA — один запрос через ES (Pan-EU pool)
print("── FBA returns (Pan-EU, single request) ──")
try:
    rid = request_report("GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA",
                         MARKETPLACES["ES"], start_date, end_date)
    doc_id = wait_for_report(rid)
    if doc_id:
        content = download_report(doc_id)
        fba_rows = parse_fba_returns(content, "_UNRESOLVED_")  # MP резолвится позже
        all_returns.extend(fba_rows)
        print(f"  ✅ FBA Pan-EU: {len(fba_rows)} returns")
    else:
        print("  ⚠️ FBA: report not ready")
except Exception as e:
    print(f"  ❌ FBA: {str(e)[:100]}")

# 2️⃣ MFN — per-marketplace
print("\n── MFN returns (per marketplace) ──")
for mp_code, mp_id in MARKETPLACES.items():
    try:
        rid = request_report("GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE",
                             mp_id, start_date, end_date)
        doc_id = wait_for_report(rid)
        if doc_id:
            content = download_report(doc_id)
            rows = parse_mfn_returns(content, mp_code)
            all_returns.extend(rows)
            if rows:
                print(f"  ✅ MFN/{mp_code}: {len(rows)} returns")
            else:
                print(f"  ─ MFN/{mp_code}: 0 (empty report)")
        else:
            print(f"  ⚠️ MFN/{mp_code}: report not ready")
    except Exception as e:
        print(f"  ❌ MFN/{mp_code}: {str(e)[:80]}")
    time.sleep(2)

print(f"\n── Total fetched: {len(all_returns)} return records")

# COMMAND ----------

# DBTITLE 1,MERGE into UC + stats
# ─── Resolve marketplace for FBA returns + MERGE ───
# FBA Pan-EU возвращает все EU-возвраты без привязки к MP.
# Определяем MP по order_id из raw_amazon_seller_central_get_orders.

# Reverse map: marketplace_id -> code
MP_ID_TO_CODE = {v: k for k, v in MARKETPLACES.items()}

if not all_returns:
    raise RuntimeError("❌ 0 returns fetched across all marketplaces — job forced to FAIL.")
else:
    now_ts = datetime.now(timezone.utc).isoformat()

    # Build DataFrame
    spark_rows = []
    for r in all_returns:
        if not r["order_id"]:
            continue
        spark_rows.append((
            r["order_id"], r["marketplace"], r["return_date"], r["order_date"],
            r["sku"], r["asin"], r["product_name"], r["quantity"],
            r["return_reason"], r["return_status"], r["disposition"],
            r["fulfillment_type"], r["a_to_z_claim"], r["is_prime"],
            r["label_type"], r["refunded_amount"], r["currency_code"],
            r["customer_comments"], r["raw_source"], now_ts
        ))

    schema = StructType([
        StructField("order_id", StringType(), False),
        StructField("marketplace", StringType(), False),
        StructField("return_date", StringType()),
        StructField("order_date", StringType()),
        StructField("sku", StringType()),
        StructField("asin", StringType()),
        StructField("product_name", StringType()),
        StructField("quantity", IntegerType()),
        StructField("return_reason", StringType()),
        StructField("return_status", StringType()),
        StructField("disposition", StringType()),
        StructField("fulfillment_type", StringType()),
        StructField("a_to_z_claim", StringType()),
        StructField("is_prime", StringType()),
        StructField("label_type", StringType()),
        StructField("refunded_amount", DoubleType()),
        StructField("currency_code", StringType()),
        StructField("customer_comments", StringType()),
        StructField("raw_source", StringType()),
        StructField("loaded_at", StringType()),
    ])

    df = spark.createDataFrame(spark_rows, schema=schema)
    df = (df
        .withColumn("return_date", F.to_date("return_date"))
        .withColumn("order_date", F.to_date("order_date"))
        .withColumn("loaded_at", F.to_timestamp("loaded_at"))
    )

    # ── Resolve marketplace for FBA (_UNRESOLVED_) via orders table ──
    unresolved = df.filter(F.col("marketplace") == "_UNRESOLVED_")
    resolved_already = df.filter(F.col("marketplace") != "_UNRESOLVED_")

    if unresolved.count() > 0:
        orders_mp = spark.sql("""
            SELECT DISTINCT amazon_order_id, marketplace_id
            FROM dnipro_m.dnipro_m.raw_amazon_seller_central_get_orders
        """).withColumnRenamed("amazon_order_id", "_oid")

        # Map marketplace_id to code
        mp_mapping = spark.createDataFrame(
            [(mid, code) for mid, code in MP_ID_TO_CODE.items()],
            ["marketplace_id", "mp_code"]
        )
        orders_mp = orders_mp.join(mp_mapping, "marketplace_id", "left").select("_oid", "mp_code")

        # Join
        unresolved_joined = (unresolved
            .join(orders_mp, unresolved["order_id"] == orders_mp["_oid"], "left")
            .withColumn("marketplace",
                        F.coalesce(F.col("mp_code"), F.lit("UNKNOWN")))
            .drop("_oid", "mp_code")
        )
        df = resolved_already.unionByName(unresolved_joined)
        resolved_cnt = unresolved_joined.filter(F.col("marketplace") != "UNKNOWN").count()
        unknown_cnt = unresolved_joined.filter(F.col("marketplace") == "UNKNOWN").count()
        print(f"🔍 FBA marketplace resolved: {resolved_cnt} OK, {unknown_cnt} UNKNOWN")
    else:
        df = resolved_already

    # ── Drop UNKNOWN (orders not in our system) ──
    df = df.filter(F.col("marketplace") != "UNKNOWN")

    # ── Дедупликация: MERGE требует уникальности по ключу (order_id, sku, fulfillment_type) ──
    from pyspark.sql.window import Window
    dedup_w = Window.partitionBy("order_id", "sku", "fulfillment_type").orderBy(F.col("return_date").desc())
    df = (df
        .withColumn("_rn", F.row_number().over(dedup_w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
    df.createOrReplaceTempView("_returns_staging")

    # ── MERGE (dedup by order_id + sku + fulfillment_type) ──
    # Не включаем marketplace в ключ: FBA Pan-EU может резолвиться иначе.
    spark.sql("""
        MERGE INTO dnipro_m.kabinet_data.raw_amazon_returns t
        USING _returns_staging s
        ON t.order_id = s.order_id
            AND COALESCE(t.sku, '') = COALESCE(s.sku, '')
            AND t.fulfillment_type = s.fulfillment_type
        WHEN MATCHED THEN UPDATE SET
            marketplace=s.marketplace, return_date=s.return_date, order_date=s.order_date,
            asin=s.asin, product_name=s.product_name, quantity=s.quantity,
            return_reason=s.return_reason, return_status=s.return_status, disposition=s.disposition,
            a_to_z_claim=s.a_to_z_claim, is_prime=s.is_prime, label_type=s.label_type,
            refunded_amount=s.refunded_amount, currency_code=s.currency_code,
            customer_comments=s.customer_comments, raw_source=s.raw_source, loaded_at=s.loaded_at
        WHEN NOT MATCHED THEN INSERT
            (order_id, marketplace, return_date, order_date, sku, asin, product_name, quantity,
             return_reason, return_status, disposition, fulfillment_type, a_to_z_claim, is_prime,
             label_type, refunded_amount, currency_code, customer_comments, raw_source, loaded_at)
            VALUES (s.order_id, s.marketplace, s.return_date, s.order_date, s.sku, s.asin, s.product_name, s.quantity,
             s.return_reason, s.return_status, s.disposition, s.fulfillment_type, s.a_to_z_claim, s.is_prime,
             s.label_type, s.refunded_amount, s.currency_code, s.customer_comments, s.raw_source, s.loaded_at)
    """)

    # Stats
    final = spark.sql("""
        SELECT marketplace, fulfillment_type, COUNT(*) as cnt,
               MIN(return_date) as min_dt, MAX(return_date) as max_dt
        FROM dnipro_m.kabinet_data.raw_amazon_returns
        GROUP BY 1, 2 ORDER BY 1, 2
    """)
    total = spark.sql("SELECT COUNT(*) FROM dnipro_m.kabinet_data.raw_amazon_returns").collect()[0][0]
    print(f"✅ Loaded {total} returns (deduped, marketplace resolved)")
    print(f"\n── Table stats:")
    display(final)

# COMMAND ----------

# DBTITLE 1,Sync to Lakebase + System Pulse
# ═══════════════════════════════════════════════════════════════
# Sync raw_amazon_returns → Lakebase (full overwrite, ~100 rows)
# Дашборд CM Dashboard читает Lakebase — без этого шага возвраты не видны.
# ═══════════════════════════════════════════════════════════════
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg_conn = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
    port=5432, dbname="databricks_postgres",
    user="v.tereshyn@dniprom.com", password=cred.token, sslmode="require")
pg_cur = pg_conn.cursor()

# Read all returns from UC
returns_df = spark.sql("""
    SELECT order_id, marketplace, return_date, order_date, sku, asin,
           product_name, quantity, return_reason, return_status,
           disposition, fulfillment_type, a_to_z_claim, is_prime,
           label_type, refunded_amount, currency_code, customer_comments,
           raw_source, loaded_at
    FROM dnipro_m.kabinet_data.raw_amazon_returns
""").collect()

# Full overwrite (TRUNCATE + INSERT) — volume is small
pg_cur.execute("TRUNCATE TABLE kabinet_data.raw_amazon_returns")

if returns_df:
    rows = [
        (r["order_id"], r["marketplace"], r["return_date"], r["order_date"],
         r["sku"], r["asin"], r["product_name"], r["quantity"],
         r["return_reason"], r["return_status"], r["disposition"],
         r["fulfillment_type"], r["a_to_z_claim"], r["is_prime"],
         r["label_type"], r["refunded_amount"], r["currency_code"],
         r["customer_comments"], r["raw_source"], r["loaded_at"])
        for r in returns_df
    ]
    psycopg2.extras.execute_values(pg_cur, """
        INSERT INTO kabinet_data.raw_amazon_returns
            (order_id, marketplace, return_date, order_date, sku, asin,
             product_name, quantity, return_reason, return_status,
             disposition, fulfillment_type, a_to_z_claim, is_prime,
             label_type, refunded_amount, currency_code, customer_comments,
             raw_source, loaded_at)
        VALUES %s
    """, rows, page_size=500)
    pg_conn.commit()
    print(f"\u2705 Lakebase sync: {len(rows)} returns written to kabinet_data.raw_amazon_returns")
else:
    pg_conn.commit()
    print("\u26a0\ufe0f No returns to sync")

# ─── SYSTEM PULSE: безусловная метка завершения ───
pg_cur.execute("""
    INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
    VALUES ('Kabinet - Returns Loader', now(), %s)
    ON CONFLICT (job_name) DO UPDATE SET
        last_success_at = now(), note = EXCLUDED.note
""", (f"{len(rows) if returns_df else 0} returns synced",))
pg_conn.commit()
print(f"✅ System pulse записан")

pg_conn.close()