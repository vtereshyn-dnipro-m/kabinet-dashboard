# Databricks notebook source
# DBTITLE 1,Kabinet - Morning Report: утренняя сводка ночи — в бот одним сообщением
# Kabinet - Morning Report (19.10.2026, решение владельца), 08:00 Kyiv, под владельцем.
# Одно сообщение в основной чат: как прошла ночь (20:00 вчера — сейчас) у джоб Amazon API — наших, Дарины и Listing
# Suite: ✅ записали свои таблицы, ❌ упали или «зелёные, но без записи», ⏳ ещё идут или не запустились по расписанию;
# 429 за ночь по джобам и видам квоты; открытые тревоги. Источник — kabinet_data.amazon_run_checks (её пишет
# Kabinet - Amazon Run Check по истории таблиц и выводу прогонов) и Jobs API (что идёт сейчас). Amazon не вызывает.
# Секрет бота читает только эта джоба. Не ушло — прогон падает после пульса: молчание канала должно быть красным.
# dry_run=1 — печатает текст, не отправляет и пульс не пишет.
# Источник кода — nb/morning_report.py в kabinet-dashboard.

# COMMAND ----------

import html, re
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Morning Report"
KYIV = ZoneInfo("Europe/Kyiv")
LIMIT = 3800                         # предел Telegram 4096, запас на разметку
w = WorkspaceClient()
try:
    dbutils.widgets.text("dry_run", "0")  # noqa: F821
    DRY = (dbutils.widgets.get("dry_run") or "0").strip() == "1"  # noqa: F821
except Exception:
    DRY = False
now = dt.datetime.now(KYIV)
w_from = (now - dt.timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
_errors = []


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def esc(x):
    return html.escape(str(x))


def hm(d):
    return d.astimezone(KYIV).strftime("%H:%M")


with pg() as c, c.cursor() as cur:
    cur.execute("SELECT job_id, job_name, owner, check_write FROM kabinet_data.amazon_api_jobs WHERE is_active")
    JOBS = {int(r[0]): dict(zip(("job_id", "job_name", "owner", "check_write"), r)) for r in cur.fetchall()}
    cur.execute("""SELECT run_id, job_id, job_name, started_at, ended_at, state, wrote, tables, n429, kinds_429
                   FROM kabinet_data.amazon_run_checks WHERE started_at >= %s ORDER BY started_at""", (w_from,))
    RUNS = [dict(zip(("run_id", "job_id", "job_name", "started_at", "ended_at", "state", "wrote", "tables", "n429",
                      "kinds"), r)) for r in cur.fetchall()]
    cur.execute("SELECT job_id, slots FROM kabinet_data.job_schedule_snapshot WHERE NOT coalesce(paused, false)")
    SLOTS = {int(j): (s or []) for j, s in cur.fetchall()}
    # порог «проверка не работала» — из базы: правило здоровья проверки, иначе ожидаемый интервал её пульса
    cur.execute("""SELECT p.last_success_at, coalesce(r.expected_interval_hours, p.expected_interval_hours)
                   FROM (SELECT 'Kabinet - Amazon Run Check'::text AS job_name) j
                   LEFT JOIN kabinet_data.system_pulse p USING (job_name)
                   LEFT JOIN kabinet_data.job_health_rules r ON r.job_name = j.job_name AND r.is_active""")
    _p = cur.fetchone()
    CHECK_AGE_H = (dt.datetime.now(dt.timezone.utc) - _p[0]).total_seconds() / 3600 if _p and _p[0] else None
    CHECK_MAX_H = float(_p[1]) if _p and _p[1] is not None else None
    cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'amazon_check_lag_min'")
    _r = cur.fetchone()
    # слот моложе этого — ещё не пропуск: serverless стартует минутами (тот же запас, что у проверки прогонов)
    SLOT_GRACE = dt.timedelta(minutes=float(_r[0]) if _r else 15)
    # created_at — timestamp БЕЗ зоны (UTC): сравнивать только через AT TIME ZONE 'UTC'; NULL — как «давно»
    cur.execute("""SELECT i.severity, i.incident_type, coalesce(t.title, i.incident_type), i.message,
                          coalesce(i.created_at AT TIME ZONE 'UTC', '1970-01-01'::timestamptz) AS created,
                          coalesce(i.created_at AT TIME ZONE 'UTC' >= %s, false) AS is_new
                   FROM kabinet_data.incidents i LEFT JOIN kabinet_data.incident_types t USING (incident_type)
                   WHERE i.status <> 'resolved' AND i.resolved_at IS NULL""", (w_from,))
    OPEN = cur.fetchall()

# ── по джобам: последний прогон за ночь ──
last, night_fail = {}, {}
for r in RUNS:
    last[r["job_id"]] = r                 # по возрастанию времени — остаётся последний
    if r["state"] != "SUCCESS":
        night_fail.setdefault(r["job_id"], []).append(hm(r["started_at"]))
# Jobs API — только по джобам, которых нет в проверке: идёт сейчас или кончилась позже, чем её проверил Amazon Run Check
# (он ходит в :50 и берёт прогоны, кончившиеся 15+ минут назад)
RUNNING = {"QUEUED", "PENDING", "RUNNING", "BLOCKED", "WAITING_FOR_RETRY", "TERMINATING"}
fresh, unread = {}, set()
for jid in JOBS:
    if jid in last:
        continue
    try:
        a = next(iter(w.jobs.list_runs(job_id=jid, start_time_from=int(w_from.timestamp() * 1000), limit=1)), None)
        if a is not None:
            life = a.state.life_cycle_state.value if a.state and a.state.life_cycle_state else ""
            res = a.state.result_state.value if a.state and a.state.result_state else None
            # None — идёт; иначе итог (SKIPPED/INTERNAL_ERROR без result_state — по life_cycle_state)
            fresh[jid] = (dt.datetime.fromtimestamp(a.start_time / 1000, dt.timezone.utc),
                          None if life in RUNNING else (res or life or "UNKNOWN"))
    except Exception as e:
        unread.add(jid)                    # не знаем — не «прогона нет»
        _errors.append(f"прогоны {JOBS[jid]['job_name']}: {type(e).__name__}")


def night_slots(jid):
    """Слоты расписания джобы в окне ночи (20:00–сейчас), без «после <джобы>»."""
    out = []
    for sl in SLOTS.get(jid, []):
        t = sl.get("t")
        if not t or sl.get("after") or "dows" not in sl:
            continue
        hh, mm = map(int, t.split(":"))
        for day in (w_from.date(), now.date()):
            d = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=KYIV)
            if w_from <= d <= now - SLOT_GRACE and d.isoweekday() in (sl.get("dows") or []):
                out.append(d)
    return out


ok, bad, wait = [], [], []
for jid, J in sorted(JOBS.items(), key=lambda kv: kv[1]["job_name"]):
    name = J["job_name"]
    r = last.get(jid)
    if r is None:
        if jid in fresh and fresh[jid][1] is None:
            wait.append(f"⏳ {esc(name)} — идёт с {hm(fresh[jid][0])}")
        elif jid in fresh and fresh[jid][1] != "SUCCESS":
            bad.append(f"❌ {esc(name)} {hm(fresh[jid][0])} — {esc(fresh[jid][1])}")
        elif jid in fresh:
            wait.append(f"⏳ {esc(name)} {hm(fresh[jid][0])} — успешна, запись ещё не проверена")
        elif jid in unread:
            wait.append(f"⏳ {esc(name)} — состояние не прочитано (Jobs API)")
        elif night_slots(jid):
            wait.append(f"⏳ {esc(name)} — по расписанию {', '.join(hm(d) for d in night_slots(jid))}, прогона нет")
        continue                           # джоба ночью не ходит — в сводку не попадает
    when = hm(r["started_at"])
    if r["state"] == "SUCCESS" and night_fail.get(jid):   # последний успешен, но ночью до него были сбои
        when += f" (ночью сбой: {', '.join(night_fail[jid])})"
    if r["state"] != "SUCCESS":
        bad.append(f"❌ {esc(name)} {when} — {esc(r['state'])}")
    elif r["wrote"] is False:
        bad.append(f"❌ {esc(name)} {when} — зелёная, но таблицы не записаны")
    else:
        ok.append(f"{esc(name)} {when}" + (f" ({esc(r['tables'])})" if r["tables"] else
                                           ("" if r["wrote"] is not None else
                                            " (запись не прочитана)" if J["check_write"] else " (запись не проверяется)")))

q429 = {}
for r in RUNS:
    if r["n429"]:
        k = (r["job_name"], r["kinds"] or "")
        q429[k] = q429.get(k, 0) + int(r["n429"])

SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1}
by_sev = {}
for sev, *_x in OPEN:
    by_sev[str(sev).lower()] = by_sev.get(str(sev).lower(), 0) + 1
# critical/high — группами по типу: новые за ночь первыми, внутри — по важности и свежести. Не «8 самых старых»:
# 10.10.2026 так в сводке сторожа восемь строк «нет остатка» за август закрыли свежие поломки джоб
groups = {}
for sev, itype, title, msg, created, is_new in OPEN:
    if str(sev).lower() not in ("critical", "high"):
        continue
    g = groups.setdefault((str(sev).lower(), itype), {"title": title, "n": 0, "new": 0, "last": created, "tok": None})
    g["n"] += 1
    g["new"] += 1 if is_new else 0
    if created >= g["last"]:
        g["last"] = created
        m = re.match(r"\[([^\]]+)\]", msg or "")
        g["tok"] = m.group(1) if m else None
top = sorted(groups.items(), key=lambda kv: (-kv[1]["new"], -SEV.get(kv[0][0], 0), -kv[1]["last"].timestamp()))

# ── текст ──
lines = [f"🌅 <b>Ночь {w_from:%d.%m} 20:00 → {now:%d.%m %H:%M}</b> — джобы Amazon API"]
if CHECK_AGE_H is None or CHECK_MAX_H is None or CHECK_AGE_H > CHECK_MAX_H:
    lines.append(f"⚠️ проверка прогонов (Amazon Run Check) не работала "
                 + (f"{CHECK_AGE_H:.0f} ч" if CHECK_AGE_H is not None else "ни разу") + " — данные ниже неполные")
lines.append(f"✅ {len(ok)} · ❌ {len(bad)} · ⏳ {len(wait)}")
lines += bad + wait
if q429:
    tot = sum(q429.values())
    lines.append(f"🧮 <b>429 за ночь: {tot}</b> — " + "; ".join(
        f"{esc(j)} ×{n}" + (f" ({esc(k)})" if k else "") for (j, k), n in sorted(q429.items(), key=lambda kv: -kv[1])))
else:
    lines.append("🧮 429 за ночь: 0")
lines.append("🔔 <b>Открытые тревоги:</b> " + (", ".join(f"{s} {by_sev[s]}" for s in ("critical", "high", "medium", "low")
                                                   if by_sev.get(s)) or "нет"))
for (sev, itype), g in top[:8]:
    lines.append(f"• {esc(g['title'])} ({esc(sev)})" + (f" ×{g['n']}" if g["n"] > 1 else "")
                 + (f", новых за ночь {g['new']}" if g["new"] else "")
                 + (f" — <code>{esc(g['tok'])}</code>" if g["tok"] and g["n"] == 1 else ""))
if len(top) > 8:
    lines.append(f"  …ещё типов: {len(top) - 8}")
if _errors:
    lines.append("⚙️ сбои сводки: " + esc("; ".join(_errors)[:300]))
# записавшие — последними: при обрезке по длине теряется хвост этого списка, а не сбои и тревоги
if ok:
    lines.append("<b>Записали:</b>")
    lines += ["✅ " + x for x in ok]
# обрезка по строкам, не посреди тега: оборванный <b> Telegram с parse_mode=HTML не примет вовсе
text = ""
for i, ln in enumerate(lines):
    if len(text) + len(ln) + 1 > LIMIT - 20:
        if text.endswith("\n<b>Записали:</b>"):     # одинокий заголовок без строк — убрать
            text = text[: -len("\n<b>Записали:</b>")]
        text += f"\n…ещё строк: {len(lines) - i}"
        break
    text += ("\n" if text else "") + ln
print(text)

if DRY:
    dbutils.notebook.exit(text)  # noqa: F821

# ── отправка: сбой — текстом без токена, падение после пульса ──
_send_err = None
try:
    token = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")  # noqa: F821
    chat = dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")  # noqa: F821
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                         timeout=30)
    if not resp.ok:
        _send_err = f"Telegram HTTP {resp.status_code}: {resp.text[:200]}"
except Exception as e:
    _send_err = f"{type(e).__name__}: " + re.sub(r"bot\d+:[\w-]+", "bot<токен>", str(e))[:200]

note = (f"✅ {len(ok)} ❌ {len(bad)} ⏳ {len(wait)}, 429 {sum(q429.values())}, тревог {len(OPEN)}"
        + (f"; не отправлено: {_send_err}" if _send_err else "") + (f"; сбои: {'; '.join(_errors)[:200]}" if _errors else ""))
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 26)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (JOB_NAME, note))
print(f"💓 {JOB_NAME}: {note}")
if _send_err:
    raise RuntimeError(f"{JOB_NAME}: сводка не ушла — {_send_err}")
