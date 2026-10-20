# Databricks notebook source
# DBTITLE 1,Kabinet - Amazon Run Check: прогоны джоб Amazon API — успех, запись в таблицы, 429
# Kabinet - Amazon Run Check (19.10.2026, решение владельца: «закрываем тему квоты»), раз в час, под владельцем —
# ему видны история таблиц и вывод прогонов всех джоб, в том числе Дарины (только чтение).
#
# По каждой джобе из kabinet_data.amazon_api_jobs (наши, Дарины, Listing Suite) берёт новые завершённые прогоны и пишет
# строку в kabinet_data.amazon_run_checks: состояние, была ли запись в её таблицы (Unity Catalog или Lakebase), сколько
# 429 в выводе.
# Amazon не вызывает вовсе — квоты не трогает. Запись — по истории изменений таблиц (DESCRIBE HISTORY: коммит с
# job.jobId этой джобы во время прогона). Lineage UC для этого не годится: 19.10.2026 он не знал записей Ledger Summary
# 16:27 и FBA Shipments 15:31, которые в истории таблиц есть, — дал бы ложные тревоги. Из lineage взят только СПИСОК
# таблиц джобы (amazon_api_jobs.tables, 14 дней) — его хватает: достаточно одной таблицы с коммитом. С 20.10.2026 — и
# Lakebase (amazon_api_jobs.pg_db / pg_table / pg_ts_col): строка с временем внутри прогона или снимок за его день; база
# Listing Suite — отдельным подключением, только чтение.
#
# «Зелёная, но без записи»: два ПОДРЯД успешных прогона без единой записи в таблицы UC — тревога silent_success
# [SILENT:<джоба>] (high). Одного мало: у ежедневной джобы бывает день без новых данных. У джоб, которые законно пишут
# не каждый прогон (Settlements, SQP), — amazon_api_jobs.quiet_days: тревога, если за столько дней ни одной записи
# при двух и более успешных прогонах. Закрывается сама, когда
# очередной успешный прогон записал. Джобы из kabinet_data.source_job_checks (Ledger Summary) тревоги отсюда не получают:
# их уже после первого такого прогона проверяет Self-Heal — тревога source_silent_fail и один перезапуск. Проверка
# записи — только у джоб с check_write: Auth Guard (писать нечего), паузы и доборы — без неё, только состояние и 429.
# Для джоб Дарины — только чтение и тревога, никаких перезапусков (перезапуск её Amazon-джоб делает Power BI Self-Heal).
#
# Прогон проверяется не раньше reorder_params.amazon_check_lag_min (15) после конца — даём лечь последнему коммиту.
# dry_run=1 — без записи: печатает, что записал бы. since_hours — окно первого прогона (по умолчанию 72).
# Источник кода — nb/amazon_run_check.py в kabinet-dashboard.

# COMMAND ----------

import base64, json, re, urllib.parse
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import ViewsToExport

JOB_NAME = "Kabinet - Amazon Run Check"
KYIV = ZoneInfo("Europe/Kyiv")
w = WorkspaceClient()
for _n, _d in (("dry_run", "0"), ("since_hours", "72"), ("registry_json", "")):
    try:
        dbutils.widgets.text(_n, _d)  # noqa: F821
    except Exception:
        pass
def _wg(n, d):
    try:
        return (dbutils.widgets.get(n) or d).strip()  # noqa: F821
    except Exception:
        return d
DRY = _wg("dry_run", "0") == "1"
SINCE_H = int(_wg("since_hours", "72"))
now = dt.datetime.now(dt.timezone.utc)
_errors = []


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def pg_ls():
    """База Listing Suite (listing_data.*) — только чтение для проверки записи."""
    cred = w.postgres.generate_database_credential(endpoint="projects/listing-suite/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-little-lab-d24nnmco.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def kyiv(ms_or_dt, fmt="%d.%m %H:%M"):
    d = dt.datetime.fromtimestamp(ms_or_dt / 1000, dt.timezone.utc) if isinstance(ms_or_dt, (int, float)) else ms_or_dt
    return d.astimezone(KYIV).strftime(fmt)


def clean(txt, n=160):
    txt = re.sub(r"bot\d+:[\w-]+", "bot<токен>", str(txt))
    txt = re.sub(r"(https?://[^\s?]+)\?\S*", r"\1?…", txt)
    return " ".join(txt.split())[:n]


# Один отказ — одно совпадение, по формату самих джоб (слово QuotaExceeded есть и в строке попытки, и в теле ответа —
# считать его как есть значит вдвое больше отказов). Ложные «429» (счётчики, «429 заказов») сюда не попадают.
C429 = re.compile(r"попытка \d+: QuotaExceeded|\[429\]|создания отчёта: 429|HTTP 429|429 на createReport|\[QUOTA_429\]"
                  r"|квот\w*[^\n]{0,60}\(429\)|\b429\b:\s*\{", re.I)


def kind_of(txt):
    if re.search(r"dataKiosk|Data Kiosk", txt, re.I): return "Data Kiosk"
    if re.search(r"reports/2021-06-30|createReport|create_report|QUOTA_429|создания отчёта", txt, re.I): return "createReport"
    if re.search(r"advertising|Throttled|\[429\] ждём", txt, re.I): return "Ads API"
    return "SP-API"


def run_output_text(task_run_id, failed):
    """Текст ошибки (упавший) или вывод ячеек без кода (успешный)."""
    if failed:
        o = w.jobs.get_run_output(run_id=task_run_id)
        return o.error or ""
    out = []
    for v in (w.jobs.export_run(task_run_id, views_to_export=ViewsToExport.CODE).views or []):
        m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", v.content or "")
        if not m:
            continue
        model = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
        out += [json.dumps(c.get("results"), ensure_ascii=False) for c in model.get("commands", []) if c.get("results")]
    return " ".join(out)


# ── реестр, настройки, что уже проверено ──
# registry_json — только для пробы до создания таблиц (dry_run): реестр списком, без чтения amazon_api_jobs
_REG = _wg("registry_json", "")
assert not (_REG and not DRY), "registry_json — только с dry_run=1"
with pg() as c, c.cursor() as cur:
    if _REG:
        JOBS = [dict(zip(("job_id", "job_name", "owner", "check_write", "tables", "pg_db", "pg_table", "pg_ts_col", "quiet_days"), list(r) + [None] * 4)) for r in json.loads(_REG)]
    else:
        cur.execute("""SELECT job_id, job_name, owner, check_write, tables, pg_db, pg_table, pg_ts_col, quiet_days
                       FROM kabinet_data.amazon_api_jobs WHERE is_active""")
        JOBS = [dict(zip(("job_id", "job_name", "owner", "check_write", "tables", "pg_db", "pg_table", "pg_ts_col", "quiet_days"), r)) for r in cur.fetchall()]
    cur.execute("SELECT job_id FROM kabinet_data.source_job_checks WHERE is_active")
    SELF_HEAL = {int(r[0]) for r in cur.fetchall()}      # их «без записи» ведёт Self-Heal — здесь только строка прогона
    cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'amazon_check_lag_min'")
    _r = cur.fetchone()
    LAG = dt.timedelta(minutes=float(_r[0]) if _r else 15)
    try:
        cur.execute("SELECT run_id FROM kabinet_data.amazon_run_checks WHERE ended_at >= now() - interval '10 days'")
        DONE = {int(r[0]) for r in cur.fetchall()}
    except Exception:
        if not DRY:
            raise
        c.rollback(); DONE = set()          # проба до создания таблицы результатов
print(f"джоб в реестре: {len(JOBS)}; уже проверено прогонов за 10 дней: {len(DONE)}; задержка {LAG}")

# ── прогоны к проверке ──
since_ms = int((now - dt.timedelta(hours=SINCE_H)).timestamp() * 1000)
todo = []
for J in JOBS:
    try:
        for r in w.jobs.list_runs(job_id=J["job_id"], start_time_from=since_ms, expand_tasks=True, completed_only=True):
            if r.run_id in DONE or not r.end_time:
                continue
            if dt.datetime.fromtimestamp(r.end_time / 1000, dt.timezone.utc) > now - LAG:
                continue                     # последний коммит мог ещё не лечь — проверим следующим часом
            todo.append((J, r))
    except Exception as e:
        _errors.append(f"прогоны {J['job_name']}: {type(e).__name__}: {clean(e)}")
print(f"прогонов к проверке: {len(todo)}")

# ── история таблиц: какие прогоны записали (кеш на таблицу) ──
WRITE_OPS = ("WRITE", "MERGE", "UPDATE", "DELETE", "CREATE OR REPLACE TABLE", "REPLACE TABLE", "CREATE TABLE AS SELECT",
             "COPY INTO", "STREAMING UPDATE")
_HIST = {}


def commits(table):
    """[(время UTC, job_id)] коммитов записи в таблицу; None — история не прочиталась."""
    if table not in _HIST:
        try:
            out = []
            for h in spark.sql(f"DESCRIBE HISTORY {table} LIMIT 500").collect():  # noqa: F821
                ts = h["timestamp"].replace(tzinfo=dt.timezone.utc) if h["timestamp"].tzinfo is None else h["timestamp"]
                if any(str(h["operation"]).startswith(op) for op in WRITE_OPS):
                    out.append((ts, str(h["job"]["jobId"]) if h["job"] and h["job"]["jobId"] else ""))
            _HIST[table] = out
        except Exception as e:
            _errors.append(f"история {table}: {type(e).__name__}: {clean(e)}")
            _HIST[table] = None
    return _HIST[table]


# ── Lakebase: была ли строка с временем записи внутри прогона (с 20.10.2026 — джобы, которые пишут не в UC) ──
# pg_ts_col типа date (снимок за день) сравнивается с датой начала прогона по Киеву, timestamp — с окном прогона.
_PGC, _PGT = {}, {}


def pg_wrote(db, table, col, st, en):
    """True/False — была ли запись; None — не прочиталось (сбой — в _errors)."""
    try:
        if db not in _PGC:
            _PGC[db] = pg_ls() if db == "listing" else pg()
            _PGC[db].set_session(readonly=True, autocommit=True)
        with _PGC[db].cursor() as cur:
            if (db, table, col) not in _PGT:
                sch, tb = table.split(".", 1)
                cur.execute("""SELECT data_type FROM information_schema.columns
                               WHERE table_schema = %s AND table_name = %s AND column_name = %s""", (sch, tb, col))
                _r = cur.fetchone()
                if not _r:
                    raise ValueError(f"нет колонки {table}.{col}")
                _PGT[(db, table, col)] = _r[0]
            if _PGT[(db, table, col)] == "date":
                cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {col} = (%s AT TIME ZONE 'Europe/Kyiv')::date)",
                            (st,))
            else:
                cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {col} BETWEEN %s AND %s)",
                            (st, en + dt.timedelta(minutes=5)))
            return bool(cur.fetchone()[0])
    except Exception as e:
        _errors.append(f"Lakebase {db}:{table}: {type(e).__name__}: {clean(e)}")
        _bad = _PGC.pop(db, None)                     # следующая проверка откроет новое соединение
        if _bad is not None:
            try:
                _bad.close()
            except Exception:
                pass
        return None


rows = []
UNREAD = [0]
for J, r in todo:
    state = r.state.result_state.value if r.state and r.state.result_state else (r.state.life_cycle_state.value if r.state else "?")
    failed = state != "SUCCESS"
    st = dt.datetime.fromtimestamp(r.start_time / 1000, dt.timezone.utc)
    en = dt.datetime.fromtimestamp(r.end_time / 1000, dt.timezone.utc)
    wrote, tables = None, None
    if J["check_write"] and (J["tables"] or J.get("pg_table")) and not failed:
        hits, unknown = [], False
        for tb in J["tables"] or []:
            cm = commits(tb)
            if cm is None:
                unknown = True
                continue
            if any(jid == str(J["job_id"]) and st <= ts <= en + dt.timedelta(minutes=5) for ts, jid in cm):
                hits.append(tb.split(".")[-1])
        if J.get("pg_table"):
            _pw = pg_wrote(J.get("pg_db") or "kabinet", J["pg_table"], J["pg_ts_col"], st, en)
            if _pw:
                hits.append(J["pg_table"].split(".")[-1])
            elif _pw is None:
                unknown = True
        # история хоть одной таблицы не прочиталась и записей не нашли — «не знаем», а не «не писал»
        wrote = True if hits else (None if unknown else False)
        tables = ", ".join(hits)[:1000] or None
    n429, kinds = 0, set()
    try:
        for t in r.tasks or []:
            txt = run_output_text(t.run_id, failed)
            for m in C429.finditer(txt):
                n429 += 1
                kinds.add(kind_of(txt[max(0, m.start() - 160): m.end() + 160]))
    except Exception as e:
        if "permission" in (type(e).__name__ + str(e)).lower():
            UNREAD[0] += 1               # вывод временного ноутбука прогона без прав на просмотр — 429 не посчитать
            n429 = None
        else:
            _errors.append(f"вывод {J['job_name']} {kyiv(r.start_time)}: {type(e).__name__}: {clean(e)}")
    rows.append((r.run_id, J["job_id"], J["job_name"], J["owner"], st, en, state, wrote, tables, n429,
                 ", ".join(sorted(kinds)) or None))

for _cn in _PGC.values():
    try:
        _cn.close()
    except Exception:
        pass
print(f"проверено: {len(rows)}; без записи: {sum(1 for x in rows if x[7] is False)}; с 429: {sum(1 for x in rows if x[9])}")
for x in rows:
    if x[7] is False or x[9]:
        print(f"  {x[2]} {kyiv(x[4])} {x[6]} записал={x[7]} 429={x[9]} ({x[10]})")

if DRY:
    dbutils.notebook.exit(json.dumps({  # noqa: F821
        "checked": len(rows), "errors": _errors, "unread": UNREAD[0],
        "rows": [[x[2], kyiv(x[4]), x[6], x[7], x[9], x[10]] for x in rows]}, ensure_ascii=False, default=str))

# ── запись результатов (своё соединение: шаг короткий) ──
try:
    with pg() as c, c.cursor() as cur:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO kabinet_data.amazon_run_checks
                (run_id, job_id, job_name, owner, started_at, ended_at, state, wrote, tables, n429, kinds_429, checked_at)
            VALUES %s ON CONFLICT (run_id) DO NOTHING""",
            [x + (now,) for x in rows], page_size=500)
except Exception as e:
    _errors.append(f"запись результатов: {type(e).__name__}: {clean(e)}")

# ── тревоги «зелёная, но без записи»: два подряд успешных прогона без записи; у джоб с quiet_days (законно пишут не
# каждый прогон: Settlements, SQP) — ни одной записи за quiet_days дней при двух и более успешных прогонах; окно
# истории — 15 дней, поэтому quiet_days не больше 14 (CHECK в amazon_api_jobs) ──
QUIET = {J["job_name"]: int(J["quiet_days"]) for J in JOBS if J.get("quiet_days")}
silent = {}
try:
    with pg() as c, c.cursor() as cur:
        cur.execute("""
            WITH s AS (SELECT job_id, job_name, owner, started_at, wrote,
                              row_number() OVER (PARTITION BY job_id ORDER BY started_at DESC) AS rn
                       FROM kabinet_data.amazon_run_checks
                       WHERE state = 'SUCCESS' AND wrote IS NOT NULL AND started_at >= now() - interval '15 days')
            SELECT job_id, job_name, owner, bool_or(wrote) FILTER (WHERE rn = 1) AS last_wrote,
                   count(*) FILTER (WHERE rn <= 2 AND NOT wrote) AS no_write_2,
                   max(started_at) FILTER (WHERE rn = 1), max(started_at) FILTER (WHERE rn = 2),
                   max(started_at) FILTER (WHERE wrote) AS last_true, min(started_at) AS first_ck
            FROM s GROUP BY 1, 2, 3""")
        _seen = set()
        for jid, name, owner, last_wrote, no2, t1, t2, last_true, first_ck in cur.fetchall():
            _seen.add(name)
            if int(jid) in SELF_HEAL:
                continue
            if name in QUIET:
                ref = last_true or first_ck           # с последней записи; записи не было — с первого проверенного
                cur.execute("""SELECT count(*) FROM kabinet_data.amazon_run_checks
                               WHERE job_id = %s AND state = 'SUCCESS' AND wrote IS NOT NULL AND started_at > %s""",
                            (jid, ref))
                _n_after = cur.fetchone()[0]
                if now - ref > dt.timedelta(days=QUIET[name]) and _n_after >= 2:
                    silent[name] = (owner, ref, None)
                    continue
                last_wrote = bool(last_true and now - last_true <= dt.timedelta(days=QUIET[name]))
                if not last_wrote:
                    continue
            elif no2 == 2:
                silent[name] = (owner, t1, t2)
                continue
            if last_wrote:
                cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                                      resolved_by = 'watchdog-autoclose: прогон записал таблицы'
                               WHERE incident_type = 'silent_success' AND source = 'amazon_run_check'
                                 AND message LIKE %s AND resolved_at IS NULL""", (f"[SILENT:{name}]%",))
        # джоба выпала из проверки (убрана из реестра, check_write = false, ушла в Self-Heal, 15 дней без прогонов) —
        # её тревога сама уже не закроется: закрываем здесь
        _eligible = {J["job_name"] for J in JOBS
                     if J["check_write"] and (J["tables"] or J.get("pg_table")) and int(J["job_id"]) not in SELF_HEAL}
        cur.execute("""SELECT id, substring(message from '^\\[SILENT:([^\\]]+)\\]') FROM kabinet_data.incidents
                       WHERE incident_type = 'silent_success' AND source = 'amazon_run_check' AND resolved_at IS NULL""")
        for _iid, _nm in cur.fetchall():
            if _nm not in silent and (_nm not in _eligible or _nm not in _seen):
                cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                                      resolved_by = 'watchdog-autoclose: джоба больше не проверяется на запись'
                               WHERE id = %s""", (_iid,))
        for name, (owner, t1, t2) in silent.items():
            whose = {"darina": " Джоба витрины Power BI — только сообщаем, не перезапускаем.",
                     "listing_suite": " Джоба Listing Suite."}.get(owner, "")
            if t2 is None:                           # правило quiet_days
                msg = (f"[SILENT:{name}] больше {QUIET[name]} дн. без записи: после {kyiv(t1)} ни один успешный прогон не "
                       f"записал данные (ни коммита в таблицы Unity Catalog, ни строки в Lakebase во время прогона), хотя "
                       f"обычно пишет хотя бы раз за этот срок — смотреть вывод прогонов (429, пустой ответ, пропуск в "
                       f"try).{whose}")
            else:
                msg = (f"[SILENT:{name}] два успешных прогона подряд ({kyiv(t2)} и {kyiv(t1)}) не записали данные (ни "
                       f"коммита в таблицы Unity Catalog, ни строки в Lakebase во время прогона) — смотреть вывод прогона "
                       f"(429, пустой ответ, пропуск в try).{whose}")
            cur.execute("""SELECT id FROM kabinet_data.incidents WHERE incident_type = 'silent_success'
                           AND source = 'amazon_run_check' AND message LIKE %s AND resolved_at IS NULL LIMIT 1""",
                        (f"[SILENT:{name}]%",))
            _row = cur.fetchone()
            if _row:
                cur.execute("UPDATE kabinet_data.incidents SET message = %s WHERE id = %s", (msg, _row[0]))
            else:
                cur.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, created_at, source)
                               VALUES ('silent_success', 'high', %s, 'open', now(), 'amazon_run_check')""", (msg,))
except Exception as e:
    _errors.append(f"тревоги: {type(e).__name__}: {clean(e)}")

# ── пульс — последним и безусловно; сбои — после него ──
note = (f"прогонов {len(rows)}, без записи {sum(1 for x in rows if x[7] is False)}, с 429 {sum(1 for x in rows if x[9])}; "
        f"тревог silent {len(silent)}" + (f"; вывод не прочитан у {UNREAD[0]}" if UNREAD[0] else "") + (f"; сбои: {' | '.join(_errors)[:400]}" if _errors else ""))
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 2)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (JOB_NAME, note))
print(f"💓 {JOB_NAME}: {note}")
if _errors:
    raise RuntimeError(f"{JOB_NAME}: сбоев {len(_errors)}: " + " | ".join(_errors)[:900])
