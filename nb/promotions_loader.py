# Databricks notebook source
# DBTITLE 1,Промо Amazon по товару (Data Kiosk, Seller Analytics) → сырьё
# ═════════════════════════════════════════════════════════════
# KABINET - AMAZON PROMOTIONS LOADER — акции и скидки Amazon по ASIN × день, без ожидания settlement
# Источник: SP-API Data Kiosk, analytics_sellerAnalytics_2025_03_31 → sellerAnalyticsView, блок promotion
#           (тип и статус акции, даты, сделка dealId/dealTitle, показы, конверсия, скидка, цена, штуки и выручка).
# Пишет:    dnipro_m.dnipro_m.raw_amazon_seller_analytics_promotions — строка на ASIN × рынок × день, только дни с акцией.
# Один запрос на все рынки Amazon (один регион EU), суммы — в евро (currencyCode EUR, пересчёт GB/SE/PL делает Amazon).
# Группировка — asin и marketplaceId: msku Amazon для промо не отдаёт (проба 18.10.2026 — пусто у всех строк), а
# идентификатора акции в группировке нет; акцию называют dealId и dealTitle.
# Окно: таблица пуста — вся история (не старше двух лет); дальше каждый прогон перечитывает последние
# reorder_params.promotions_reread_days (Amazon уточняет промо задним числом) и всё, чего ещё нет. Окно заменяется
# целиком по дате. Кусок (31 день), который не загрузился, не пишется; на 429 не повторяем — остаток следующим прогоном.
# Квота Data Kiosk — 1 запрос и 1 скачивание в минуту на аккаунт: днём её занимают реплика Sales & Traffic (~10:30,
# запасной 11:00) и Economics Loader (12:30), поэтому прогон в 08:50, а первая загрузка истории — ночью.
# Параметры: dry_run=1 — days последних дней без записи; since=ГГГГ-ММ-ДД — перечитать с даты.
# Самодостаточная ячейка: своё подключение, свои константы. Метка пульса — последней и безусловно.
# ═════════════════════════════════════════════════════════════
import datetime as dt
import gzip
import json
import time
from zoneinfo import ZoneInfo

import psycopg2
import requests
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import DateType, DoubleType, IntegerType, StringType, StructField, StructType, TimestampType

JOB_NAME = "Kabinet - Amazon Promotions Loader"
EP = "https://sellingpartnerapi-eu.amazon.com"
TABLE = "dnipro_m.dnipro_m.raw_amazon_seller_analytics_promotions"
CHUNK_DAYS = 31
DK_PAUSE_SEC = 62

for _n, _d in (("dry_run", "0"), ("days", "7"), ("since", "")):
    try:
        dbutils.widgets.text(_n, _d)
    except Exception:
        pass
DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
PROBE_DAYS = int(dbutils.widgets.get("days").strip() or 7)
SINCE = dbutils.widgets.get("since").strip()

_w = WorkspaceClient()


def pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_w.current_user.me().user_name,
                            password=_w.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token,
                            sslmode="require")


REREAD_DAYS = 35
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""SELECT amazon_id, upper(country) FROM kabinet_data.marketplaces
                    WHERE is_active = true AND amazon_id IS NOT NULL""")
    MARKETS = dict(_cur.fetchall())
    _cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'promotions_reread_days'")
    _row = _cur.fetchone()
    if _row and _row[0]:
        REREAD_DAYS = int(_row[0])

today = dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()
END = today - dt.timedelta(days=1)
EARLIEST = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=729)     # Amazon: не старше двух лет
if DRY_RUN:
    START = END - dt.timedelta(days=PROBE_DAYS - 1)
elif SINCE:
    START = max(dt.date.fromisoformat(SINCE), EARLIEST)
else:
    last = spark.sql(f"SELECT max(date) d FROM {TABLE}").collect()[0]["d"] if spark.catalog.tableExists(TABLE) else None
    START = EARLIEST if last is None else min(last + dt.timedelta(days=1), END - dt.timedelta(days=REREAD_DAYS - 1))
chunks, d1 = [], START
while d1 <= END:
    d2 = min(d1 + dt.timedelta(days=CHUNK_DAYS - 1), END)
    chunks.append((d1, d2))
    d1 = d2 + dt.timedelta(days=1)
print(f"рынков {len(MARKETS)}: {sorted(MARKETS.values())}; окно {START}…{END}, кусков {len(chunks)}"
      + (" (проба, без записи)" if DRY_RUN else ""))

# ── Data Kiosk ──
sec = lambda k: dbutils.secrets.get("amazon-sp-api", k)
_tok = {"v": None, "exp": 0}


def headers():
    if not _tok["v"] or time.time() > _tok["exp"] - 120:
        r = requests.post("https://api.amazon.com/auth/o2/token", timeout=30, data={
            "grant_type": "refresh_token", "refresh_token": sec("refresh-token"),
            "client_id": sec("lwa-app-id"), "client_secret": sec("lwa-client-secret")})
        r.raise_for_status()
        _tok.update(v=r.json()["access_token"], exp=time.time() + int(r.json().get("expires_in", 3600)))
    return {"x-amz-access-token": _tok["v"], "Content-Type": "application/json"}


class Quota429(Exception):
    pass


_last = {"create": 0.0, "doc": 0.0}


def paced(kind):
    wait = _last[kind] + DK_PAUSE_SEC - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[kind] = time.time()


def dk(method, path, **kw):
    r = requests.request(method, EP + path, headers=headers(), timeout=60, **kw)
    if r.status_code == 429:
        raise Quota429(f"{path}: 429 {r.text[:150]}")
    r.raise_for_status()
    return r.json()


MP_LIST = ", ".join(f'"{m}"' for m in sorted(MARKETS))
QUERY = """query { analytics_sellerAnalytics_2025_03_31 { sellerAnalyticsView(startDate: "%s", endDate: "%s",
 aggregateBy: DAY, currencyCode: "EUR", marketplaceId: [%s]) { startDate endDate metrics { groupByKey { asin marketplaceId }
 metrics { promotion { promotionType promotionStatus promotionStartDate promotionEndDate promotionAsinStateType dealId dealTitle
 promotionGlanceViewCnt { value } promotionConversionRate { value } promotionDiscountPct { value }
 promotionDiscountAmt { amount { amount currencyCode } } promotionOrderedPrice { amount { amount currencyCode } }
 dealOurPrice { amount { amount currencyCode } }
 promotionOrderedUnitsWithRevenue { unitsWithValue { units value { amount currencyCode } } } } } } } } }"""


def val(node):
    v = (node or {}).get("value")
    return float(v) if v is not None else None


def amt(node):
    a = ((node or {}).get("amount") or {})
    return (float(a["amount"]) if a.get("amount") is not None else None), a.get("currencyCode")


def d(v):
    try:
        return dt.date.fromisoformat(v) if v else None
    except ValueError:
        return None


def rows_of(line):
    day = d(line.get("startDate"))
    out = []
    for m in line.get("metrics") or []:
        k = m.get("groupByKey") or {}
        p = (m.get("metrics") or {}).get("promotion") or {}
        disc, cur = amt(p.get("promotionDiscountAmt"))
        price, cur2 = amt(p.get("promotionOrderedPrice"))
        deal_price, _ = amt(p.get("dealOurPrice"))
        uv = ((p.get("promotionOrderedUnitsWithRevenue") or {}).get("unitsWithValue") or {})
        units = uv.get("units")
        rev = (uv.get("value") or {}).get("amount")
        if not (p.get("promotionType") or p.get("dealId") or disc):
            continue                                    # строки без акции не храним
        out.append((day, k.get("marketplaceId"), MARKETS.get(k.get("marketplaceId")), k.get("asin"),
                    p.get("promotionType"), p.get("promotionStatus"), d(p.get("promotionStartDate")),
                    d(p.get("promotionEndDate")), p.get("promotionAsinStateType"), p.get("dealId"), p.get("dealTitle"),
                    val(p.get("promotionGlanceViewCnt")), val(p.get("promotionConversionRate")),
                    val(p.get("promotionDiscountPct")), disc, price, deal_price,
                    int(units) if units is not None else None, float(rev) if rev is not None else None,
                    cur or cur2 or "EUR"))
    return out


SCHEMA = StructType([
    StructField("date", DateType()), StructField("marketplace_id", StringType()), StructField("country", StringType()),
    StructField("asin", StringType()), StructField("promotion_type", StringType()),
    StructField("promotion_status", StringType()), StructField("promotion_start_date", DateType()),
    StructField("promotion_end_date", DateType()), StructField("promotion_asin_state", StringType()),
    StructField("deal_id", StringType()), StructField("deal_title", StringType()),
    StructField("glance_views", DoubleType()), StructField("conversion_rate", DoubleType()),
    StructField("discount_pct", DoubleType()), StructField("discount_amount", DoubleType()),
    StructField("ordered_price", DoubleType()), StructField("deal_our_price", DoubleType()),
    StructField("units_with_revenue", IntegerType()), StructField("revenue", DoubleType()),
    StructField("currency", StringType()), StructField("loaded_at", TimestampType())])

LOADED = dt.datetime.now(dt.timezone.utc)
errors, parts, n_rows, made, stopped, probe = [], [], 0, False, None, []
for d1, d2 in chunks:
    try:
        paced("create")
        qid = dk("post", "/dataKiosk/2023-11-15/queries", json={"query": QUERY % (d1, d2, MP_LIST)})["queryId"]
        t0, meta = time.time(), {}
        while time.time() - t0 < 1800:
            meta = dk("get", f"/dataKiosk/2023-11-15/queries/{qid}")
            if meta.get("processingStatus") in ("DONE", "FATAL", "CANCELLED"):
                break
            time.sleep(10)
        st = meta.get("processingStatus")
        rows = []
        if st == "DONE" and meta.get("dataDocumentId"):
            paced("doc")
            doc = dk("get", f"/dataKiosk/2023-11-15/documents/{meta['dataDocumentId']}")
            raw = requests.get(doc["documentUrl"], timeout=300).content
            if doc.get("compressionAlgorithm") == "GZIP":
                raw = gzip.decompress(raw)
            for line in raw.decode("utf-8").splitlines():
                if line.strip():
                    rows.extend(rows_of(json.loads(line)))
        elif st != "DONE":
            err = f"{st}: {json.dumps(meta)[:200]}"
            if st == "FATAL" and meta.get("errorDocumentId"):
                paced("doc")
                doc = dk("get", f"/dataKiosk/2023-11-15/documents/{meta['errorDocumentId']}")
                err = f"FATAL: {requests.get(doc['documentUrl'], timeout=120).text[:200]}"
            errors.append(f"{d1}…{d2}: {err}")
            continue
        n_rows += len(rows)
        disc = sum(r[14] or 0 for r in rows)
        parts.append(f"{d1:%d.%m.%y}…{d2:%d.%m.%y} {len(rows)} стр, скидка {disc:,.0f} €")
        if DRY_RUN:
            probe.append(parts[-1] + f", ASIN {len({(r[1], r[3]) for r in rows})}, акций {len({r[9] for r in rows if r[9]})}")
            print("  " + probe[-1])
            continue
        if not made:
            ddl = ", ".join(f"{f.name} {f.dataType.simpleString().upper()}" for f in SCHEMA.fields)
            spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLE} ({ddl}) USING DELTA COMMENT 'Data Kiosk Seller Analytics, "
                      f"блок promotion: ASIN × рынок × день с акцией, суммы в евро. Пишет {JOB_NAME}, окно перечитывается "
                      f"целиком.'")
            made = True
        # replaceWhere: кусок заменяется атомарно — уточнённые Amazon дни переписываются, дублей нет
        (spark.createDataFrame([(*r, LOADED) for r in rows], SCHEMA).write.format("delta").mode("overwrite")
         .option("replaceWhere", f"date >= DATE'{d1}' AND date <= DATE'{d2}'").saveAsTable(TABLE))
    except Quota429 as e:
        stopped = f"квота Data Kiosk (429) — не повторяю, остаток следующим прогоном: {e}"
        break
    except Exception as e:
        errors.append(f"{d1}…{d2}: {type(e).__name__}: {str(e)[:200]}")

summary = (f"кусков {len(chunks)}, строк {n_rows} с {START}; " + "; ".join(parts[-3:])
           + (f"; остановлено: {stopped}" if stopped else "")
           + (f" | ⚙️ сбои: {'; '.join(errors[:3])}" if errors else ""))
print("📊 " + summary)
if DRY_RUN:
    dbutils.notebook.exit(json.dumps({"summary": summary, "probe": probe, "errors": errors}, ensure_ascii=False))

# ── SYSTEM PULSE: безусловно, последним ──
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                    VALUES (%s, now(), %s)
                    ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                 (JOB_NAME, summary[:900]))
print(f"💓 {JOB_NAME}")

# Незаписанный кусок — не тишина: записанное и пульс на месте, прогон падает. Квота — не сбой: остаток завтра.
if errors:
    raise RuntimeError("промо Amazon не загружено: " + "; ".join(errors[:4]))
