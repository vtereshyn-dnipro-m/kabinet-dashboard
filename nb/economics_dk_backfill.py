# Databricks notebook source
# DBTITLE 1,Добор экономики Amazon из Data Kiosk за два года → economics_daily / economics_fees
# ═════════════════════════════════════════════════════════════
# KABINET - ECONOMICS DK BACKFILL — история экономики Amazon (продажи, сборы, выплата) до первого загруженного дня
# Источник: SP-API Data Kiosk, analytics_economics_2024_03_15 — тот же запрос, что в Kabinet - Economics Loader.
# Пишет:    dnipro_m.kabinet.economics_daily и dnipro_m.kabinet.economics_fees — те же таблицы и колонки, что
#           Economics Loader; журнал кусков — dnipro_m.kabinet.economics_load_runs (статусы BACKFILL_*).
# Решения владельца 18.10.2026:
#   • граница — первый загруженный день КАЖДОГО рынка (у большинства 15.05.2026, у GB и IE — 01.06.2026): пишем только
#     дни раньше неё и только те, которых в economics_daily ещё нет — уже загруженное не перезаписывается. Граница
#     фиксируется первым прогоном (строка BACKFILL_BOUNDARY в журнале, end_date — последний день добора) ДО любой
#     записи: иначе после первой ночи «первым загруженным днём» стал бы уже добранный октябрь 2024 и остальная
#     история выпала бы. Новый рынок без данных получает границу 15.05.2026;
#   • в economics_summary история не переносится: ячейка 2 Economics Loader читает с 15.05.2026 (GB и IE за 15–31.05
#     туда попадут — это уже не история до сводки, а её же период)
#     (nb/patches/2026-10-18_economics_summary_since_Economics_Loader.diff, выложить ДО первой ночи добора);
#   • окно — ночь 00:30–04:30 Kyiv: Data Kiosk днём занимают реплика Sales & Traffic (~10:30, запасной 11:00) и
#     Economics Loader (12:30). Новых запросов после reorder_params.econ_backfill_deadline_hhmm не создаём —
#     остаток доберёт следующая ночь.
# Квота Data Kiosk — 1 createQuery и 1 getDocument в минуту (запас 15) на аккаунт; createReport не трогаем.
# На 429 не повторяем: кусок остаётся на следующую ночь, записанное — остаётся.
# Amazon отдаёт не старше двух лет (проверено 16.10.2026: «Start date must be no more than two years ago»).
# Параметры: dry_run=1 — limit кусков без записи; limit — сколько кусков в пробе; deadline — HH:MM вместо настройки.
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
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, IntegerType, StringType, StructField, StructType

JOB_NAME = "Kabinet - Economics DK Backfill"
EP = "https://sellingpartnerapi-eu.amazon.com"
DEFAULT_CUTOFF = dt.date(2026, 5, 15)   # с этой даты экономику грузит Economics Loader; граница рынка без данных
CHUNK_DAYS = 31
DK_PAUSE_SEC = 62                 # 1 createQuery и 1 getDocument в минуту — держим шаг чуть больше минуты
KYIV = ZoneInfo("Europe/Kyiv")

for _n, _d in (("dry_run", "0"), ("limit", "2"), ("deadline", "")):
    try:
        dbutils.widgets.text(_n, _d)
    except Exception:
        pass
DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
LIMIT = int(dbutils.widgets.get("limit").strip() or 2)
DEADLINE_ARG = dbutils.widgets.get("deadline").strip()

_w = WorkspaceClient()


def pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_w.current_user.me().user_name,
                            password=_w.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token,
                            sslmode="require")


# ── рынки — тот же отбор, что у Economics Loader; срок окна — из настроек ──
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""SELECT amazon_id, upper(country) FROM kabinet_data.marketplaces
                    WHERE sync_economics = true AND is_active = true AND amazon_id IS NOT NULL""")
    MARKETPLACES = dict(_cur.fetchall())
    _cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'econ_backfill_deadline_hhmm'")
    _row = _cur.fetchone()
DEADLINE_HHMM = int(DEADLINE_ARG.replace(":", "")) if DEADLINE_ARG else int(_row[0]) if _row and _row[0] else 430
now_kyiv = dt.datetime.now(KYIV)
deadline = now_kyiv.replace(hour=DEADLINE_HHMM // 100, minute=DEADLINE_HHMM % 100, second=0, microsecond=0)
if deadline < now_kyiv - dt.timedelta(hours=12):       # запуск вечером накануне — срок завтрашним утром
    deadline += dt.timedelta(days=1)
print(f"рынков {len(MARKETPLACES)}: {sorted(MARKETPLACES.values())}; новых запросов не создаём после "
      f"{deadline:%d.%m %H:%M} Kyiv" + (" (проба — срок не действует)" if DRY_RUN else ""))

# ── граница каждого рынка: фиксируется один раз, до первой записи добора ──
EARLIEST = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=729)   # Amazon: не старше двух лет
RUNS = "dnipro_m.kabinet.economics_load_runs"
saved = {r["marketplace"]: r["end_date"] for r in spark.sql(
    f"SELECT marketplace, max(end_date) end_date FROM {RUNS} WHERE status = 'BACKFILL_BOUNDARY' GROUP BY 1").collect()}
first_day = {r["marketplace"]: r["d"] for r in spark.sql(
    "SELECT marketplace, min(sales_date) d FROM dnipro_m.kabinet.economics_daily GROUP BY 1").collect()}
LAST = {}                                   # последний день добора по рынку (включительно)
for mk in MARKETPLACES.values():
    if mk in saved:
        LAST[mk] = saved[mk]
    else:
        LAST[mk] = (first_day.get(mk) or DEFAULT_CUTOFF) - dt.timedelta(days=1)
        if not DRY_RUN:
            (spark.createDataFrame([(dt.datetime.now(dt.timezone.utc), mk, None, LAST[mk], "BACKFILL_BOUNDARY", 0,
                                     f"первый загруженный день {first_day.get(mk) or 'нет данных, взят ' + str(DEFAULT_CUTOFF)}")],
                                   "run_ts timestamp, marketplace string, start_date date, end_date date, status string, "
                                   "rows_loaded int, error_message string").write.mode("append").saveAsTable(RUNS))
print("граница добора (последний день): " + ", ".join(f"{mk} {LAST[mk]}" for mk in sorted(LAST)))

# ── что уже есть: дни рынка до границы и куски, закрытые прошлыми ночами ──
have_days = {}
for r in spark.sql(f"""SELECT marketplace, sales_date FROM dnipro_m.kabinet.economics_daily
                       WHERE sales_date <= DATE'{max(LAST.values())}' GROUP BY 1, 2""").collect():
    if r["sales_date"] <= LAST.get(r["marketplace"], DEFAULT_CUTOFF):
        have_days.setdefault(r["marketplace"], set()).add(r["sales_date"])
done_chunks = {(r["marketplace"], r["end_date"]) for r in spark.sql(
    f"SELECT marketplace, end_date FROM {RUNS} WHERE status IN ('BACKFILL_DONE', 'BACKFILL_EMPTY')").collect()}

# сетка кусков привязана к границе рынка (от неё назад по 31 дню), а не к «сегодня минус два года»: край истории
# сдвигается каждый день, и сетка от него давала бы каждую ночь новые куски вместо уже закрытых
chunks = []
for mp_id, mk in sorted(MARKETPLACES.items(), key=lambda x: x[1]):
    d2 = LAST[mk]
    while d2 >= EARLIEST:
        d1 = max(d2 - dt.timedelta(days=CHUNK_DAYS - 1), EARLIEST)
        days = {d1 + dt.timedelta(days=i) for i in range((d2 - d1).days + 1)}
        if (mk, d2) not in done_chunks and not days <= have_days.get(mk, set()):
            chunks.append((mp_id, mk, d1, d2))
        d2 = d2 - dt.timedelta(days=CHUNK_DAYS)
chunks.sort(key=lambda c: (c[1], c[2]))
total = len(chunks)
print(f"история с {EARLIEST}: кусков осталось {total}" + (f", в пробе {min(LIMIT, total)}" if DRY_RUN else ""))
if DRY_RUN:
    chunks = chunks[:LIMIT]

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
        raise Quota429(f"{path}: 429 {r.headers.get('x-amzn-RateLimit-Limit')} {r.text[:150]}")
    r.raise_for_status()
    return r.json()


def build_query(d1, d2, mp_id):          # дословно запрос Economics Loader (build_query)
    return f"""
    query SellerEconomicsDaily {{
      analytics_economics_2024_03_15 {{
        economics(startDate: "{d1}" endDate: "{d2}"
          marketplaceIds: ["{mp_id}"]
          aggregateBy: {{ date: DAY, productId: CHILD_ASIN }}) {{
          startDate endDate parentAsin childAsin msku
          sales {{ unitsOrdered unitsRefunded netUnitsSold
            orderedProductSales {{ amount currencyCode }}
            refundedProductSales {{ amount currencyCode }}
            netProductSales {{ amount currencyCode }}
            averageSellingPrice {{ amount currencyCode }} }}
          fees {{ feeTypeName charge {{ aggregatedDetail {{
            quantity amount {{ amount currencyCode }}
            amountPerUnit {{ amount currencyCode }} }} }} }}
          netProceeds {{ total {{ amount currencyCode }}
            perUnit {{ amount currencyCode }} }}
        }} }} }}
    """


def money(node):
    try:
        return float(node["amount"]), node.get("currencyCode")
    except (KeyError, TypeError, ValueError):
        return None, None


def parse(raw, mp_id, mk):               # как parse_daily Economics Loader: строка без childAsin не пишется
    asin = raw.get("childAsin")
    if not asin:
        return None, []
    try:
        day = dt.date.fromisoformat(raw["startDate"])
    except Exception:
        return None, []
    s = raw.get("sales") or {}
    ordered, cur = money(s.get("orderedProductSales"))
    refunded, _ = money(s.get("refundedProductSales"))
    net, _ = money(s.get("netProductSales"))
    asp, _ = money(s.get("averageSellingPrice"))
    fees, total_fees = [], 0.0
    for fee in raw.get("fees") or []:
        name = fee.get("feeTypeName")
        agg = (fee.get("charge") or {}).get("aggregatedDetail") or {}
        amt, fcur = money(agg.get("amount"))
        if not name or amt is None:
            continue
        apu, _ = money(agg.get("amountPerUnit"))
        fees.append((mp_id, mk, day, asin, name, float(agg["quantity"]) if agg.get("quantity") is not None else None,
                     amt, apu, fcur))
        total_fees += amt
    npt, _ = money((raw.get("netProceeds") or {}).get("total"))
    npu, _ = money((raw.get("netProceeds") or {}).get("perUnit"))
    daily = (mp_id, mk, day, asin, raw.get("parentAsin"), raw.get("msku"), int(s.get("unitsOrdered") or 0),
             int(s.get("unitsRefunded") or 0), int(s.get("netUnitsSold") or 0), ordered or 0.0, refunded or 0.0,
             net or 0.0, asp, cur, total_fees, npt, npu)
    return daily, fees


DAILY_SCHEMA = StructType([
    StructField("marketplace_id", StringType()), StructField("marketplace", StringType()),
    StructField("sales_date", DateType()), StructField("child_asin", StringType()),
    StructField("parent_asin", StringType()), StructField("msku", StringType()),
    StructField("units_ordered", IntegerType()), StructField("units_refunded", IntegerType()),
    StructField("net_units_sold", IntegerType()), StructField("ordered_product_sales", DoubleType()),
    StructField("refunded_product_sales", DoubleType()), StructField("net_product_sales", DoubleType()),
    StructField("average_selling_price", DoubleType()), StructField("currency_code", StringType()),
    StructField("total_fees", DoubleType()), StructField("net_proceeds_total", DoubleType()),
    StructField("net_proceeds_per_unit", DoubleType())])
FEES_SCHEMA = StructType([
    StructField("marketplace_id", StringType()), StructField("marketplace", StringType()),
    StructField("sales_date", DateType()), StructField("child_asin", StringType()),
    StructField("fee_type_name", StringType()), StructField("quantity", DoubleType()),
    StructField("amount", DoubleType()), StructField("amount_per_unit", DoubleType()),
    StructField("currency_code", StringType())])


def log_run(mk, d1, d2, status, rows=0, err=None):
    if DRY_RUN:
        return
    (spark.createDataFrame([(dt.datetime.now(dt.timezone.utc), mk, d1, d2, status, int(rows), err)],
                           "run_ts timestamp, marketplace string, start_date date, end_date date, status string, "
                           "rows_loaded int, error_message string")
     .write.mode("append").saveAsTable("dnipro_m.kabinet.economics_load_runs"))


# ── куски по очереди: один запрос в работе, запись сразу после куска ──
done, empty, rows_total, fee_total, errors, stopped, probe = 0, 0, 0, 0, [], None, []
for mp_id, mk, d1, d2 in chunks:
    if not DRY_RUN and dt.datetime.now(KYIV) >= deadline:
        stopped = f"срок {deadline:%H:%M} — остаток следующей ночью"
        break
    try:
        paced("create")
        qid = dk("post", "/dataKiosk/2023-11-15/queries", json={"query": build_query(d1, d2, mp_id)})["queryId"]
        t0, meta = time.time(), {}
        while time.time() - t0 < 1800:
            meta = dk("get", f"/dataKiosk/2023-11-15/queries/{qid}")
            if meta.get("processingStatus") in ("DONE", "FATAL", "CANCELLED"):
                break
            time.sleep(15)
        status = meta.get("processingStatus")
        if status != "DONE":
            err = f"{status}: {json.dumps(meta)[:300]}"
            if status == "FATAL" and meta.get("errorDocumentId"):
                paced("doc")
                d = dk("get", f"/dataKiosk/2023-11-15/documents/{meta['errorDocumentId']}")
                err = f"FATAL: {requests.get(d['documentUrl'], timeout=120).text[:300]}"
            errors.append(f"{mk} {d1}…{d2}: {err}")
            log_run(mk, d1, d2, "BACKFILL_ERROR", err=err[:900])
            continue
        if not meta.get("dataDocumentId"):          # за кусок у Amazon ничего нет — кусок закрыт
            empty += 1
            log_run(mk, d1, d2, "BACKFILL_EMPTY")
            continue
        paced("doc")
        d = dk("get", f"/dataKiosk/2023-11-15/documents/{meta['dataDocumentId']}")
        raw = requests.get(d["documentUrl"], timeout=300).content
        if d.get("compressionAlgorithm") == "GZIP":
            raw = gzip.decompress(raw)
        have = have_days.get(mk, set())
        daily_rows, fee_rows = [], []
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            daily, fees = parse(json.loads(line), mp_id, mk)
            if daily is None or daily[2] > LAST[mk] or daily[2] in have:
                continue                            # день уже загружен или не наш — не трогаем
            daily_rows.append(daily)
            fee_rows.extend(fees)
        if DRY_RUN:
            probe.append(f"{mk} {d1}…{d2}: дней {len({r[2] for r in daily_rows})}, строк {len(daily_rows)}, "
                         f"сборов {len(fee_rows)}, продажи {sum(r[11] for r in daily_rows):,.0f}, "
                         f"сборы {sum(f[6] for f in fee_rows):,.0f} {daily_rows[0][13] if daily_rows else ''}")
            print("  " + probe[-1])
        else:
            if daily_rows:
                (spark.createDataFrame(daily_rows, DAILY_SCHEMA).withColumn("loaded_at", F.current_timestamp())
                 .write.mode("append").saveAsTable("dnipro_m.kabinet.economics_daily"))
            if fee_rows:
                (spark.createDataFrame(fee_rows, FEES_SCHEMA).withColumn("loaded_at", F.current_timestamp())
                 .write.mode("append").saveAsTable("dnipro_m.kabinet.economics_fees"))
            log_run(mk, d1, d2, "BACKFILL_DONE", rows=len(daily_rows))
        done += 1
        rows_total += len(daily_rows)
        fee_total += len(fee_rows)
    except Quota429 as e:
        stopped = f"квота Data Kiosk (429) — не повторяю, остаток следующей ночью: {e}"
        break
    except Exception as e:
        errors.append(f"{mk} {d1}…{d2}: {type(e).__name__}: {str(e)[:200]}")
        log_run(mk, d1, d2, "BACKFILL_ERROR", err=str(e)[:900])

left = total - done - empty
summary = (f"кусков в очереди {total}: загружено {done}, пустых {empty}, осталось {left}; "
           f"строк economics_daily {rows_total}, сборов {fee_total}"
           + ("; история полная" if left == 0 and not errors else "")
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

# Упавший кусок — не тишина: записанное и пульс на месте, прогон падает. Квота и срок — не сбой: остаток завтра.
if errors:
    raise RuntimeError("добор экономики: куски не загружены: " + "; ".join(errors[:5]))
