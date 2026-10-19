# Databricks notebook source
# MAGIC %md
# MAGIC # Kabinet - FBA Charges Loader
# MAGIC
# MAGIC Два отчёта SP-API, которых не видит Data Kiosk, в `dnipro_m.raw_*` и реплики
# MAGIC в Lakebase:
# MAGIC
# MAGIC - `GET_FBA_STORAGE_FEE_CHARGES_DATA` → `raw_amazon_fba_storage_fees` — помесячное
# MAGIC   хранение по ASIN и центру. Amazon пересчитывает месяц до середины следующего,
# MAGIC   поэтому каждый прогон перезапрашивает два последних закрытых месяца.
# MAGIC - `GET_FBA_REIMBURSEMENTS_DATA` → `raw_amazon_fba_reimbursements` — возмещения за
# MAGIC   утерю, порчу, возвраты. Каждый прогон — последние 60 дней.
# MAGIC
# MAGIC Оба отчёта приходят по всему EU-аккаунту сразу: один запрос, не по рынкам.
# MAGIC
# MAGIC Backfill — параметрами джобы: `storage_from` (YYYY-MM), `reimb_from` (YYYY-MM-DD).
# MAGIC Расписание: ежедневно. Метка `Kabinet - FBA Charges Loader` — в конце, безусловно.

# COMMAND ----------

# Ячейка 1: только зависимости и рестарт. Ничего после restartPython().
import importlib.metadata as _md
import subprocess, sys
_need = False
try:
    import psycopg2  # noqa: F401
    from packaging.version import Version
    if Version(_md.version("databricks-sdk")) < Version("0.118.0"):
        _need = True
except (ImportError, _md.PackageNotFoundError):
    _need = True
if _need:
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "psycopg2-binary", "databricks-sdk>=0.118.0", "-q"])
    dbutils.library.restartPython()  # noqa: F821
else:
    print(f"⏭️ deps OK (sdk=={_md.version('databricks-sdk')})")

# COMMAND ----------

# Ячейка 2: вся работа. Самодостаточна.
import csv, gzip, io, time, calendar
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal, InvalidOperation

import requests
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               TimestampType, DecimalType)

JOB_NAME = "Kabinet - FBA Charges Loader"
SP_API_EU = "https://sellingpartnerapi-eu.amazon.com"
MP_ES = "A1RKKUPIHCS9HS"          # любой рынок региона: отчёты приходят по всему аккаунту
UC_STORAGE = "dnipro_m.dnipro_m.raw_amazon_fba_storage_fees"
UC_REIMB   = "dnipro_m.dnipro_m.raw_amazon_fba_reimbursements"
VOL = "/Volumes/dnipro_m/dnipro_m/kabinet_raw"
PG_HOST = "ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com"
PG_EP   = "projects/kabinet-dashboard/branches/production/endpoints/primary"
STORAGE_MONTHS_BACK = 2
REIMB_DAYS_BACK = 60

def _param(name):
    try:
        return dbutils.widgets.get(name) or None  # noqa: F821
    except Exception:
        return None
STORAGE_FROM = _param("storage_from")     # YYYY-MM — backfill
REIMB_FROM   = _param("reimb_from")       # YYYY-MM-DD — backfill

# ── SP-API ────────────────────────────────────────────────────────────────
LWA_APP_ID    = dbutils.secrets.get("amazon-sp-api", "lwa-app-id")        # noqa: F821
LWA_SECRET    = dbutils.secrets.get("amazon-sp-api", "lwa-client-secret")  # noqa: F821
REFRESH_TOKEN = dbutils.secrets.get("amazon-sp-api", "refresh-token")      # noqa: F821
_tok = {"v": None, "exp": 0}
def token():
    if _tok["v"] and time.time() < _tok["exp"] - 60:
        return _tok["v"]
    r = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN,
        "client_id": LWA_APP_ID, "client_secret": LWA_SECRET}, timeout=30)
    r.raise_for_status(); _tok["v"] = r.json()["access_token"]; _tok["exp"] = time.time() + 3300
    return _tok["v"]

def api(method, path, **kw):
    # createReport — один запрос в минуту на весь аккаунт, и квоту делят все
    # загрузчики: SQP Loader в это же время гоняет очередь из сотен отчётов.
    # Поэтому на создании ждём терпеливо, до 40 минут по минуте; остальные
    # вызовы — короткими паузами.
    is_create = method.lower() == "post" and path.endswith("/reports")
    tries, pause = (40, 60) if is_create else (10, 15)
    for attempt in range(tries):
        r = requests.request(method, SP_API_EU + path, headers={"x-amz-access-token": token()}, timeout=90, **kw)
        if r.status_code == 429:
            time.sleep(pause if is_create else min(pause * (attempt + 1), 90)); continue
        r.raise_for_status(); return r.json()
    # [QUOTA_429] — маркер для сторожа: это исчерпанная квота createReport, а не поломка кода
    raise RuntimeError(f"[QUOTA_429] {tries} попыток по {pause} с, всё 429: {path}")

def fetch_report(rtype, start, end):
    """Запросить отчёт, дождаться, скачать. Возвращает (report_id, строки TSV)."""
    rid = api("post", "/reports/2021-06-30/reports",
              json={"reportType": rtype, "marketplaceIds": [MP_ES],
                    "dataStartTime": start, "dataEndTime": end})["reportId"]
    t0 = time.time()
    while True:
        st = api("get", f"/reports/2021-06-30/reports/{rid}")
        if st["processingStatus"] in ("DONE", "FATAL", "CANCELLED"): break
        if time.time() - t0 > 900: raise RuntimeError(f"{rtype} {rid}: не готов за 15 минут")
        time.sleep(15)
    if st["processingStatus"] == "CANCELLED":
        # CANCELLED у Amazon — «за этот период данных нет» (хранение за прошлый месяц публикуется около 7–15 числа),
        # а не сбой: 05.10.2026 такой ответ ронял весь прогон, и возмещения с пульсом не записывались (10.10.2026)
        return rid, None
    if st["processingStatus"] != "DONE":
        raise RuntimeError(f"{rtype} {rid}: {st['processingStatus']}")
    doc = api("get", f"/reports/2021-06-30/documents/{st['reportDocumentId']}")
    raw = requests.get(doc["url"], timeout=180).content
    if doc.get("compressionAlgorithm") == "GZIP": raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "replace")
    dbutils.fs.put(f"{VOL}/amazon_fba_charges/raw/{rtype}_{rid}.tsv", text, True)  # noqa: F821
    return rid, list(csv.reader(io.StringIO(text), delimiter="\t"))

def num(v, q="0.01"):
    v = (v or "").strip().replace(",", ".")
    if v in ("", "--"): return None
    try: return Decimal(v).quantize(Decimal(q))
    except InvalidOperation: return None
def integer(v):
    v = (v or "").strip()
    return int(float(v)) if v not in ("", "--") else None
def ts(v):
    v = (v or "").strip()
    if not v: return None
    try: return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError: return None

def norm_header(h): return h.strip().lower().replace("-", "_")

# ── Lakebase ──────────────────────────────────────────────────────────────
_w = WorkspaceClient()
_pg = psycopg2.connect(host=PG_HOST, port=5432, dbname="databricks_postgres",
                       user=_w.current_user.me().user_name,
                       password=_w.postgres.generate_database_credential(endpoint=PG_EP).token, sslmode="require")

def replicate(table, cols, rows, key):
    if not rows: return
    # loaded_at — время ЗАПИСИ этим прогоном, и у уже бывших строк тоже: по нему правило свежести судит, жив ли
    # загрузчик, а без этого оно показывало «последняя новая строка» и тревожило в тихие недели (10.10.2026)
    upd = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in key] + ["loaded_at = now()"])
    with _pg.cursor() as cur:
        psycopg2.extras.execute_values(cur,
            f"INSERT INTO kabinet_data.{table} ({','.join(cols)}) VALUES %s "
            f"ON CONFLICT ({','.join(key)}) DO UPDATE SET {upd}", rows, page_size=1000)
    _pg.commit()

# ═══ 1. Хранение: два последних закрытых месяца (или backfill) ═══════════
today = datetime.now(timezone.utc).date()
def month_range(first_ym, last_ym):
    y, m = map(int, first_ym.split("-")); ly, lm = map(int, last_ym.split("-"))
    while (y, m) <= (ly, lm):
        yield f"{y:04d}-{m:02d}", y, m
        m += 1
        if m == 13: y, m = y + 1, 1
last_closed = (today.replace(day=1) - timedelta(days=1))
first_ym = STORAGE_FROM or (last_closed.replace(day=1) - timedelta(days=31 * (STORAGE_MONTHS_BACK - 1))).strftime("%Y-%m")
months = list(month_range(first_ym, last_closed.strftime("%Y-%m")))
print(f"хранение: месяцы {[m[0] for m in months]}")

S_COLS = ["asin","fnsku","product_name","fulfillment_center","country_code","longest_side","median_side","shortest_side",
          "measurement_units","weight","weight_units","item_volume","volume_units","product_size_tier",
          "average_quantity_on_hand","average_quantity_pending_removal","estimated_total_item_volume","month_of_charge",
          "storage_utilization_ratio","storage_utilization_ratio_units","base_rate","utilization_surcharge_rate",
          "avg_qty_for_sus","est_vol_for_sus","est_base_msf","est_sus","currency","estimated_monthly_storage_fee",
          "category","eligible_for_inventory_discount","qualifies_for_inventory_discount","total_incentive_fee_amount",
          "breakdown_incentive_fee_amount","average_quantity_customer_orders","report_id"]
S_NUM2 = {"longest_side","median_side","shortest_side","average_quantity_on_hand","average_quantity_pending_removal",
          "storage_utilization_ratio","avg_qty_for_sus","average_quantity_customer_orders"}
S_NUM3 = {"weight"}; S_NUM4 = {"base_rate","utilization_surcharge_rate","est_base_msf","est_sus","estimated_monthly_storage_fee","total_incentive_fee_amount"}
S_NUM6 = {"item_volume","estimated_total_item_volume","est_vol_for_sus"}
storage_rows, storage_months_done = [], []
def dec(p, q): return DecimalType(p, q)
S_SCHEMA = StructType([StructField(c,
    dec(10,2) if c in S_NUM2 else dec(10,3) if c in S_NUM3 else dec(12,4) if c in S_NUM4 else dec(14,6) if c in S_NUM6 else StringType())
    for c in S_COLS])

def write_storage(rows):
    """Месяц пишем сразу, как скачали: упадём на лимите через три месяца —
    первые три уже лежат, а не пропали вместе с прогоном."""
    if not rows: return
    spark.createDataFrame(rows, S_SCHEMA).createOrReplaceTempView("_storage_new")  # noqa: F821
    spark.sql(f"""
        MERGE INTO {UC_STORAGE} t
        USING (SELECT *, current_timestamp() AS loaded_at FROM _storage_new) s
        ON t.asin = s.asin AND t.fnsku = s.fnsku AND t.fulfillment_center = s.fulfillment_center AND t.month_of_charge = s.month_of_charge
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)  # noqa: F821
    replicate("raw_amazon_fba_storage_fees", S_COLS, rows, ["asin","fnsku","fulfillment_center","month_of_charge"])

for ym, y, m in months:
    last_day = calendar.monthrange(y, m)[1]
    rid, rows = fetch_report("GET_FBA_STORAGE_FEE_CHARGES_DATA",
                             f"{ym}-01T00:00:00Z", f"{ym}-{last_day:02d}T23:59:59Z")
    if rows is None:
        storage_months_done.append((ym, "нет данных"))
        print(f"  {ym}: Amazon ответил CANCELLED — за месяц данных пока нет, report {rid}")
        continue
    hdr = [norm_header(h) for h in rows[0]]; idx = {h: i for i, h in enumerate(hdr)}
    seen = set(); n = 0; month_rows = []
    for r in rows[1:]:
        g = lambda c: (r[idx[c]].strip() if c in idx and idx[c] < len(r) else "")
        fc = g("fulfillment_center").strip("'\"")
        key = (g("asin"), g("fnsku"), fc, g("month_of_charge"))
        if not all(key) or key in seen: continue          # дубли строк в отчёте бывают
        seen.add(key)
        rec = []
        for c in S_COLS:
            if c == "report_id": rec.append(rid)
            elif c == "fulfillment_center": rec.append(fc)
            elif c in S_NUM2: rec.append(num(g(c), "0.01"))
            elif c in S_NUM3: rec.append(num(g(c), "0.001"))
            elif c in S_NUM4: rec.append(num(g(c), "0.0001"))
            elif c in S_NUM6: rec.append(num(g(c), "0.000001"))
            else: rec.append(g(c) or None)
        month_rows.append(tuple(rec)); n += 1
    write_storage(month_rows)
    storage_rows += month_rows
    storage_months_done.append((ym, n))
    print(f"  {ym}: строк {n}, report {rid} — записано")

if storage_rows:
    print(f"✅ хранение: {len(storage_rows)} строк в UC и Lakebase")

# ═══ 2. Возмещения: последние 60 дней (или backfill) ═════════════════════
r_from = date.fromisoformat(REIMB_FROM) if REIMB_FROM else today - timedelta(days=REIMB_DAYS_BACK)
R_COLS = ["approval_date","reimbursement_id","case_id","amazon_order_id","reason","sku","fnsku","asin","product_name",
          "condition","currency_unit","amount_per_unit","amount_total","quantity_reimbursed_cash",
          "quantity_reimbursed_inventory","quantity_reimbursed_total","original_reimbursement_id",
          "original_reimbursement_type","report_id"]
reimb_rows = []
# отчёт принимает окно до ~180 дней; backfill режем кусками
cur_from = r_from
while cur_from < today:
    cur_to = min(cur_from + timedelta(days=170), today)
    rid, rows = fetch_report("GET_FBA_REIMBURSEMENTS_DATA",
                             f"{cur_from.isoformat()}T00:00:00Z", f"{cur_to.isoformat()}T23:59:59Z")
    if rows is None:   # CANCELLED — возмещений за окно нет
        print(f"  возмещения {cur_from}–{cur_to}: CANCELLED, данных нет, report {rid}")
        cur_from = cur_to + timedelta(days=1); continue
    hdr = [norm_header(h) for h in rows[0]]; idx = {h: i for i, h in enumerate(hdr)}
    seen = set(); n = 0
    for r in rows[1:]:
        g = lambda c: (r[idx[c]].strip() if c in idx and idx[c] < len(r) else "")
        key = (g("reimbursement_id"), g("sku"), g("asin"))
        if not all(key) or key in seen: continue
        seen.add(key)
        reimb_rows.append((ts(g("approval_date")), g("reimbursement_id"), g("case_id") or None, g("amazon_order_id") or None,
                           g("reason") or None, g("sku"), g("fnsku") or None, g("asin"), g("product_name") or None,
                           g("condition") or None, g("currency_unit") or None,
                           num(g("amount_per_unit")), num(g("amount_total")),
                           integer(g("quantity_reimbursed_cash")), integer(g("quantity_reimbursed_inventory")),
                           integer(g("quantity_reimbursed_total")),
                           g("original_reimbursement_id") or None, g("original_reimbursement_type") or None, rid))
        n += 1
    print(f"  возмещения {cur_from}→{cur_to}: строк {n}, report {rid}")
    cur_from = cur_to + timedelta(days=1)

if reimb_rows:
    R_SCHEMA = StructType([StructField("approval_date", TimestampType())] +
        [StructField(c, StringType()) for c in R_COLS[1:11]] +
        [StructField("amount_per_unit", DecimalType(12,2)), StructField("amount_total", DecimalType(12,2)),
         StructField("quantity_reimbursed_cash", IntegerType()), StructField("quantity_reimbursed_inventory", IntegerType()),
         StructField("quantity_reimbursed_total", IntegerType()),
         StructField("original_reimbursement_id", StringType()), StructField("original_reimbursement_type", StringType()),
         StructField("report_id", StringType())])
    rdf = spark.createDataFrame(reimb_rows, R_SCHEMA)  # noqa: F821
    rdf.createOrReplaceTempView("_reimb_new")
    spark.sql(f"""
        MERGE INTO {UC_REIMB} t
        USING (SELECT *, current_timestamp() AS loaded_at FROM _reimb_new) s
        ON t.reimbursement_id = s.reimbursement_id AND t.sku = s.sku AND t.asin = s.asin
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)  # noqa: F821
    replicate("raw_amazon_fba_reimbursements", R_COLS, reimb_rows, ["reimbursement_id","sku","asin"])
    print(f"✅ возмещения: {len(reimb_rows)} строк в UC и Lakebase")

# ── SYSTEM PULSE: безусловно, последним, на верхнем уровне ───────────────
_note = (f"storage {', '.join(f'{ym}:{n}' for ym, n in storage_months_done)}; "
         f"reimb {len(reimb_rows)} rows since {r_from}")
with _pg.cursor() as cur:
    cur.execute("""
        INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
        VALUES (%s, now(), %s, 30)
        ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note
    """, (JOB_NAME, _note))
_pg.commit(); _pg.close()
print(f"\n💓 {JOB_NAME}: {_note}")
