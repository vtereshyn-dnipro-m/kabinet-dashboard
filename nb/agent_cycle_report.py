# Databricks notebook source
# DBTITLE 1,Kabinet - Agent Cycle Report: сводки циклов агента — в бот
# Kabinet - Agent Cycle Report (предложение 19.10.2026), каждые 15 минут 08:00–22:45 Kyiv, под владельцем.
# Агент в конце каждого цикла кладёт сводку строкой в kabinet_data.agent_cycle_reports (scratchpad/cycle_report.py);
# здесь неотправленные строки уходят в основной чат и получают sent_at. Секрет бота читает только эта джоба — агент
# его не касается. Не ушло — ошибка в send_error и прогон падает после пульса: молчание канала должно быть красным.

# COMMAND ----------

import html
import psycopg2, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Agent Cycle Report"
w = WorkspaceClient()


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


with pg() as c, c.cursor() as cur:
    cur.execute("""SELECT id, title, done, merged, waiting, problems FROM kabinet_data.agent_cycle_reports
                   WHERE sent_at IS NULL ORDER BY id LIMIT 10""")
    rows = cur.fetchall()

sent, errors = 0, []
for rid, title, done, merged, waiting, problems in rows:
    parts = [f"🤖 <b>{html.escape(title)}</b>"]
    for label, text in (("Сделано", done), ("Смержено само", merged), ("Ждёт вас", waiting), ("Не получилось", problems)):
        if text and text.strip():
            parts.append(f"<b>{label}:</b>\n{html.escape(text.strip())}")
    try:
        r = requests.post(f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                          json={"chat_id": dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"),
                                "text": "\n\n".join(parts)[:4000], "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        err = None if r.ok else f"{r.status_code}: {r.text[:200]}"
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:200]}"
    with pg() as c, c.cursor() as cur:
        if err:
            cur.execute("UPDATE kabinet_data.agent_cycle_reports SET send_error = %s WHERE id = %s", (err, rid))
            errors.append(err)
        else:
            cur.execute("UPDATE kabinet_data.agent_cycle_reports SET sent_at = now(), send_error = NULL WHERE id = %s", (rid,))
            sent += 1

note = f"отправлено {sent} из {len(rows)}" + (f"; ошибки: {errors[0]}" if errors else "")
print(note)
# ── пульс — последним и безусловно ──
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 26)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                (JOB_NAME, note[:900]))
if errors:
    raise RuntimeError(f"сводка цикла не ушла в бот: {errors[0]}")
