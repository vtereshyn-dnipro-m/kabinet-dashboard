# Databricks notebook source
# DBTITLE 1,Kabinet - Amazon API Journal: журнал getReports и Data Kiosk getQueries
# Kabinet - Amazon API Journal (21.10.2026, решение владельца: «журнал getReports/getQueries», пункт 4 плана «закрываем
# тему квоты»), раз в час в :40, под владельцем.
#
# Что видно в Amazon, а не в наших джобах: какие отчёты SP-API и запросы Data Kiosk созданы на аккаунте продавца, кем бы
# ни были созданы — нашими джобами, Дарины или Listing Suite, — когда и сколько шли и чем кончились. Квота createReport
# общая на аккаунт, а 429 одной джобы — это чужие отчёты в ту же минуту; без журнала «кто занимал квоту» не узнать.
#
# Только чтение у Amazon: getReports (`GET /reports/2021-06-30/reports`) и getQueries (`GET /dataKiosk/.../queries`).
# createReport и createQuery НЕ вызываются — квоту создания не трогаем. У getReports свой лимит (0,0222 запроса в
# секунду, запас 10): за прогон 2–8 запросов, по 3 с между ними; на 429 НЕ повторяем — окно с перекрытием, следующий
# час доберёт. getReports требует список типов: он в kabinet_data.amazon_report_types (новый тип — строкой туда).
#
# Пишет kabinet_data.amazon_report_log (отчёт — строка, статус обновляется: IN_QUEUE → IN_PROGRESS → DONE/FATAL/
# CANCELLED) и amazon_dk_query_log (запрос Data Kiosk — строка). Чья это джоба, Amazon не говорит — сопоставление по
# времени и типу делает экран «Amazon API», не журнал. Окно — каждый прогон целиком за reorder_params.
# amazon_journal_window_h (26 ч): так отчёт, который шёл дольше часа, и группа типов, получившая 429 в прошлый час, не
# теряются, а статусы дозревают сами (проба 21.10: 6 запросов за прогон — в пределах лимита). Пульс — последним, сбои —
# падение после пульса.
# dry_run=1 — без записи: печатает, что записал бы. Источник кода — nb/amazon_api_journal.py в kabinet-dashboard.

# COMMAND ----------

import json, re, time
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, psycopg2.extras, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Amazon API Journal"
KYIV = ZoneInfo("Europe/Kyiv")
SP = "https://sellingpartnerapi-eu.amazon.com"
w = WorkspaceClient()
try:
    dbutils.widgets.text("dry_run", "0")  # noqa: F821
    dbutils.widgets.text("types_json", "")  # noqa: F821
    DRY = (dbutils.widgets.get("dry_run") or "0").strip() == "1"  # noqa: F821
    _TYPES_JSON = (dbutils.widgets.get("types_json") or "").strip()  # noqa: F821
except Exception:
    DRY, _TYPES_JSON = False, ""
# types_json — только для пробы до создания таблиц (dry_run): список типов параметром
assert not (_TYPES_JSON and not DRY), "types_json — только с dry_run=1"
now = dt.datetime.now(dt.timezone.utc)
_errors = []


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def clean(e):
    """Текст ошибки без токенов и query-строк URL."""
    t = re.sub(r"(Atza\|[\w-]+|Atzr\|[\w-]+)", "<токен>", str(e))
    return re.sub(r"\?[^\s'\"]+", "?…", t)[:300]


def ts(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


# ── настройки и окно ──
with pg() as c, c.cursor() as cur:
    cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'amazon_journal_window_h'")
    _r = cur.fetchone()
    if _r is None and not _TYPES_JSON:
        _errors.append("нет reorder_params.amazon_journal_window_h — окно 26 ч")
    WINDOW = dt.timedelta(hours=float(_r[0]) if _r else 26)
    if _TYPES_JSON:                       # проба до создания таблиц
        TYPES = sorted(json.loads(_TYPES_JSON))
    else:
        cur.execute("SELECT report_type FROM kabinet_data.amazon_report_types WHERE is_active ORDER BY 1")
        TYPES = [r[0] for r in cur.fetchall()]
since_rep = since_dk = now - WINDOW
print(f"типов отчётов: {len(TYPES)}; окно отчётов с {since_rep:%d.%m %H:%M} UTC, Data Kiosk с {since_dk:%d.%m %H:%M} UTC")

# ── токен LWA ──
_tok = None
try:
    _lwa = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token",
        "refresh_token": dbutils.secrets.get("amazon-sp-api", "refresh-token"),  # noqa: F821
        "client_id": dbutils.secrets.get("amazon-sp-api", "lwa-app-id"),  # noqa: F821
        "client_secret": dbutils.secrets.get("amazon-sp-api", "lwa-client-secret")}, timeout=30)  # noqa: F821
    _lwa.raise_for_status()
    _tok = _lwa.json()["access_token"]
except Exception as e:
    _errors.append(f"LWA: {type(e).__name__}: {clean(e)}")
H = {"x-amz-access-token": _tok or ""}
calls, q429 = [0], [0]


def get(path, params):
    """Один GET. 429 — не повторяем (None и пометка): окно с перекрытием, доберёт следующий час."""
    if calls[0]:
        time.sleep(3)                    # getReports / getQueries: 0,0222 запроса в секунду, запас 10
    calls[0] += 1
    r = requests.get(SP + path, headers=H, params=params, timeout=60)
    if r.status_code == 429:
        q429[0] += 1
        return None
    r.raise_for_status()
    return r.json()


# ── getReports: по 10 типов за запрос, со страницами ──
reports = {}
if _tok:
    for i in range(0, len(TYPES), 10):
        prm = {"reportTypes": ",".join(TYPES[i:i + 10]), "pageSize": 100,
               "createdSince": since_rep.strftime("%Y-%m-%dT%H:%M:%SZ")}
        try:
            while True:
                js = get("/reports/2021-06-30/reports", prm)
                if js is None:
                    break
                for rp in js.get("reports", []):
                    reports[rp["reportId"]] = rp
                nxt = js.get("nextToken")
                if not nxt:
                    break
                prm = {"nextToken": nxt}
        except Exception as e:
            _errors.append(f"getReports {i // 10 + 1}: {type(e).__name__}: {clean(e)}")

# ── getQueries Data Kiosk ──
queries = {}
if _tok:
    prm = {"pageSize": 100, "createdSince": since_dk.strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        while True:
            js = get("/dataKiosk/2023-11-15/queries", prm)
            if js is None:
                break
            for qq in js.get("queries", []):
                queries[qq["queryId"]] = qq
            nxt = (js.get("pagination") or {}).get("nextToken")
            if not nxt:
                break
            # у getQueries, в отличие от getReports, со следующей страницей передаются и прежние параметры
            prm = {"pageSize": 100, "createdSince": since_dk.strftime("%Y-%m-%dT%H:%M:%SZ"), "paginationToken": nxt}
    except Exception as e:
        _errors.append(f"getQueries: {type(e).__name__}: {clean(e)}")


def schema_of(q):
    """Набор Data Kiosk из текста запроса: «analytics_salesAndTraffic_2024_04_24» — без самого запроса."""
    m = re.search(r"\b(analytics_\w+?_\d{4}_\d{2}_\d{2})\b", q or "")
    return m.group(1) if m else None


rep_rows = [(rid, rp.get("reportType"), rp.get("processingStatus"), ts(rp.get("createdTime")),
             ts(rp.get("processingStartTime")), ts(rp.get("processingEndTime")),
             ",".join(rp.get("marketplaceIds") or []) or None, ts(rp.get("dataStartTime")), ts(rp.get("dataEndTime")),
             rp.get("reportScheduleId"), now) for rid, rp in reports.items()]
dk_rows = [(qid, qq.get("processingStatus"), ts(qq.get("createdTime")), ts(qq.get("processingStartTime")),
            ts(qq.get("processingEndTime")), schema_of(qq.get("query")), now) for qid, qq in queries.items()]
print(f"отчётов: {len(rep_rows)}, запросов Data Kiosk: {len(dk_rows)}, вызовов: {calls[0]}, 429: {q429[0]}")

if DRY:
    by_type = {}
    for x in rep_rows:
        by_type[x[1]] = by_type.get(x[1], 0) + 1
    dbutils.notebook.exit(json.dumps({  # noqa: F821
        "reports": len(rep_rows), "dk_queries": len(dk_rows), "calls": calls[0], "q429": q429[0], "errors": _errors,
        "by_type": by_type, "dk_by_schema": {s: sum(1 for x in dk_rows if x[5] == s) for s in {x[5] for x in dk_rows}}},
        ensure_ascii=False))

# ── запись (своё соединение: шаг короткий); статус отчёта обновляется ──
try:
    with pg() as c, c.cursor() as cur:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.amazon_report_log
                (report_id, report_type, processing_status, created_time, processing_start, processing_end,
                 marketplace_ids, data_start, data_end, schedule_id, seen_at)
            VALUES %s
            ON CONFLICT (report_id) DO UPDATE SET processing_status = EXCLUDED.processing_status,
                processing_start = EXCLUDED.processing_start, processing_end = EXCLUDED.processing_end,
                seen_at = EXCLUDED.seen_at""", rep_rows, page_size=500)
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.amazon_dk_query_log
                (query_id, processing_status, created_time, processing_start, processing_end, dataset, seen_at)
            VALUES %s
            ON CONFLICT (query_id) DO UPDATE SET processing_status = EXCLUDED.processing_status,
                processing_start = EXCLUDED.processing_start, processing_end = EXCLUDED.processing_end,
                seen_at = EXCLUDED.seen_at""", dk_rows, page_size=500)
except Exception as e:
    _errors.append(f"запись: {type(e).__name__}: {clean(e)}")

# ── пульс — последним и безусловно; сбои — после него. 429 — не сбой: следующий час доберёт ──
note = (f"отчётов {len(rep_rows)}, запросов Data Kiosk {len(dk_rows)}, вызовов {calls[0]}"
        + (f", 429 ×{q429[0]} — доберёт следующий час" if q429[0] else "")
        + (f"; сбои: {' | '.join(_errors)[:400]}" if _errors else ""))
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 3)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (JOB_NAME, note))
print(f"💓 {JOB_NAME}: {note}")
if _errors:
    raise RuntimeError(f"{JOB_NAME}: сбоев {len(_errors)}: " + " | ".join(_errors)[:900])
