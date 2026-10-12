# Databricks notebook source
# DBTITLE 1,Kabinet - Job Schedule Snapshot: расписание джоб, зависимости, изменения
# Kabinet - Job Schedule Snapshot (с 12.10.2026, «Паспорт данных» → вкладка «Расписание»).
#
# Раз в час снимает со всего воркспейса: расписание каждой джобы, её прогоны за 14 дней (длительность по каждому
# запуску дня отдельно — у утреннего и вечернего прогона одной джобы она разная), какие таблицы джоба пишет и читает
# (по коду её ноутбука и по определениям вьюх), и историю расписаний из журнала аудита. Отсюда — зависимости
# «наша джоба ждёт источник»: наша читает таблицу, источник её пишет; запас = наш старт − конец источника.
#
# Только чтение чужих джоб. Идёт под владельцем: только он видит все джобы и журнал аудита.
# Сообщение в Telegram — только когда у источника сменилось расписание И это задевает наши джобы; «порядок нарушен»
# ведёт сторож (тревога schedule_order, красный блок).
#
# Локальный прогон (без Databricks): SCHEDULE_SNAPSHOT_JSON=путь python job_schedule_snapshot.py — результат пишется
# в JSON, база и Telegram не трогаются. Параметр dry_run=1 в джобе — то же, но печать вместо записи.

# COMMAND ----------

# DBTITLE 1,1. Снимок
import base64, json, os, re, statistics, urllib.parse
import datetime as dt
from zoneinfo import ZoneInfo

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import ViewsToExport
from databricks.sdk.service.workspace import ExportFormat

KYIV = ZoneInfo("Europe/Kyiv")
IN_DATABRICKS = "DATABRICKS_RUNTIME_VERSION" in os.environ
LOCAL_OUT = os.environ.get("SCHEDULE_SNAPSHOT_JSON")
try:
    dbutils.widgets.text("dry_run", "0")  # noqa: F821
    DRY = dbutils.widgets.get("dry_run") == "1"  # noqa: F821
except NameError:
    DRY = True
WAREHOUSE = "4324e4ac3ee7fbf8"
RUNS_DAYS = 14
AUDIT_DAYS = 90            # глубина поиска «было» для первого изменения в окне
SHOW_CHANGES_DAYS = 30     # что храним и показываем
SLOT_MATCH_MIN = 25        # прогон относится к запуску расписания, если стартовал в пределах стольких минут
SCHEMAS = ("dnipro_m", "kabinet", "kabinet_data")

w = WorkspaceClient()
now = dt.datetime.now(dt.timezone.utc)


def uc(sql):
    """SQL по Unity Catalog: в джобе — spark, локально — SQL warehouse."""
    if IN_DATABRICKS:
        return [r.asDict() for r in spark.sql(sql).collect()]  # noqa: F821
    res = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    cols = [c.name for c in res.manifest.schema.columns]
    rows, chunk = [], res.result
    while chunk is not None:
        rows += [dict(zip(cols, r)) for r in (chunk.data_array or [])]
        nxt = chunk.next_chunk_index
        chunk = (w.statement_execution.get_statement_result_chunk_n(res.statement_id, nxt) if nxt else None)
    return rows


def pg_connect():
    import psycopg2
    if IN_DATABRICKS:
        cred = w.postgres.generate_database_credential(
            endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
        return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                                port=5432, dbname="databricks_postgres", user=w.current_user.me().user_name,
                                password=cred.token, sslmode="require")
    return psycopg2.connect(os.environ["LAKEBASE_DSN"])


# ── расписание: Quartz → запуски дня по Киеву ────────────────────────────────────────────────────────────────────
_DOW = {"SUN": 1, "MON": 2, "TUE": 3, "WED": 4, "THU": 5, "FRI": 6, "SAT": 7}


def _expand(field, lo, hi, names=None):
    out = set()
    for part in field.split(","):
        part = part.strip().upper()
        if names:
            for k, v in names.items():
                part = part.replace(k, str(v))
        step = 1
        if "/" in part:
            part, step = part.split("/")
            step = int(step)
        if part in ("*", "?", ""):
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-"))
        else:
            a = b = int(part)
            if step > 1:
                b = hi
        out.update(range(a, b + 1, step))
    return sorted(out)


def quartz_slots(cron, tz):
    """[(HH:MM по Киеву, [ISO дни недели])] или None, если выражение не разобрать (тогда показываем как есть)."""
    try:
        f = cron.split()
        _sec, minute, hour, dom, _mon, dow = f[:6]
        mins, hours = _expand(minute, 0, 59), _expand(hour, 0, 23)
        if dow in ("?", "*"):
            days = list(range(1, 8))
        else:
            days = sorted({7 if q == 1 else q - 1 for q in _expand(dow, 1, 7, _DOW)})
        monthly = dom not in ("?", "*")
        zone = ZoneInfo({"Europe/Kiev": "Europe/Kyiv"}.get(tz, tz or "UTC"))
        today = now.astimezone(zone).date()
        out = []
        for h in hours:
            for m in mins:
                local = dt.datetime(today.year, today.month, today.day, h, m, tzinfo=zone).astimezone(KYIV)
                out.append((local.strftime("%H:%M"), days, monthly))
        return sorted(out)
    except Exception:
        return None


# ── джобы и прогоны ──────────────────────────────────────────────────────────────────────────────────────────────
jobs = {}
clusters = {}
for j in w.jobs.list(expand_tasks=True):
    s = j.settings
    tasks = s.tasks or []
    paths = [t.notebook_task.notebook_path for t in tasks if t.notebook_task]
    run_jobs = [t.run_job_task.job_id for t in tasks if t.run_job_task]
    task_meta = {}
    for t in tasks:
        cond = None
        if t.condition_task and "job.start_time.hour" in (t.condition_task.left or ""):
            cond = (str(getattr(t.condition_task.op, "value", t.condition_task.op)), t.condition_task.right)
        task_meta[t.task_key] = dict(deps=[(d.task_key, d.outcome) for d in (t.depends_on or [])], cond=cond,
                                     run_job=t.run_job_task.job_id if t.run_job_task else None)
    ecid = next((t.existing_cluster_id for t in tasks if t.existing_cluster_id), None)
    if ecid:
        ckind = "all_purpose"
        if ecid not in clusters:
            try:
                clusters[ecid] = w.clusters.get(ecid).cluster_name
            except Exception:
                clusters[ecid] = ecid
        cname = clusters[ecid]
    elif any(t.job_cluster_key or t.new_cluster for t in tasks):
        ckind, cname = "job", None
    else:
        ckind, cname = "serverless", None
    sch, trg = s.schedule, s.trigger
    if sch and sch.quartz_cron_expression:
        kind, cron, tz = "cron", sch.quartz_cron_expression, sch.timezone_id
        paused = str(getattr(sch.pause_status, "value", sch.pause_status)) == "PAUSED"
    elif trg:
        kind, cron, tz = "event", None, None
        paused = str(getattr(trg.pause_status, "value", trg.pause_status)) == "PAUSED"
    elif s.continuous:
        kind, cron, tz, paused = "continuous", None, None, False
    else:
        kind, cron, tz, paused = "manual", None, None, False
    jobs[j.job_id] = dict(job_id=j.job_id, job_name=s.name or str(j.job_id), creator=j.creator_user_name or "",
                          kind=kind, cron=cron, tz=tz, paused=paused, paths=paths, run_jobs=run_jobs,
                          task_meta=task_meta, cluster_kind=ckind, cluster_name=cname)


# «Что если» (только локальная проба, переменная SCHEDULE_WHATIF = папка с payload'ами `jobs update`): изменения джоб
# накладываются на прочитанные настройки в памяти — так порядок проверяется ДО выкладки, по тем же файлам, что пойдут
# в Databricks. В джобе переменной нет, и блок ничего не делает.
for _f in sorted(os.listdir(os.environ["SCHEDULE_WHATIF"])) if os.environ.get("SCHEDULE_WHATIF") else []:
    _pl = json.load(open(os.path.join(os.environ["SCHEDULE_WHATIF"], _f)))
    _J = jobs.get(_pl["job_id"])
    if not _J:
        continue
    _ns = _pl.get("new_settings", {})
    if "schedule" in (_pl.get("fields_to_remove") or []):
        _J.update(kind="manual", cron=None, tz=None, paused=False)
    if _ns.get("schedule"):
        _J.update(kind="cron", cron=_ns["schedule"]["quartz_cron_expression"], tz=_ns["schedule"]["timezone_id"],
                  paused=_ns["schedule"].get("pause_status") == "PAUSED")
    for _t in _ns.get("tasks", []):
        _c = _t.get("condition_task")
        _J["task_meta"][_t["task_key"]] = dict(
            deps=[(d["task_key"], d.get("outcome")) for d in _t.get("depends_on", [])],
            cond=(_c["op"], _c["right"]) if _c and "job.start_time.hour" in _c.get("left", "") else None,
            run_job=(_t.get("run_job_task") or {}).get("job_id"))
    print("что если:", _f)


def _p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))]


since_ms = int((now - dt.timedelta(days=RUNS_DAYS)).timestamp() * 1000)
for jid, J in jobs.items():
    runs = []
    try:
        for r in w.jobs.list_runs(job_id=jid, start_time_from=since_ms, expand_tasks=False):
            runs.append(r)
            if len(runs) >= 200:
                break
    except Exception:
        pass
    J["last_run"] = None
    if runs:
        r = max(runs, key=lambda x: x.start_time or 0)
        st = r.state
        life = str(getattr(st.life_cycle_state, "value", st.life_cycle_state) or "")
        res = str(getattr(st.result_state, "value", st.result_state) or "")
        state = ("running" if life in ("PENDING", "RUNNING", "QUEUED", "BLOCKED", "WAITING_FOR_RETRY")
                 else {"SUCCESS": "success", "CANCELED": "canceled", "SKIPPED": "skipped",
                       "EXCLUDED": "skipped"}.get(res, "failed"))
        J["last_run"] = dict(start=r.start_time, end=r.end_time or None, state=state, task_run=None, run_id=r.run_id)
    ok = [(dt.datetime.fromtimestamp(r.start_time / 1000, KYIV), (r.end_time - r.start_time) / 60000)
          for r in runs if r.start_time and r.end_time and str(getattr(r.state.result_state, "value",
                                                                         r.state.result_state)) == "SUCCESS"]
    J["median_min"] = round(statistics.median([d for _, d in ok]), 1) if ok else None
    slots = []
    parsed = quartz_slots(J["cron"], J["tz"]) if J["kind"] == "cron" else None
    for t, days, monthly in (parsed or []):
        h, m = map(int, t.split(":"))
        mine = [d for s, d in ok if abs((s.hour * 60 + s.minute) - (h * 60 + m)) <= SLOT_MATCH_MIN]
        slots.append(dict(t=t, dows=days, monthly=monthly,
                          median_min=round(statistics.median(mine), 1) if mine else J["median_min"],
                          p90_min=round(_p90(mine), 1) if mine else None, runs=len(mine)))
    J["slots"] = slots
    J["cron_unparsed"] = J["kind"] == "cron" and parsed is None

# ── цепочки: задача «запустить другую джобу» (run_job_task) ───────────────────────────────────────────────────────
# Дочерняя джоба стартует не по часам, а когда до её задачи дойдёт прогон родителя. Время её запуска = запуск
# родителя + обычное смещение этой задачи от начала прогона (по истории задач); истории ещё нет — по окончанию задач,
# от которых она зависит. Условие «по часу старта» ({{job.start_time.hour}}, UTC) отбирает запуски родителя: так
# Unified Pricing идёт только после дневного прогона LM Offers, а не после утреннего.
_OPS = {"GREATER_THAN": lambda a, b: a > b, "GREATER_THAN_OR_EQUAL": lambda a, b: a >= b,
        "LESS_THAN": lambda a, b: a < b, "LESS_THAN_OR_EQUAL": lambda a, b: a <= b,
        "EQUAL_TO": lambda a, b: a == b, "NOT_EQUAL": lambda a, b: a != b}


def _task_offsets(jid):
    """Медианы смещений начала и конца каждой задачи от начала прогона, минуты."""
    st, en = {}, {}
    try:
        for r in w.jobs.list_runs(job_id=jid, start_time_from=since_ms, expand_tasks=True, completed_only=True):
            for t in r.tasks or []:
                if t.start_time and r.start_time:
                    st.setdefault(t.task_key, []).append((t.start_time - r.start_time) / 60000)
                if t.end_time and r.start_time:
                    en.setdefault(t.task_key, []).append((t.end_time - r.start_time) / 60000)
    except Exception:
        pass
    return ({k: statistics.median(v) for k, v in st.items()}, {k: statistics.median(v) for k, v in en.items()})


for pid, P in jobs.items():
    edges = [(k, m) for k, m in P["task_meta"].items() if m["run_job"] and m["run_job"] in jobs]
    if not edges or P["paused"] or not P["slots"]:
        continue
    st_off, en_off = _task_offsets(pid)

    def _start(k, seen=()):
        if k in st_off:
            return st_off[k]
        deps_ = [d for d, _ in P["task_meta"].get(k, {}).get("deps", []) if d not in seen]
        return max((_end(d, seen + (k,)) for d in deps_), default=0.0)

    def _end(k, seen=()):
        if k in en_off:
            return en_off[k]
        m = P["task_meta"].get(k, {})
        if m.get("run_job") and jobs.get(m["run_job"], {}).get("median_min"):
            return _start(k, seen) + jobs[m["run_job"]]["median_min"]
        return _start(k, seen)

    def _conds(k, seen=()):
        """Условия по часу на пути к задаче: [(op, порог, нужный исход)]."""
        out = []
        for d, outcome in P["task_meta"].get(k, {}).get("deps", []):
            if d in seen:
                continue
            c = P["task_meta"].get(d, {}).get("cond")
            if c:
                out.append((c[0], c[1], (outcome or "true").lower()))
            out += _conds(d, seen + (k,))
        return out

    for k, m in edges:
        C = jobs[m["run_job"]]
        off = _start(k)
        conds = _conds(k)
        for ps in P["slots"]:
            h, mi = map(int, ps["t"].split(":"))
            hour_utc = dt.datetime(now.year, now.month, now.day, h, mi, tzinfo=KYIV).astimezone(dt.timezone.utc).hour
            ok_ = True
            for op, right, need in conds:
                try:
                    res = _OPS.get(op, lambda a, b: True)(hour_utc, int(float(right)))
                except ValueError:
                    res = True
                ok_ = ok_ and (res == (need == "true"))
            if not ok_:
                continue
            t_ = (h * 60 + mi + off) % (24 * 60)
            C["slots"].append(dict(t=f"{int(t_) // 60:02d}:{int(t_) % 60:02d}", dows=ps["dows"], monthly=ps.get("monthly"),
                                   median_min=C["median_min"], p90_min=None, runs=0,
                                   after=P["job_name"], after_id=pid, after_task=k))
        if C["kind"] == "manual":
            C["kind"] = "chain"
for J in jobs.values():
    J["slots"].sort(key=lambda x: x["t"])


def _ancestors(pid, k, seen=()):
    """Задачи родителя, которые идут раньше задачи k в том же прогоне (по depends_on)."""
    out = set()
    for d, _ in jobs[pid]["task_meta"].get(k, {}).get("deps", []):
        if d not in seen:
            out |= {d} | _ancestors(pid, d, seen + (k,))
    return out


def _same_run_order(J, s, W):
    """Порядок задан задачами одного прогона: наша джоба сама запускает источник раньше своих задач, или оба запущены
    одним родителем и задача источника стоит раньше нашей (сверка → реплика Power BI → сверка → сторож)."""
    if any(x.get("after_id") == J["job_id"] for x in W["slots"]):
        return True
    if s.get("after_id"):
        anc = _ancestors(s["after_id"], s["after_task"])
        return any(x.get("after_id") == s["after_id"] and x.get("after_task") in anc for x in W["slots"])
    return False

# ── код ноутбуков → какие таблицы джоба пишет и читает ───────────────────────────────────────────────────────────
uc_tables = uc(f"""SELECT table_schema, table_name, table_type FROM dnipro_m.information_schema.tables
                   WHERE table_schema IN {SCHEMAS}""")
uc_views = uc(f"""SELECT table_schema, table_name, view_definition FROM dnipro_m.information_schema.views
                  WHERE table_schema IN {SCHEMAS}""")
pg = pg_connect()
with pg.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'kabinet_data'")
    pg_tables = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT viewname, definition FROM pg_views WHERE schemaname = 'kabinet_data'")
    pg_views = cur.fetchall()
    try:
        cur.execute("SELECT job_id, system FROM kabinet_data.job_systems")
        sys_override = dict(cur.fetchall())
    except Exception:
        pg.rollback()   # таблицы ещё нет (локальная проба до SQL) — та же поправка, что в SQL-файле
        sys_override = {347595451511001: "powerbi"}
    try:
        cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'schedule_margin_warn_min'")
        row = cur.fetchone()
        WARN_MIN = int(float(row[0])) if row else 10
    except Exception:
        pg.rollback()
        WARN_MIN = 10

KNOWN = {f"{r['table_schema']}.{r['table_name']}".lower() for r in uc_tables}
KNOWN |= {f"kabinet_data.{x}".lower() for x in pg_tables}
VIEW_DEF = {f"{r['table_schema']}.{r['table_name']}".lower(): r["view_definition"] or "" for r in uc_views}
VIEW_DEF.update({f"kabinet_data.{n}".lower(): d or "" for n, d in pg_views})
# реплики Кабинета в UC (dnipro_m.kabinet_data.x) и в Lakebase (kabinet_data.x) — одна таблица по смыслу
NAME_RE = re.compile(r"\b(?:dnipro_m\.)?(dnipro_m|kabinet_data|kabinet)\.([A-Za-z_][A-Za-z0-9_]*)(\{)?", re.I)


def mentions(code):
    out = set()
    for m in NAME_RE.finditer(code):
        name = f"{m.group(1)}.{m.group(2)}".lower()
        if m.group(3):              # f"…_{country}" — все таблицы с этим началом
            out |= {k for k in KNOWN if k.startswith(name)}
        elif name in KNOWN:
            out.add(name)
    return out


WRITE_KW = (r"(?:INSERT\s+(?:INTO|OVERWRITE)(?:\s+TABLE)?|MERGE\s+INTO|CREATE\s+(?:OR\s+REPLACE\s+)?TABLE"
            r"(?:\s+IF\s+NOT\s+EXISTS)?|DELETE\s+FROM|UPDATE)\s+[`\"]?")
WRITE_LIT = re.compile(WRITE_KW + r"((?:dnipro_m\.)?(?:dnipro_m|kabinet_data|kabinet)\.[A-Za-z_][A-Za-z0-9_]*)", re.I)
WRITE_VAR = re.compile(WRITE_KW + r"\{([A-Za-z_][A-Za-z0-9_]*)\}", re.I)
SAVE = re.compile(r"(?:saveAsTable|insertInto|toTable)\(\s*(?:f?[\"']([^\"']+)[\"']|([A-Za-z_][A-Za-z0-9_]*))")
ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*f?[\"']([A-Za-z0-9_.]+)[\"']", re.M)


def _norm(name):
    m = NAME_RE.search(name or "")
    return f"{m.group(1)}.{m.group(2)}".lower() if m else None


def writes_of(code):
    vars_ = {k: v for k, v in ASSIGN.findall(code)}
    out = set()
    for m in WRITE_LIT.finditer(code):
        out.add(_norm(m.group(1)))
    for m in WRITE_VAR.finditer(code):
        out.add(_norm(vars_.get(m.group(1), "")))
    for lit, var in SAVE.findall(code):
        out.add(_norm(lit or vars_.get(var, "")))
    return {x for x in out if x and x in KNOWN}


def expand_views(names, depth=0):
    """Таблицы под вьюхами: наша джоба читает вью, а ждать надо того, кто пишет таблицы под ней."""
    out = set(names)
    if depth > 5:
        return out
    for n in names:
        if n in VIEW_DEF:
            out |= expand_views(mentions(VIEW_DEF[n]) - {n}, depth + 1)
    return out


def export_run_code(run_id):
    """Код ноутбука из последнего прогона — работает и без прав на сам файл."""
    run = w.jobs.get_run(run_id)
    for t in run.tasks or []:
        try:
            ex = w.jobs.export_run(t.run_id, views_to_export=ViewsToExport.CODE)
            html = ex.views[0].content
            m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
            model = json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode()))
            return "\n".join(c.get("command", "") for c in model.get("commands", []))
        except Exception:
            continue
    return ""


# Служебные таблицы пишут почти все джобы (пульс, инциденты, журналы), и зависимость через них ничего не значит:
# сторож «ждал» бы каждый загрузчик. Это не настройка, а смысл таблицы, поэтому список здесь, а не в reorder_params.
SERVICE = {"kabinet_data.system_pulse", "kabinet_data.incidents", "kabinet_data.app_action_log",
           "kabinet_data.watchdog_heartbeat", "kabinet_data.data_freshness_rules", "kabinet_data.job_health_rules",
           "kabinet_data.reorder_params", "kabinet_data.sync_log", "dnipro_m.sync_log", "kabinet_data.clickup_tasks",
           "kabinet_data.clickup_sync_state", "kabinet_data.incident_types", "kabinet_data.job_schedule_snapshot",
           "kabinet_data.job_dependencies", "kabinet_data.job_schedule_changes", "kabinet_data.job_systems",
           "kabinet_data.load_day_snapshots"}

for jid, J in jobs.items():
    code = ""
    for p in J["paths"]:
        try:
            code += "\n" + base64.b64decode(w.workspace.export(p, format=ExportFormat.SOURCE).content).decode("utf-8", "ignore")
        except Exception:
            pass
    if not code and J["last_run"]:
        try:
            code = export_run_code(J["last_run"]["run_id"])
        except Exception:
            code = ""
    J["code_read"] = bool(code)
    wr = writes_of(code)
    J["writes"] = sorted(wr - SERVICE)
    J["reads"] = sorted(expand_views(mentions(code) - wr) - wr - SERVICE)


def system_of(J):
    if J["job_id"] in sys_override:
        return sys_override[J["job_id"]]
    n = J["job_name"]
    if n.startswith("Kabinet"):
        return "kabinet"
    if n.lower().replace("-", " ").startswith("listing suite"):
        return "listing_suite"
    if "spiderweb" in n.lower() or "power bi" in n.lower():
        return "powerbi"
    if "tableau" in n.lower():
        return "tableau"
    return "other"


for J in jobs.values():
    J["system"] = system_of(J)

# ── зависимости ──────────────────────────────────────────────────────────────────────────────────────────────────
writers = {}
for J in jobs.values():
    for tname in J["writes"]:
        writers.setdefault(tname, set()).add(J["job_id"])


def _mins(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _hhmm(x):
    x = int(round(x)) % (24 * 60)
    return f"{x // 60:02d}:{x % 60:02d}"


deps = []
for J in jobs.values():
    if J["system"] != "kabinet" or J["kind"] == "manual" or (J["paused"] and J["kind"] != "chain"):
        continue
    src_tables = {}
    for tname in J["reads"]:
        for wid in writers.get(tname, ()):
            if wid != J["job_id"] and jobs[wid]["kind"] != "manual" and not (jobs[wid]["paused"]
                                                                               and jobs[wid]["kind"] != "chain"):
                src_tables.setdefault(wid, set()).add(tname)
    for wid, tabs in src_tables.items():
        W = jobs[wid]
        base = dict(our_job_id=J["job_id"], our_job=J["job_name"], source_job_id=wid, source_job=W["job_name"],
                    source_system=W["system"], tables=sorted(tabs))
        if J["kind"] not in ("cron", "chain") or not J["slots"]:
            deps.append({**base, "our_time": "event", "source_start": None, "source_end": None,
                         "margin_min": None, "status": "event", "days": None})
            continue
        for s in J["slots"]:
            if s.get("after_id") == wid or _same_run_order(J, s, W):
                # наша джоба запускается задачей в прогоне самого источника — после его окончания по построению
                deps.append({**base, "our_time": s["t"], "source_start": None, "source_end": None,
                             "margin_min": None, "status": "chain", "days": None})
                continue
            if W["kind"] not in ("cron", "chain") or not W["slots"]:
                deps.append({**base, "our_time": s["t"], "source_start": None, "source_end": None,
                             "margin_min": None, "status": "source_event", "days": None})
                continue
            worst, worst_days = None, []
            for d in s["dows"]:
                cands = [x for x in W["slots"] if d in x["dows"] and _mins(x["t"]) <= _mins(s["t"])]
                if not cands:
                    res = dict(status="prev_day", margin=None, start=None, end=None)
                else:
                    c = max(cands, key=lambda x: _mins(x["t"]))
                    dur = c["median_min"] if c["median_min"] is not None else 0
                    end = _mins(c["t"]) + dur
                    margin = _mins(s["t"]) - end
                    status = "broken" if margin < 0 else ("warn" if margin < WARN_MIN else "ok")
                    res = dict(status=status, margin=margin, start=c["t"], end=_hhmm(end))
                rank = {"broken": 0, "warn": 1, "ok": 2, "prev_day": 3}[res["status"]]
                if worst is None or rank < worst[0] or (rank == worst[0] and (res["margin"] or 0) < (worst[1]["margin"] or 0)):
                    worst, worst_days = (rank, res), [d]
                elif rank == worst[0] and res["margin"] == worst[1]["margin"]:
                    worst_days.append(d)
            res = worst[1]
            all_days = len(worst_days) == len(s["dows"]) == 7
            deps.append({**base, "our_time": s["t"], "source_start": res["start"], "source_end": res["end"],
                         "margin_min": None if res["margin"] is None else int(round(res["margin"])),
                         "status": res["status"], "days": None if all_days else ",".join(map(str, sorted(worst_days)))})

# ── история расписаний из журнала аудита ─────────────────────────────────────────────────────────────────────────
audit = uc(f"""
    SELECT event_time, action_name,
           coalesce(request_params['job_id'], get_json_object(response.result, '$.job_id')) AS job_id,
           request_params['new_settings'] AS new_settings, request_params['schedule'] AS schedule_p,
           request_params['trigger'] AS trigger_p, request_params['name'] AS name_p,
           request_params['fields_to_remove'] AS removed_p
    FROM system.access.audit
    WHERE service_name = 'jobs' AND action_name IN ('create', 'update', 'reset')
      AND event_date >= current_date() - INTERVAL {AUDIT_DAYS} DAYS AND response.status_code = 200
    ORDER BY event_time""")


def _sched_of(settings):
    """Расписание из настроек события: None — событие расписание не трогало."""
    if settings is None:
        return None
    if "schedule" in settings and settings["schedule"]:
        sc = settings["schedule"]
        cron, tz = sc.get("quartz_cron_expression"), sc.get("timezone_id")
        sl = quartz_slots(cron, tz) or []
        return dict(kind="cron", cron=cron, timezone=tz, paused=sc.get("pause_status") == "PAUSED",
                    slots=[dict(t=t, dows=d) for t, d, _ in sl])
    if "trigger" in settings and settings["trigger"]:
        return dict(kind="event", cron=None, timezone=None,
                    paused=settings["trigger"].get("pause_status") == "PAUSED", slots=[])
    return None


state, changes = {}, []
for ev in audit:
    try:
        jid = int(ev["job_id"])
    except (TypeError, ValueError):
        continue
    if ev["action_name"] == "create":
        settings = {"schedule": json.loads(ev["schedule_p"]) if ev["schedule_p"] else None,
                    "trigger": json.loads(ev["trigger_p"]) if ev["trigger_p"] else None}
    else:
        try:
            settings = json.loads(ev["new_settings"]) if ev["new_settings"] else None
        except Exception:
            settings = None
    new = _sched_of(settings)
    if new is None and "schedule" in str(ev.get("removed_p") or ""):
        new = dict(kind="manual", cron=None, timezone=None, paused=False, slots=[])
    if new is None:
        continue
    key = lambda x: (x["kind"], x["cron"], x["timezone"], x["paused"])  # noqa: E731
    prev = state.get(jid)
    if prev is None or key(prev) != key(new):
        et = ev["event_time"]
        et = et if isinstance(et, dt.datetime) else dt.datetime.fromisoformat(str(et).replace("Z", "+00:00"))
        if et.tzinfo is None:
            et = et.replace(tzinfo=dt.timezone.utc)
        if et >= now - dt.timedelta(days=SHOW_CHANGES_DAYS) and (prev is not None or ev["action_name"] != "create"):
            changes.append(dict(job_id=jid, event_time=et, before=prev, after=new))
    state[jid] = new

changes_last = {}
for c in changes:
    changes_last[c["job_id"]] = c       # последнее изменение джобы — его «стало» и есть текущее расписание
ours_by_source = {}
for d in deps:
    ours_by_source.setdefault(d["source_job_id"], set()).add(d["our_job"])
for c in changes:
    J = jobs.get(c["job_id"])
    if J and c["after"]["kind"] == "manual" and J["kind"] == "chain" and c is changes_last.get(c["job_id"]):
        c["after"] = dict(c["after"], kind="chain", slots=[x for x in J["slots"] if x.get("after")])
    c["job_name"] = J["job_name"] if J else str(c["job_id"])
    c["system"] = J["system"] if J else "other"
    aff = set(ours_by_source.get(c["job_id"], set()))
    if J and J["system"] == "kabinet":
        aff.add(J["job_name"])
    c["affected_jobs"] = sorted(aff)
    c["affects_ours"] = bool(aff)

# ── запись ───────────────────────────────────────────────────────────────────────────────────────────────────────
snap = []
for J in jobs.values():
    lr = J["last_run"] or {}
    ts = lambda v: dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc) if v else None  # noqa: E731
    snap.append(dict(job_id=J["job_id"], job_name=J["job_name"], system=J["system"], schedule_kind=J["kind"],
                     cron=J["cron"], timezone=J["tz"], paused=J["paused"], slots=J["slots"],
                     median_min=J["median_min"], last_run_start=ts(lr.get("start")), last_run_end=ts(lr.get("end")),
                     last_run_state=lr.get("state"), writes=J["writes"], reads=J["reads"], code_read=J["code_read"],
                     cluster_kind=J["cluster_kind"], cluster_name=J["cluster_name"]))

broken = [d for d in deps if d["status"] == "broken"]
summary = (f"джоб {len(snap)}, зависимостей {len(deps)}, нарушен порядок {len(broken)}, "
           f"изменений расписания за {SHOW_CHANGES_DAYS} дн {len(changes)}, код прочитан у "
           f"{sum(1 for s in snap if s['code_read'])}")
print("📅", summary)
for d in broken:
    print(f"   🔴 {d['our_job']} {d['our_time']} ждёт {d['source_job']} (до {d['source_end']}), запас {d['margin_min']} мин")

if LOCAL_OUT:
    json.dump(dict(observed_at=now, warn_min=WARN_MIN, snapshot=snap, deps=deps, changes=changes),
              open(LOCAL_OUT, "w"), ensure_ascii=False, default=str, indent=1)
    print("→", LOCAL_OUT)

# COMMAND ----------

# DBTITLE 1,2. Запись и сообщение о смене расписания
if not LOCAL_OUT:
    import psycopg2.extras
    _J = psycopg2.extras.Json
    pg.close()
    pg = pg_connect()   # своё соединение на запись: шаг выше мог идти дольше жизни токена
    with pg, pg.cursor() as cur:
        cur.execute("SELECT max(observed_at) FROM kabinet_data.job_schedule_snapshot")
        prev_run = cur.fetchone()[0]
        # какие изменения уже известны: журнал аудита отдаёт события с задержкой (12.10.2026 — 25+ минут), и событие
        # может появиться в нём ПОСЛЕ прогона, который по времени должен был его увидеть. Поэтому «новое» — то, чего
        # ещё нет в таблице, а не то, что новее прошлого прогона: иначе опоздавшее событие не сообщалось бы никогда.
        cur.execute("SELECT job_id, event_time FROM kabinet_data.job_schedule_changes")
        known = {(int(a), b) for a, b in cur.fetchall()}
        if not DRY:
            cur.execute("DELETE FROM kabinet_data.job_schedule_snapshot")
            psycopg2.extras.execute_values(cur, """
                INSERT INTO kabinet_data.job_schedule_snapshot (job_id, job_name, system, schedule_kind, cron, timezone,
                    paused, slots, median_min, last_run_start, last_run_end, last_run_state, writes, reads, code_read,
                    cluster_kind, cluster_name, observed_at) VALUES %s""",
                [(s["job_id"], s["job_name"], s["system"], s["schedule_kind"], s["cron"], s["timezone"], s["paused"],
                  _J(s["slots"]), s["median_min"], s["last_run_start"], s["last_run_end"], s["last_run_state"],
                  s["writes"], s["reads"], s["code_read"], s["cluster_kind"], s["cluster_name"], now) for s in snap])
            cur.execute("DELETE FROM kabinet_data.job_dependencies")
            if deps:
                psycopg2.extras.execute_values(cur, """
                    INSERT INTO kabinet_data.job_dependencies (our_job_id, our_job, source_job_id, source_job,
                        source_system, tables, our_time, source_start, source_end, margin_min, status, days, observed_at)
                    VALUES %s ON CONFLICT DO NOTHING""",
                    [(d["our_job_id"], d["our_job"], d["source_job_id"], d["source_job"], d["source_system"],
                      d["tables"], d["our_time"], d["source_start"], d["source_end"], d["margin_min"], d["status"],
                      d["days"], now) for d in deps])
            for c in changes:
                cur.execute("""
                    INSERT INTO kabinet_data.job_schedule_changes (job_id, event_time, job_name, system, before, after,
                        affects_ours, affected_jobs, observed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (job_id, event_time) DO UPDATE SET job_name = EXCLUDED.job_name,
                        system = EXCLUDED.system, affects_ours = EXCLUDED.affects_ours,
                        affected_jobs = EXCLUDED.affected_jobs""",
                    (c["job_id"], c["event_time"], c["job_name"], c["system"],
                     _J(c["before"]) if c["before"] else None, _J(c["after"]), c["affects_ours"], c["affected_jobs"]))
            cur.execute("DELETE FROM kabinet_data.job_schedule_changes WHERE event_time < now() - %s * interval '1 day'",
                        (SHOW_CHANGES_DAYS,))

    # Сообщение — только о сменах, случившихся после прошлого снимка и задевающих наши джобы. Первый прогон (снимка ещё
    # не было) — точка отсчёта: история за 30 дней видна на вкладке, но в чат её не шлём.
    def _when(sch):
        if not sch:
            return "—"
        if sch["kind"] == "event":
            return "по событию" + (" (пауза)" if sch["paused"] else "")
        if sch["kind"] == "manual":
            return "вручную"
        if sch["kind"] == "chain":
            return "; ".join(f"после {s['after']} (~{s['t']})" for s in sch["slots"] if s.get("after")) or "по цепочке"
        days = sorted({d for s in sch["slots"] for d in s["dows"]})
        dn = "" if len(days) == 7 else " " + ",".join(["пн", "вт", "ср", "чт", "пт", "сб", "вс"][d - 1] for d in days)
        return (", ".join(s["t"] for s in sch["slots"]) or sch["cron"]) + dn + (" (пауза)" if sch["paused"] else "")

    fresh = [c for c in changes if c["affects_ours"] and prev_run is not None
             and (int(c["job_id"]), c["event_time"]) not in known
             and c["event_time"] > now - dt.timedelta(days=2)]
    if fresh and not DRY:
        import html as _html
        import requests
        lines = [f"🕒 <b>Расписание изменилось: {len(fresh)}</b>"]
        for c in fresh:
            lines.append(f"• <b>{_html.escape(c['job_name'])}</b> — было {_html.escape(_when(c['before']))} → стало "
                         f"{_html.escape(_when(c['after']))} ({c['event_time'].astimezone(KYIV):%d.%m %H:%M})")
            for d in deps:
                if (d["source_job_id"] == c["job_id"] or d["our_job_id"] == c["job_id"]) \
                        and d["status"] in ("broken", "warn", "ok"):
                    mark = {"broken": "🔴 порядок нарушен", "warn": "🟡 запас меньше нормы", "ok": "🟢 порядок соблюдён"}
                    lines.append(f"   {_html.escape(d['our_job'])} {d['our_time']}: источник заканчивает "
                                 f"{d['source_end']}, запас {d['margin_min']} мин — {mark[d['status']]}")
        token = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")  # noqa: F821
        chat = dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")      # noqa: F821
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML"}, timeout=15)
        if not resp.ok:
            _tg_err = f"Telegram HTTP {resp.status_code} {resp.text[:200]}"
        else:
            _tg_err = None
            with pg, pg.cursor() as cur:
                for c in fresh:
                    cur.execute("UPDATE kabinet_data.job_schedule_changes SET notified_at = now() "
                                "WHERE job_id = %s AND event_time = %s", (c["job_id"], c["event_time"]))
    else:
        _tg_err = None

    # пульс — последним и безусловно; недоставленное сообщение роняет прогон ПОСЛЕ пульса
    with pg, pg.cursor() as cur:
        if not DRY:
            cur.execute("""
                INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                VALUES ('Kabinet - Job Schedule Snapshot', now(), %s, 2)
                ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (summary,))
    pg.close()
    print("💓 Kabinet - Job Schedule Snapshot")
    if _tg_err:
        raise RuntimeError(_tg_err)
