# Databricks notebook source
# DBTITLE 1,Kabinet - Agent Cycle Report: сводки циклов агента — в бот
# Kabinet - Agent Cycle Report (предложение 19.10.2026), каждые 15 минут 08:00–22:45 Kyiv, под владельцем.
# Агент в конце каждого цикла кладёт сводку строкой в kabinet_data.agent_cycle_reports (scratchpad/cycle_report.py);
# здесь неотправленные строки уходят в основной чат и получают sent_at. Секрет бота читает только эта джоба — агент
# его не касается. Не ушло — ошибка в send_error и прогон падает после пульса: молчание канала должно быть красным.
# Две защиты (замечания проверяющего к PR #328):
#   - текст ошибки не содержит токена: requests кладёт URL запроса в текст исключения («…url: /bot<токен>/…»), а
#     send_error читает приложение и пишет пульс — токен вырезается до записи;
#   - строка, которая не ушла MAX_ATTEMPTS раз подряд (например, Telegram отвечает 400 на разметку), больше не
#     отправляется и не красит каждый прогон, но НЕ пропадает молча: на последней неудаче в бот уходит короткое
#     сообщение без разметки «сводка #id не ушла: <ошибка>»; не ушло и оно — прогон красный;
#   - у сообщения общий бюджет длины (шапка 200, разделы по 800 знаков до экранирования — около 3 500 при пределе
#     Telegram 4 096), чтобы длинная сводка не упиралась в «message is too long».

# COMMAND ----------

import html
import psycopg2, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Agent Cycle Report"
TITLE_LIMIT, PART_LIMIT = 200, 800   # знаков ДО экранирования: резать экранированный HTML нельзя — рвутся сущности
w = WorkspaceClient()
TOKEN = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")
CHAT = dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def clean(text):
    """Текст ошибки без токена бота и без идентификатора чата."""
    return str(text).replace(TOKEN, "<токен>").replace(str(CHAT), "<чат>")[:200]


def part(text, limit=PART_LIMIT):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def post(payload):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": CHAT, "disable_web_page_preview": True, **payload}, timeout=30)
        return None if r.ok else clean(f"{r.status_code}: {r.text}")
    except Exception as e:
        return clean(f"{type(e).__name__}: {e}")


with pg() as c, c.cursor() as cur:
    # предел попыток — настройка в базе, как остальные пороги
    cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'agent_report_max_attempts'")
    _r = cur.fetchone()
    MAX_ATTEMPTS = int(_r[0]) if _r else 5
    cur.execute("""SELECT id, title, done, merged, waiting, problems FROM kabinet_data.agent_cycle_reports
                   WHERE sent_at IS NULL AND attempts < %s ORDER BY id LIMIT 10""", (MAX_ATTEMPTS,))
    rows = cur.fetchall()
    cur.execute("SELECT count(*) FROM kabinet_data.agent_cycle_reports WHERE sent_at IS NULL AND attempts >= %s",
                (MAX_ATTEMPTS,))
    given_up = cur.fetchone()[0]

sent, errors, gave_up_now = 0, [], 0
for rid, title, done, merged, waiting, problems in rows:
    parts = [f"🤖 <b>{html.escape(part(title, TITLE_LIMIT))}</b>"]
    for label, text in (("Сделано", done), ("Смержено само", merged), ("Ждёт вас", waiting), ("Не получилось", problems)):
        if text and text.strip():
            parts.append(f"<b>{label}:</b>\n{html.escape(part(text))}")
    err = post({"text": "\n\n".join(parts), "parse_mode": "HTML"})
    with pg() as c, c.cursor() as cur:
        if err:
            cur.execute("""UPDATE kabinet_data.agent_cycle_reports SET send_error = %s, attempts = attempts + 1
                           WHERE id = %s RETURNING attempts""", (err, rid))
            if cur.fetchone()[0] >= MAX_ATTEMPTS:
                gave_up_now += 1
                # последняя попытка: сводка больше не отправляется — сказать об этом в бот простым текстом, без разметки
                err2 = post({"text": f"Сводка цикла #{rid} «{part(title, TITLE_LIMIT)}» не ушла после {MAX_ATTEMPTS} "
                                     f"попыток и больше не отправляется: {err}. Текст — в kabinet_data.agent_cycle_reports."})
                if err2:
                    errors.append(f"и уведомление о потере сводки #{rid} не ушло: {err2}")
            errors.append(err)
        else:
            cur.execute("UPDATE kabinet_data.agent_cycle_reports SET sent_at = now(), send_error = NULL WHERE id = %s", (rid,))
            sent += 1

note = (f"отправлено {sent} из {len(rows)}" + (f"; ошибка: {errors[0]}" if errors else "")
        + (f"; не отправляются после {MAX_ATTEMPTS} попыток: {given_up + gave_up_now}" if given_up + gave_up_now else ""))
print(note)
# ── пульс — последним и безусловно ──
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 12)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                (JOB_NAME, note[:900]))
if errors:
    raise RuntimeError(f"сводка цикла не ушла в бот: {errors[0]}")
