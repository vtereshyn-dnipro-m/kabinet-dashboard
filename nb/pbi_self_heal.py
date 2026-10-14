# Databricks notebook source
# DBTITLE 1,Kabinet - Power BI Self-Heal: перезапуск упавшей утренней сборки витрины и тревоги источника
# Kabinet - Power BI Self-Heal (с 14.10.2026, решение владельца; разрешение владельца витрины на перезапуск — 14.10.2026).
# Каждые 30 минут с 10:15 до 17:45 Kyiv, под владельцем: он администратор и может запускать чужие джобы, читает журнал
# Delta и Jobs API.
#
# Зачем. 13.10.2026 истёк ключ SP-API, утренние Amazon-джобы витрины упали, витрина Power BI собралась неполной, и
# восстановилось это только руками. Теперь:
#   1) самовосстановление: утренняя сборка неполная (реплика её не взяла — pbi_replica_meta.status = 'kept') или упали
#      Amazon-джобы источника (список — kabinet_data.pbi_source_jobs) → ждём, пока ключи рабочие (по тревогам Auth
#      Guard) → ОДИН раз в день перезапускаем упавшие Amazon-джобы, затем Spiderweb (одним прогоном jobs/submit:
#      run_job_task, Spiderweb после всех, run_if ALL_DONE) → реплика подхватит сама по записи. Не помогло → тревога.
#      Ключи не работают → не перезапускаем, тревога «замени ключи». ТОЛЬКО перезапуск: код и настройки чужих джоб не
#      трогаем;
#   2) тревоги: витрина не обновилась до pbi_source_late_hour (12:00); реплика не сработала по записи (запись в витрину
#      была, а прогона реплики с триггером TABLE после неё нет); у джобы источника сменилось расписание, ноутбук или
#      таблицы, которые она пишет (сообщение один раз, затем новая точка отсчёта).
# Тревоги о витрине — в основной чат и второму адресату (kabinet-alerts/telegram-chat-id-darina, если секрет заведён);
# о смене расписания — только в основной. Журнал решений — kabinet_data.pbi_self_heal_log, один перезапуск в день держит
# он же. Метка пульса — последней и безусловно.

# COMMAND ----------

import json, re
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs as J

JOB_NAME = "Kabinet - Power BI Self-Heal"
REPLICA_JOB = 813933040777378
AUTH_GUARD = "Kabinet - Amazon Auth Guard"
AMZ_TABLE = "dnipro_m.dnipro_m.raw_amazon_spiderweb_report"
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
K = ZoneInfo("Europe/Kyiv")
w = WorkspaceClient()
now = dt.datetime.now(dt.timezone.utc)
now_k = now.astimezone(K)
today = now_k.date()
day_start_ms = int(dt.datetime.combine(today, dt.time(0), K).timestamp() * 1000)


def pg():
    # своё соединение на каждый шаг: прогон короткий, но правило проекта одно для всех ноутбуков
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def rstate(run):
    return str(getattr(run.state.result_state, "value", run.state.result_state) or "")


def lstate(run):
    return str(getattr(run.state.life_cycle_state, "value", run.state.life_cycle_state) or "")


def kyiv(ms_or_dt, fmt="%d.%m %H:%M"):
    if ms_or_dt is None:
        return "—"
    d = dt.datetime.fromtimestamp(ms_or_dt / 1000, dt.timezone.utc) if isinstance(ms_or_dt, (int, float)) else ms_or_dt
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(K).strftime(fmt)


# ── настройки, список джоб источника, журнал за сегодня ──
with pg() as c, c.cursor() as cur:
    cur.execute("""SELECT key, value FROM kabinet_data.reorder_params
                   WHERE key IN ('pbi_source_late_hour', 'pbi_heal_last_hour', 'pbi_trigger_missed_minutes',
                                 'pbi_heal_check_after_minutes')""")
    P = {k: float(v) for k, v in cur.fetchall()}
    LATE_HOUR = P.get("pbi_source_late_hour", 12)
    LAST_HOUR = P.get("pbi_heal_last_hour", 17)
    MISSED_MIN = P.get("pbi_trigger_missed_minutes", 30)
    CHECK_AFTER = P.get("pbi_heal_check_after_minutes", 40)
    cur.execute("""SELECT job_id, job_name, role, baseline_cron, baseline_paused, baseline_notebook, baseline_writes
                   FROM kabinet_data.pbi_source_jobs WHERE is_active ORDER BY role, job_name""")
    SRC = [dict(zip(("job_id", "job_name", "role", "cron", "paused", "notebook", "writes"), r)) for r in cur.fetchall()]
    cur.execute("""SELECT kind, submit_run_id, detail, created_at FROM kabinet_data.pbi_self_heal_log
                   WHERE day = %s ORDER BY id""", (today,))
    LOG = [dict(zip(("kind", "run_id", "detail", "at"), r)) for r in cur.fetchall()]
    cur.execute("SELECT min(created_at) FROM kabinet_data.pbi_self_heal_log")
    WATCH_SINCE = cur.fetchone()[0]                      # с какого момента джоба вообще следит (первый прогон)
    cur.execute("""SELECT status, source_built_at, loaded_at, detail FROM kabinet_data.pbi_replica_meta
                   ORDER BY loaded_at DESC LIMIT 1""")
    META = dict(zip(("status", "built", "at", "detail"), cur.fetchone() or (None,) * 4))
    cur.execute("""SELECT message FROM kabinet_data.incidents WHERE incident_type = 'amazon_auth' AND status <> 'resolved'
                   AND (message LIKE '[AMZAUTH:SP-API]%%' OR message LIKE '[AMZAUTH:Amazon Ads]%%')""")
    KEY_PROBLEMS = [m for (m,) in cur.fetchall()]
    cur.execute("SELECT last_success_at FROM kabinet_data.system_pulse WHERE job_name = %s", (AUTH_GUARD,))
    _g = cur.fetchone()
    GUARD_AGE_MIN = (now - _g[0]).total_seconds() / 60 if _g and _g[0] else None
    cur.execute("SELECT job_id, writes FROM kabinet_data.job_schedule_snapshot")
    SNAP_WRITES = {int(j): sorted(wr or []) for j, wr in cur.fetchall()}
if WATCH_SINCE is None:
    WATCH_SINCE = now                                    # первый прогон: точка отсчёта — сейчас
amazon_jobs = [s for s in SRC if s["role"] == "amazon"]
spiderweb = next((s for s in SRC if s["role"] == "spiderweb"), None)
notes = []

# ── факты: прогоны джоб источника сегодня ──
def last_run_today(job_id):
    r = next(iter(w.jobs.list_runs(job_id=job_id, start_time_from=day_start_ms, limit=1)), None)
    return r

failed_amazon, runs_today = [], {}
for s in SRC:
    r = last_run_today(s["job_id"])
    runs_today[s["job_id"]] = r
    if s["role"] == "amazon" and r is not None and lstate(r) in ("TERMINATED", "INTERNAL_ERROR") and rstate(r) != "SUCCESS":
        failed_amazon.append(s)
sw_run = runs_today.get(spiderweb["job_id"]) if spiderweb else None
# идёт хоть одна джоба источника — не перезапускаем поверх: у чужих джоб одна очередь, второй запуск пропустится
running = [s["job_name"] for s in SRC if runs_today.get(s["job_id"]) is not None
           and lstate(runs_today[s["job_id"]]) in ("PENDING", "QUEUED", "RUNNING", "BLOCKED", "WAITING_FOR_RETRY")]
sw_failed = sw_run is not None and lstate(sw_run) in ("TERMINATED", "INTERNAL_ERROR") and rstate(sw_run) != "SUCCESS"

# последняя запись в витрину Amazon
try:
    _h = spark.sql(f"DESCRIBE HISTORY {AMZ_TABLE} LIMIT 1").collect()[0]["timestamp"]
    BUILT = _h.replace(tzinfo=dt.timezone.utc) if _h.tzinfo is None else _h
except Exception as e:
    BUILT = None
    notes.append(f"история витрины не прочиталась: {type(e).__name__}")
built_today = BUILT is not None and BUILT.astimezone(K).date() == today
meta_built = META["built"].replace(tzinfo=dt.timezone.utc) if META.get("built") and META["built"].tzinfo is None else META.get("built")
kept_today = META.get("status") == "kept" and meta_built is not None and meta_built.astimezone(K).date() == today

# ключи: тревога Auth Guard по ключу открыта — не работают; Auth Guard давно не отрабатывал — не знаем, ждём
keys_bad = bool(KEY_PROBLEMS)
keys_unknown = GUARD_AGE_MIN is None or GUARD_AGE_MIN > 45

problems = []
if failed_amazon:
    problems.append("упали: " + ", ".join(s["job_name"] for s in failed_amazon))
if sw_failed:
    problems.append(f"{spiderweb['job_name']} упала")
if kept_today:
    problems.append("сборка неполная — реплика её не взяла" + (f" ({META['detail']})" if META.get("detail") else ""))

# ── решения: один перезапуск в день ──
alerts = {}            # токен → (тип, severity, текст, второму адресату)
resolve = {}           # токен → причина закрытия
log_rows = []          # (kind, submit_run_id, detail)
restart = next((l for l in LOG if l["kind"] == "restart"), None)
outcome_logged = any(l["kind"] in ("helped", "not_helped") for l in LOG)

if restart and not outcome_logged:
    # перезапуск уже был: дождаться его конца и посмотреть, помог ли
    sr = w.jobs.get_run(restart["run_id"]) if restart["run_id"] else None
    if sr is not None and lstate(sr) in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
        end = dt.datetime.fromtimestamp(sr.end_time / 1000, dt.timezone.utc)
        if now - end >= dt.timedelta(minutes=CHECK_AFTER):
            fine = META.get("status") == "replaced" and META.get("at") is not None and META["at"] >= end
            if fine:
                log_rows.append(("helped", restart["run_id"], "после перезапуска реплика взяла полную витрину"))
                resolve["[PBIHEAL:restart]"] = "перезапуск помог: витрина полная, реплика заменена"
            else:
                bad = [f"{t.task_key}: {rstate(t)}" for t in (sr.tasks or []) if rstate(t) != "SUCCESS"]
                why = ("не отработали — " + ", ".join(bad)) if bad else (
                    f"витрина всё ещё неполная ({META.get('detail') or 'реплика её не взяла'})"
                    if META.get("status") == "kept" else "реплика после перезапуска не прогналась")
                log_rows.append(("not_helped", restart["run_id"], why))
                alerts["[PBIHEAL:restart]"] = ("pbi_self_heal", "high",
                    f"Перезапуск утренней сборки витрины Power BI не помог: {why}. Второй раз сегодня не перезапускаю — "
                    f"нужно разобраться вручную.", True)
elif problems and not restart:
    if keys_bad:
        alerts["[PBIHEAL:keys]"] = ("pbi_self_heal", "critical",
            "Сборка витрины Power BI не прошла (" + "; ".join(problems) + "), а ключи Amazon не работают — перезапуск "
            "не делаю. Замените ключи в трёх местах (Databricks amazon-sp-api, Streamlit Secrets Listing Suite и "
            "Кабинета); после этого перезапуск сделаю сам на ближайшей проверке.", True)
    elif keys_unknown:
        notes.append(f"проблема есть, но Auth Guard не отрабатывал {GUARD_AGE_MIN or '—'} мин — жду")
    elif running:
        notes.append("проблема есть, но идёт " + ", ".join(running) + " — жду конца")
    elif now_k.hour >= LAST_HOUR:
        alerts["[PBIHEAL:late]"] = ("pbi_self_heal", "high",
            "Сборка витрины Power BI сегодня не прошла (" + "; ".join(problems) + "), а для перезапуска уже поздно: "
            "длинная сборка пересеклась бы с вечерними загрузчиками. Перезапуск не делал.", True)
    else:
        resolve["[PBIHEAL:keys]"] = "ключи снова рабочие"
        names = list(failed_amazon)
        tasks = [J.SubmitTask(task_key=f"j{s['job_id']}", run_job_task=J.RunJobTask(job_id=int(s["job_id"])),
                              timeout_seconds=6 * 3600) for s in names]
        if spiderweb:
            tasks.append(J.SubmitTask(task_key="spiderweb", run_job_task=J.RunJobTask(job_id=int(spiderweb["job_id"])),
                                      depends_on=[J.TaskDependency(task_key=t.task_key) for t in tasks],
                                      run_if=J.RunIf.ALL_DONE, timeout_seconds=3 * 3600))
        listed = ", ".join(s["job_name"] for s in names) + (", затем " if names else "") + (
            spiderweb["job_name"] if spiderweb else "")
        run_id = None
        if not DRY:
            run_id = w.jobs.submit(run_name=f"{JOB_NAME}: перезапуск {today:%d.%m}", tasks=tasks).run_id
        log_rows.append(("restart", run_id, listed))
        alerts["[PBIHEAL:restart]"] = ("pbi_self_heal", "medium",
            f"Утренняя сборка витрины Power BI не прошла ({'; '.join(problems)}). Ключи Amazon рабочие — перезапустил "
            f"{listed}. Реплика Кабинета подхватит витрину сама; если не поможет — напишу.", True)
elif not problems:
    resolve["[PBIHEAL:keys]"] = "сборка в порядке"
    resolve["[PBIHEAL:late]"] = "сборка в порядке"

# ── тревога: витрина не обновилась до LATE_HOUR ──
if now_k.hour >= LATE_HOUR and BUILT is not None and not built_today:
    alerts["[PBISRC:late]"] = ("pbi_source_late", "high",
        f"Витрина Power BI сегодня не обновлялась: последняя сборка Amazon {kyiv(BUILT)}, сейчас {now_k:%H:%M}. "
        f"Кабинет и Power BI показывают вчерашние цифры.", True)
elif built_today:
    resolve["[PBISRC:late]"] = f"витрина собрана {kyiv(BUILT)}"

# ── тревога: запись в витрину была, а реплика по записи не сработала ──
# считаем только записи после первого прогона этой джобы: раньше триггера могло не быть
if BUILT is not None and BUILT >= WATCH_SINCE and now - BUILT >= dt.timedelta(minutes=MISSED_MIN):
    since_ms = int(BUILT.timestamp() * 1000)
    trig = [r for r in w.jobs.list_runs(job_id=REPLICA_JOB, start_time_from=since_ms, limit=10)
            if "TABLE" in str(getattr(r.trigger, "value", r.trigger) or "").upper()]
    if not trig:
        alerts["[PBIREPL:trigger]"] = ("pbi_trigger_missed", "high",
            f"Витрина Power BI записана {kyiv(BUILT)}, а реплика Кабинета по записи не сработала (прошло "
            f"{int((now - BUILT).total_seconds() // 60)} мин). Проверить триггер джобы Kabinet - Power BI Replica; "
            f"до этого цифры обновятся только сверкой в 13:00 и запуском в 16:45.", False)
    else:
        resolve["[PBIREPL:trigger]"] = f"реплика сработала по записи {kyiv(trig[0].start_time)}"

# ── сообщение: сменилось расписание, ноутбук или таблицы джобы источника ──
changes, baselines = [], []
for s in SRC:
    try:
        st_ = w.jobs.get(s["job_id"]).settings
    except Exception as e:
        changes.append((s, f"джоба не читается ({type(e).__name__}) — удалена?"))
        continue
    cron = st_.schedule.quartz_cron_expression if st_.schedule else None
    paused = str(getattr(st_.schedule.pause_status, "value", "")) == "PAUSED" if st_.schedule else None
    nb_ = next((t.notebook_task.notebook_path for t in (st_.tasks or []) if t.notebook_task), None)
    writes = SNAP_WRITES.get(int(s["job_id"]))
    cur_ = {"cron": cron, "paused": paused, "notebook": nb_, "writes": writes}
    if s["cron"] is None and s["notebook"] is None:
        baselines.append((s["job_id"], cur_))                  # первая точка отсчёта — молча
        continue
    diff = []
    if cron != s["cron"]:
        diff.append(f"расписание {s['cron'] or 'нет'} → {cron or 'нет'}")
    if paused != s["paused"]:
        diff.append("поставлена на паузу" if paused else "снята с паузы")
    if nb_ != s["notebook"]:
        diff.append(f"ноутбук {s['notebook']} → {nb_}")
    if writes is not None and s["writes"] is not None and sorted(writes) != sorted(s["writes"]):
        added, removed = sorted(set(writes) - set(s["writes"])), sorted(set(s["writes"]) - set(writes))
        diff.append("пишет " + ", ".join([f"+{x}" for x in added] + [f"−{x}" for x in removed]))
    if diff:
        changes.append((s, "; ".join(diff)))
        baselines.append((s["job_id"], cur_))

# ── запись: журнал, инциденты, точки отсчёта ──
def recipients(second):
    chats = [("основной", dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"))]
    if second:
        try:
            chats.append(("второй адресат", dbutils.secrets.get("kabinet-alerts", "telegram-chat-id-darina")))
        except Exception:
            pass
    return chats


def send(text, second):
    errs = {}
    for who, chat in recipients(second):
        try:
            r = requests.post(f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                              json={"chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
                                    "disable_web_page_preview": True}, timeout=30)
            if not r.ok:
                errs[who] = f"{r.status_code}: {r.text[:150]}"
        except Exception as e:
            errs[who] = f"{type(e).__name__}: {str(e)[:150]}"
    return errs


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


SEND_ERR, sent, closed = [], [], []
TITLES = {"pbi_self_heal": "Самовосстановление витрины Power BI", "pbi_source_late": "Витрина Power BI не обновилась",
          "pbi_trigger_missed": "Реплика Power BI не сработала по записи"}
with pg() as c, c.cursor() as cur:
    cur.execute("""SELECT id, incident_type, message FROM kabinet_data.incidents
                   WHERE incident_type IN ('pbi_self_heal', 'pbi_source_late', 'pbi_trigger_missed') AND status <> 'resolved'""")
    open_inc = {}
    for iid, typ, msg in cur.fetchall():
        tok = re.match(r"\[[A-Z]+:[^\]]+\]", msg or "")
        if tok:
            open_inc[tok.group(0)] = iid
    if not DRY:
        cur.execute("""INSERT INTO kabinet_data.pbi_self_heal_log (day, kind, submit_run_id, detail)
                       SELECT %s, 'started', NULL, 'первый прогон: точка отсчёта для проверки срабатывания реплики'
                       WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.pbi_self_heal_log)""", (today,))
        for kind, rid, detail in log_rows:
            cur.execute("INSERT INTO kabinet_data.pbi_self_heal_log (day, kind, submit_run_id, detail) VALUES (%s, %s, %s, %s)",
                        (today, kind, rid, detail))
    for tok, (typ, sev, text, second) in alerts.items():
        msg = f"{tok} {text}"
        if tok in open_inc:
            if not DRY:
                cur.execute("UPDATE kabinet_data.incidents SET message = %s, severity = %s WHERE id = %s",
                            (msg, sev, open_inc[tok]))
            continue
        if not DRY:
            cur.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, source)
                           VALUES (%s, %s, %s, 'open', 'watchdog')""", (typ, sev, msg))
            icon = "🔴" if sev in ("critical", "high") else "🟡"
            errs = send(f"{icon} <b>{TITLES[typ]}</b>\n{esc(text)}", second)
            if "основной" in errs:
                SEND_ERR.append(errs["основной"])
            if errs:
                cur.execute("""UPDATE kabinet_data.incidents SET message = message || %s
                               WHERE incident_type = %s AND status <> 'resolved' AND message LIKE %s""",
                            (" В бот не ушло: " + "; ".join(f"{k} — {v}" for k, v in errs.items()), typ, tok + "%"))
        sent.append(tok)
    for tok, why in resolve.items():
        if tok in open_inc and tok not in alerts:
            if not DRY:
                cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                               resolved_by = %s WHERE id = %s""", (f"watchdog-autoclose: {why}", open_inc[tok]))
            closed.append(tok)
    # смена у джоб источника — событие: одно сообщение владельцу, журнал, новая точка отсчёта
    if changes and not DRY:
        body = "\n".join(f"• {esc(s['job_name'])}: {esc(d)}" for s, d in changes)
        errs = send("🟡 <b>Изменилась джоба источника витрины Power BI</b>\n" + body
                    + "\nПроверить, не задевает ли это реплику и сверку Кабинета.", False)
        if "основной" in errs:
            SEND_ERR.append(errs["основной"])
        for s, d in changes:
            cur.execute("INSERT INTO kabinet_data.pbi_self_heal_log (day, kind, submit_run_id, detail) VALUES (%s, 'job_changed', %s, %s)",
                        (today, s["job_id"], f"{s['job_name']}: {d}"))
    if not DRY:
        for jid, b in baselines:
            cur.execute("""UPDATE kabinet_data.pbi_source_jobs SET baseline_cron = %s, baseline_paused = %s,
                           baseline_notebook = %s, baseline_writes = %s, baseline_at = now() WHERE job_id = %s""",
                        (b["cron"], b["paused"], b["notebook"], b["writes"], jid))

note = (f"проблемы: {'; '.join(problems) or 'нет'}; ключи: {'не работают' if keys_bad else 'неизвестно' if keys_unknown else 'ок'}; "
        f"решения: {', '.join(k for k, _, _ in log_rows) or '—'}; тревог новых/обновлённых {len(sent)}, закрыто {len(closed)}; "
        f"изменений у джоб источника {len(changes)}" + (f"; {'; '.join(notes)}" if notes else "")
        + (f"; в бот НЕ ушло: {SEND_ERR}" if SEND_ERR else ""))
print(("ПРОБА: " if DRY else "") + note)
if DRY:
    dbutils.notebook.exit(json.dumps({"problems": problems, "alerts": {k: v[2][:300] for k, v in alerts.items()},
                                      "resolve": resolve, "log": log_rows, "changes": [(s["job_name"], d) for s, d in changes],
                                      "keys_bad": keys_bad, "keys_unknown": keys_unknown}, ensure_ascii=False, default=str))

# ── пульс — последним и безусловно ──
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 26)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                (JOB_NAME, note[:900]))
if SEND_ERR:
    # молчание канала должно быть красным: прогон падает ПОСЛЕ пульса
    raise RuntimeError(f"тревога витрины Power BI не ушла в бот: {SEND_ERR}")
