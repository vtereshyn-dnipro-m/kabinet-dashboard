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
#
# Источник кода — nb/returns_loader.py в kabinet-dashboard (с 19.10.2026): правка PR'ом, выкладка после мержа.
# Два режима (параметр mode):
#   daily    — джоба «Kabinet - Returns Loader», 06:00: окно от последней загруженной даты минус LOOKBACK_DAYS;
#   backfill — джоба «Kabinet - Returns Backfill», 01:00: история с reorder_params.returns_backfill_from кусками,
#              не больше returns_backfill_max_reports новых createReport за прогон и только в тихое окно 01:00–02:30;
#              на 429 не повторяет — кусок ждёт следующей ночи. Кусок, который уже покрывает готовый отчёт из
#              getReports (их кто-то уже создал), берётся из него без createReport.
# ═══════════════════════════════════════════════════════════════
import requests, gzip, io, csv, time, json
from datetime import datetime, timedelta, timezone, date as _date
import pyspark.sql.functions as F
from pyspark.sql.types import *

# ─── Config ───
LOOKBACK_DAYS = 14        # Overlap window for late-arriving returns
INITIAL_DAYS = 90         # First load: 90 days of history
SP_API_EU = "https://sellingpartnerapi-eu.amazon.com"

try:
    dbutils.widgets.text("mode", "daily")
    MODE = (dbutils.widgets.get("mode") or "daily").strip().lower()
except Exception:
    MODE = "daily"
assert MODE in ("daily", "backfill"), f"mode={MODE!r}: ждём daily или backfill"
# dry_run=1 — проба добора: только готовые отчёты (без createReport), рынок определяется, а запись в таблицы,
# прогресс и пульс не делаются — ноутбук выходит со сводкой до первой записи.
try:
    dbutils.widgets.text("dry_run", "0")
    DRY = (dbutils.widgets.get("dry_run") or "0").strip() == "1"
except Exception:
    DRY = False
assert not (DRY and MODE == "daily"), "dry_run только для mode=backfill: ежедневный режим без createReport не работает"
PULSE_NAME = "Kabinet - Returns Loader" if MODE == "daily" else "Kabinet - Returns Backfill"
print(f"режим: {MODE}")

# Сбои отчётов, которые не роняют прогон сразу: данные остальных рынков и пульс пишутся, прогон падает в конце.
# До 19.10.2026 они печатались «❌ …» в лог, джоба оставалась зелёной, и рынок молча выпадал.
_errors = []


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

class Quota429(RuntimeError):
    """createReport ответил 429, а повторять нельзя (добор истории): кусок ждёт следующей ночи."""


def request_report(report_type, marketplace_id, start, end, retry_429=True):
    """Request a report and return report_id."""
    # createReport — одна квота на аккаунт (см. CLAUDE.md): на 429 ждём по минуте, до 40 минут,
    # потом падаем с маркером [QUOTA_429] — сторож заведёт инцидент квоты, а не поломки.
    # В доборе (retry_429=False) не повторяем вовсе: квота общая, и сорок попыток её не освободят.
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
            if not retry_429:
                raise Quota429(f"[QUOTA_429] createReport {report_type} {marketplace_id} {start}…{end}: 429, без повтора")
            time.sleep(60); continue
        r.raise_for_status()
        return r.json()["reportId"]
    raise RuntimeError(f"[QUOTA_429] 40 попыток по 60 с, всё 429: createReport {report_type} {marketplace_id}")


def wait_for_report(report_id, max_wait=300):
    """Poll until DONE, return document_id or None (CANCELLED — Amazon сам отменил: за окно данных нет)."""
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
        if status == "CANCELLED":
            return None          # Amazon отменил сам: за окно данных нет — это не сбой
        if status == "FATAL":
            raise RuntimeError(f"report {report_id}: FATAL")
        time.sleep(15)
    raise RuntimeError(f"report {report_id}: не готов за {max_wait} с")


def download_report(doc_id):
    """Download and decompress report content."""
    # getReportDocument — свой лимит (около запроса в минуту, запас 15), не createReport: на 429 ждать можно
    for _try in range(10):
        r = requests.get(
            f"{SP_API_EU}/reports/2021-06-30/documents/{doc_id}",
            headers={"x-amz-access-token": get_access_token()}
        )
        if r.status_code != 429:
            break
        time.sleep(60)
    r.raise_for_status()
    doc = r.json()
    r2 = requests.get(doc["url"])
    r2.raise_for_status()
    if doc.get("compressionAlgorithm") == "GZIP":
        return gzip.decompress(r2.content).decode("utf-8", errors="replace")
    return r2.content.decode("utf-8", errors="replace")


def _reader(content):
    """Отчёт обычно TSV, но бывает и CSV в кавычках (готовый отчёт 30.09.2026 с окном 31.10.2024–01.08.2025):
    разделитель — по первой строке."""
    content = content.lstrip("\ufeff")
    head = content.split("\n", 1)[0]
    delim = "\t" if "\t" in head or "," not in head else ","
    return csv.DictReader(io.StringIO(content), delimiter=delim)


def parse_fba_returns(content, mp_code):
    """Parse FBA returns TSV into list of dicts."""
    rows = []
    for r in _reader(content):
        r = {(k or "").strip().lstrip("\ufeff"): v for k, v in r.items()}
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
    for r in _reader(content):
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
            # «Return quantity» и «Return Reason» — так колонки называются в отчёте (проба 19.10.2026 по готовым
            # документам). До этого искались «Quantity» и «Return reason»: количество всегда было 1, причина пуста.
            "quantity": int(r.get("Return quantity") or r.get("Quantity") or r.get("quantity") or 1),
            "return_reason": r.get("Return Reason") or r.get("Return reason") or r.get("Reason"),
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
# FBA: один запрос — отчёт отдаётся по всему АККАУНТУ, а не по рынку из запроса (проверено 19.10.2026: в отчётах,
#      запрошенных по GB, лежат возвраты ES, IT, FR, DE, BE и единичный GB). Отдельный запрос по GB тратил бы квоту
#      на те же строки; рынок строки определяется ниже по заказу.
# MFN: по-маркетплейсно (продавец выполняет сам, привязка к MP точная).
# Marketplace для FBA резолвится по orders, а для истории — по возвратам денег Finances (Cell 4).
FBA = "GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA"
MFN = "GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE"
FBA_SOURCES = [("ALL", MARKETPLACES["ES"])]
all_returns = []


def _parse(rtype, content, mp_code):
    return parse_fba_returns(content, "_UNRESOLVED_") if rtype == FBA else parse_mfn_returns(content, mp_code)


if MODE == "daily":
    print("── FBA returns ──")
    for label, mp_id in FBA_SOURCES:
        try:
            doc_id = wait_for_report(request_report(FBA, mp_id, start_date, end_date))
            rows = _parse(FBA, download_report(doc_id), None) if doc_id else []
            all_returns.extend(rows)
            print(f"  ✅ FBA/{label}: {len(rows)} returns")
        except Exception as e:
            _errors.append(f"FBA/{label}: {str(e)[:160]}")
            print(f"  ❌ FBA/{label}: {str(e)[:160]}")
        time.sleep(2)

    print("\n── MFN returns (per marketplace) ──")
    for mp_code, mp_id in MARKETPLACES.items():
        try:
            doc_id = wait_for_report(request_report(MFN, mp_id, start_date, end_date))
            rows = _parse(MFN, download_report(doc_id), mp_code) if doc_id else []
            all_returns.extend(rows)
            print(f"  {'✅' if rows else '─'} MFN/{mp_code}: {len(rows)}")
        except Exception as e:
            _errors.append(f"MFN/{mp_code}: {str(e)[:160]}")
            print(f"  ❌ MFN/{mp_code}: {str(e)[:160]}")
        time.sleep(2)

else:
    # ─── Добор истории ───
    import zoneinfo
    _kyiv = datetime.now(zoneinfo.ZoneInfo("Europe/Kyiv"))
    QUIET_FROM, QUIET_TO = "01:00", "02:30"          # тихое окно createReport (AGENTS.md, «Квота createReport»)

    def _params():
        """reorder_params из Lakebase (там же их читают страницы и сторож); своё соединение — шаг короткий."""
        from databricks.sdk import WorkspaceClient as _WC
        import psycopg2 as _pg
        _wc = _WC()
        _conn = _pg.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_wc.current_user.me().user_name, sslmode="require",
                            password=_wc.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
        try:
            with _conn.cursor() as _pc:
                _pc.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'returns_backfill_%'")
                return {k: v for k, v in _pc.fetchall()}
        finally:
            _conn.close()

    _P = _params()

    def _param(key, default):
        v = _P.get(key)
        return default if v in (None, "") else v

    # value в reorder_params — число, поэтому дата записана как ГГГГММДД (20241101)
    _from = str(int(_param("returns_backfill_from", 20241101)))
    BACKFILL_FROM = _date(int(_from[:4]), int(_from[4:6]), int(_from[6:8]))
    MAX_REPORTS = int(_param("returns_backfill_max_reports", 5))
    # MFN-история — только там, где MFN-заказы вообще бывают: рынки, где их за год не меньше
    # returns_backfill_mfn_min_orders (20). На 19.10.2026 это ES, IT, FR, DE; у остальных единицы.
    _min_orders = int(_param("returns_backfill_mfn_min_orders", 20))
    _mfn_ids = {r[0] for r in spark.sql(f"""
        SELECT marketplace_id FROM dnipro_m.dnipro_m.raw_amazon_seller_central_get_orders
        WHERE fulfillment_channel = 'MFN' AND purchase_date >= current_date() - INTERVAL 365 DAYS
        GROUP BY marketplace_id HAVING COUNT(*) >= {_min_orders}""").collect()}
    MFN_MARKETS = [cc for cc, mid in MARKETPLACES.items() if mid in _mfn_ids]
    print(f"добор с {BACKFILL_FROM}, не больше {MAX_REPORTS} отчётов, MFN: {MFN_MARKETS}")

    if not DRY:
        spark.sql("""
            CREATE TABLE IF NOT EXISTS dnipro_m.kabinet_data.returns_backfill_progress (
                report_type STRING, source STRING, window_start DATE, window_end DATE,
                status STRING COMMENT 'done / empty', rows INT, how STRING COMMENT 'reused <reportId> / created <reportId>',
                done_at TIMESTAMP)
            USING DELTA COMMENT 'Добор истории возвратов (Kabinet - Returns Backfill): какие куски уже взяты.'
        """)
    try:
        _prog = spark.sql("SELECT report_type, source, window_start, status FROM dnipro_m.kabinet_data.returns_backfill_progress").collect()
    except Exception:
        if not DRY:
            raise
        _prog = []          # проба до первой ночи: таблицы прогресса ещё нет
    done = {(r[0], r[1], r[2]) for r in _prog if r[3] != "anchor"}
    # Конец истории запоминается ОДИН раз — строкой anchor: после первой ночи добранные строки лежат в той же таблице,
    # и «первая загруженная дата» уехала бы к началу добора — кусков бы не осталось.
    anchors = {(r[0], r[1]): r[2] for r in _prog if r[3] == "anchor"}

    # куски: FBA — по кварталу (отчёт отдаёт и девять месяцев одним документом), MFN — по 60 дней (предел отчёта).
    # Конец истории — то, что daily уже держит: первая загруженная дата минус день.
    # FBA — один источник на аккаунт («ALL»), MFN — по рынку. Нет строк — история до сегодня.
    first_daily = {}
    for rt, src, d in spark.sql("""
            SELECT raw_source, CASE WHEN fulfillment_type = 'FBA' THEN 'ALL' ELSE marketplace END,
                   MIN(return_date)
            FROM dnipro_m.kabinet_data.raw_amazon_returns
            WHERE raw_source IS NOT NULL
            GROUP BY 1, 2""").collect():
        first_daily[(rt, src)] = d

    new_anchors = []

    def _chunks(rtype, source, step_days):
        stop = anchors.get((rtype, source))
        if stop is None:
            # MFN — до начала ежедневного окна, а не до первой загруженной строки: строки до 19.10.2026 записаны с
            # количеством 1 и без причины (не те имена колонок), их надо перечитать. FBA разбирался верно.
            stop = (_date.today() - timedelta(days=LOOKBACK_DAYS)) if rtype == MFN \
                else (first_daily.get((rtype, source)) or _date.today())
            new_anchors.append((rtype, source, stop, stop, "anchor", 0, "history end"))
        cur, out = BACKFILL_FROM, []
        while cur < stop:
            end = min(cur + timedelta(days=step_days - 1), stop - timedelta(days=1))
            out.append((rtype, source, cur, end))
            cur = end + timedelta(days=1)
        return out

    todo = []
    for label, _mp in FBA_SOURCES:
        todo += _chunks(FBA, label, 92)
    for m in MFN_MARKETS:
        if m in MARKETPLACES:
            todo += _chunks(MFN, m, 60)
    todo = [c for c in todo if (c[0], c[1], c[2]) not in done]
    print(f"кусков осталось: {len(todo)}")

    # готовые отчёты, которые уже кто-то создал: кусок внутри их окна берётся без createReport
    def _listed(rtype):
        reps, token = [], None
        while True:
            params = {"nextToken": token} if token else {"reportTypes": rtype, "processingStatuses": "DONE", "pageSize": 100}
            # getReports — свой лимит (около запроса в 45 с, запас 10), к квоте createReport отношения не имеет:
            # на 429 здесь ждать можно
            for _try in range(10):
                r = requests.get(f"{SP_API_EU}/reports/2021-06-30/reports", params=params, timeout=60,
                                 headers={"x-amz-access-token": get_access_token()})
                if r.status_code != 429:
                    break
                time.sleep(60)
            r.raise_for_status()
            j = r.json(); reps += j.get("reports", []); token = j.get("nextToken")
            if not token:
                return reps
            time.sleep(3)

    listed = {FBA: _listed(FBA), MFN: _listed(MFN)}
    src_mp = dict(FBA_SOURCES) | {m: MARKETPLACES[m] for m in MFN_MARKETS if m in MARKETPLACES}

    def _covering(rtype, source, ws, we):
        mp = src_mp[source]
        for rep_ in listed[rtype]:
            # FBA — по аккаунту, годится отчёт, запрошенный по любому рынку; MFN — только по своему
            if not rep_.get("reportDocumentId") or (rtype == MFN and (rep_.get("marketplaceIds") or [None])[0] != mp):
                continue
            st, en = rep_.get("dataStartTime", "")[:10], rep_.get("dataEndTime", "")[:10]
            if st and en and st <= ws.isoformat() and en >= we.isoformat():
                return rep_
        return None

    def _in_window(row, ws, we):
        d = str(row.get("return_date") or "")[:10]
        return bool(d) and ws.isoformat() <= d <= we.isoformat()

    created, progress = 0, []
    quiet = QUIET_FROM <= _kyiv.strftime("%H:%M") < QUIET_TO and not DRY
    if not quiet:
        print(f"⏸ {_kyiv:%H:%M} по Киеву — вне тихого окна {QUIET_FROM}–{QUIET_TO}: новых отчётов не создаю, только готовые")
    for rtype, source, ws, we in todo:
        rep_ = _covering(rtype, source, ws, we)
        try:
            if rep_:
                how, doc_id = f"reused {rep_['reportId']}", rep_["reportDocumentId"]
            else:
                # окно проверяем перед КАЖДЫМ отчётом: пять отчётов по 20 минут ожидания вышли бы за 02:30
                quiet = QUIET_FROM <= datetime.now(zoneinfo.ZoneInfo("Europe/Kyiv")).strftime("%H:%M") < QUIET_TO and not DRY
                if not quiet or created >= MAX_REPORTS:
                    continue
                if _date.today() - ws > timedelta(days=730):
                    # глубже двух лет Amazon не отдаёт; помечаем, чтобы не просить каждую ночь
                    progress.append((rtype, source, ws, we, "empty", 0, "older than 2 years"))
                    continue
                created += 1
                rid = request_report(rtype, src_mp[source], ws, we, retry_429=False)
                how, doc_id = f"created {rid}", wait_for_report(rid, max_wait=1200)
            rows_doc = _parse(rtype, download_report(doc_id), source) if doc_id else []
            rows = [r for r in rows_doc if _in_window(r, ws, we)]
            if rows_doc and not rows and not any(r.get("return_date") for r in rows_doc):
                # документ есть, а дат в нём не разобрать — не помечаем кусок пустым, иначе он потерян навсегда
                raise RuntimeError(f"в документе {len(rows_doc)} строк без даты возврата — формат не разобран")
            how += f", строк в документе {len(rows_doc)}"
            all_returns.extend(rows)
            progress.append((rtype, source, ws, we, "done" if rows else "empty", len(rows), how))
            print(f"  ✅ {source} {rtype[4:20]} {ws}…{we}: {len(rows)} ({how})")
        except Quota429 as e:
            # не ошибка кода: квота занята, остаток — следующей ночью; прогон не роняем, но пишем в пульс
            _errors.append(str(e)[:200])
            print(f"  ⏸ {e} — остальное следующей ночью")
            break
        except Exception as e:
            _errors.append(f"{source} {ws}…{we}: {str(e)[:160]}")
            print(f"  ❌ {source} {ws}…{we}: {str(e)[:160]}")
        time.sleep(2)

    _left = len(todo) - len(progress)
    print(f"\nсоздано отчётов: {created}, взято кусков: {len(progress)}, осталось: {_left}")

print(f"\n── Total fetched: {len(all_returns)} return records")

# COMMAND ----------

# DBTITLE 1,MERGE into UC + stats
# ─── Resolve marketplace for FBA returns + MERGE ───
# FBA Pan-EU возвращает все EU-возвраты без привязки к MP.
# Определяем MP по order_id из raw_amazon_seller_central_get_orders.

# Reverse map: marketplace_id -> code
MP_ID_TO_CODE = {v: k for k, v in MARKETPLACES.items()}

if not all_returns and MODE == "daily" and not _errors:
    raise RuntimeError("❌ 0 returns fetched across all marketplaces — job forced to FAIL.")
elif not all_returns:
    print("строк нет — записывать нечего" + (f" (сбоев: {len(_errors)})" if _errors else ""))
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
        # Заказы у нас с марта 2026, а история возвратов глубже: вторым источником рынка — возврат денег Finances
        # (страна заказа, с декабря 2024). Порядок: сперва заказ, потом Finances.
        fin_mp = spark.sql("""
            SELECT order_id AS _oid, MAX(upper(country)) AS mp_fin
            FROM dnipro_m.dnipro_m.v_amazon_finances_transactions_current
            WHERE transaction_type = 'Refund' AND order_id IS NOT NULL
            GROUP BY order_id
        """)
        orders_mp = (orders_mp.join(fin_mp, "_oid", "full")
                     .select("_oid", F.coalesce("mp_code", "mp_fin").alias("mp_code")))

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

    if DRY:
        _sum = [r.asDict() for r in spark.sql("""
            SELECT fulfillment_type, marketplace, date_format(return_date, 'yyyy-MM') AS month,
                   COUNT(*) AS rows, SUM(quantity) AS units, COUNT(return_reason) AS with_reason
            FROM _returns_staging GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").collect()]
        _out = {"progress": [[str(x) for x in p_] for p_ in progress], "left": _left,
                "errors": _errors, "staging": _sum}
        print(json.dumps(_out, ensure_ascii=False, default=str)[:20000])
        dbutils.notebook.exit(json.dumps(_out, ensure_ascii=False, default=str)[:60000])

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

if DRY:   # проба без строк: выходим до любой записи
    dbutils.notebook.exit(json.dumps({"progress": [[str(x) for x in p_] for p_ in progress], "left": _left,
                                      "errors": _errors, "staging": []}, ensure_ascii=False))

# Прогресс добора — только после MERGE: кусок, не дошедший до таблицы, не должен считаться взятым.
if MODE == "backfill" and (progress or new_anchors):
    _pschema = "report_type STRING, source STRING, window_start DATE, window_end DATE, status STRING, rows INT, how STRING"
    (spark.createDataFrame(new_anchors + progress, _pschema)
          .withColumn("done_at", F.current_timestamp())
          .write.mode("append").saveAsTable("dnipro_m.kabinet_data.returns_backfill_progress"))
    print(f"прогресс добора: +{len(progress)} кусков, якорей {len(new_anchors)}")

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
    user=w.current_user.me().user_name, password=cred.token, sslmode="require")
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
    VALUES (%s, now(), %s)
    ON CONFLICT (job_name) DO UPDATE SET
        last_success_at = now(), note = EXCLUDED.note
""", (PULSE_NAME,
      f"{len(rows) if returns_df else 0} returns synced"
      + (f"; добор: осталось кусков {_left}" if MODE == "backfill" else "")
      + (f"; сбои: {' | '.join(_errors)[:400]}" if _errors else "")))
pg_conn.commit()
pg_conn.close()
print(f"✅ System pulse записан ({PULSE_NAME})")

# Сбой отчёта — красным, но после пульса: иначе упавший рынок выглядел бы мёртвым загрузчиком.
# 429 в доборе — не сбой: квота занята, кусок возьмёт следующая ночь (в пульсе он записан).
_real = [e for e in _errors if not (MODE == "backfill" and e.startswith("[QUOTA_429]"))]
if _real:
    _q = " [QUOTA_429]" if any("[QUOTA_429]" in e for e in _real) else ""
    raise RuntimeError(f"Returns Loader{_q}: сбоев {len(_real)}: " + " | ".join(_real)[:900])

pg_conn.close()