# Databricks notebook source
# DBTITLE 1,Kabinet - Alert Close on Write: тревога «таблица не обновилась» закрывается, как только таблица записана
# Kabinet - Alert Close on Write (с 16.10.2026, решение владельца). Запускается ПО ЗАПИСИ в таблицу (table update
# trigger, минута тишины), а не по часам.
#
# Зачем. Тревога «таблица не обновилась» закрывалась только следующим прогоном той джобы, что её завела: #1864
# (ledger_evening, «Ledger не обновился вечером») висела бы до 18:30 следующего дня, хотя Ledger записал таблицу
# в 19:59 того же вечера. Теперь закрытие — событие записи в таблицу.
#
# Какие тревоги и какие таблицы:
#   • ledger_evening ([LEDGER_EVENING]) — dnipro_m.dnipro_m.raw_amazon_fba_inventory_ledger_summary;
#   • source_silent_fail ([SRCSILENT:<job_id>] и [SRCSILENT:<job_id>:retry]) — таблица джобы из
#     kabinet_data.source_job_checks.
# Закрываем, если в таблицу была запись (WRITE / MERGE / …, по DESCRIBE HISTORY) ПОЗЖЕ, чем заведена тревога.
# Триггер джобы обязан смотреть на те же таблицы: новая строка в source_job_checks — её таблицу в триггер.
# Параметр dry_run=1 — только показать, что закрылось бы. Метка пульса — последней и безусловно.

# COMMAND ----------

import datetime as dt
import re
from zoneinfo import ZoneInfo
import psycopg2
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Alert Close on Write"
LEDGER_TABLE = "dnipro_m.dnipro_m.raw_amazon_fba_inventory_ledger_summary"
WRITE_OPS = ("WRITE", "MERGE", "UPDATE", "DELETE", "CREATE OR REPLACE TABLE AS SELECT", "REPLACE TABLE AS SELECT",
             "CREATE TABLE AS SELECT", "COPY INTO", "STREAMING UPDATE")
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
w = WorkspaceClient()


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


_last_write = {}


def last_write(table):
    """Время последней записи в таблицу (UTC) по журналу Delta."""
    if table not in _last_write:
        ts = None
        for h in spark.sql(f"DESCRIBE HISTORY {table} LIMIT 50").collect():
            if any(str(h["operation"]).startswith(op) for op in WRITE_OPS):
                t = h["timestamp"]
                t = t.replace(tzinfo=dt.timezone.utc) if t.tzinfo is None else t
                ts = t if ts is None or t > ts else ts
        _last_write[table] = ts
    return _last_write[table]


with pg() as c, c.cursor() as cur:
    cur.execute("SELECT job_id, table_name FROM kabinet_data.source_job_checks WHERE is_active")
    job_table = {str(j): t for j, t in cur.fetchall()}
    # created_at — timestamp без зоны, пишется в UTC (AGENTS.md): читаем с явной зоной
    cur.execute("""SELECT id, incident_type, message, created_at AT TIME ZONE 'UTC'
                   FROM kabinet_data.incidents
                   WHERE incident_type IN ('ledger_evening', 'source_silent_fail') AND status <> 'resolved'""")
    open_inc = cur.fetchall()

closed, kept, errors = [], [], []
for iid, typ, msg, created in open_inc:
    created = created.replace(tzinfo=dt.timezone.utc) if created.tzinfo is None else created
    if typ == "ledger_evening":
        table = LEDGER_TABLE
    else:
        m = re.match(r"\[SRCSILENT:(\d+)", msg or "")
        table = job_table.get(m.group(1)) if m else None
    if not table:
        kept.append(f"#{iid}: таблица не определена")
        continue
    try:
        lw = last_write(table)
    except Exception as e:
        errors.append(f"{table}: {type(e).__name__}: {str(e)[:150]}")
        continue
    if lw is not None and lw > created:
        closed.append((iid, table, lw))
    else:
        kept.append(f"#{iid}: записи после тревоги нет")

if closed and not DRY:
    with pg() as c, c.cursor() as cur:
        for iid, table, lw in closed:
            cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(), resolved_by = %s
                           WHERE id = %s AND status <> 'resolved'""",
                        (f"watchdog-autoclose: таблица {table.split('.')[-1]} записана "
                         f"{lw.astimezone(ZoneInfo('Europe/Kyiv')):%d.%m %H:%M}", iid))

note = (f"открытых тревог {len(open_inc)}, закрыто {len(closed)}"
        + (f" ({', '.join('#' + str(i) for i, _, _ in closed)})" if closed else "")
        + (f"; оставлено: {'; '.join(kept)[:200]}" if kept else "")
        + (f"; сбои: {'; '.join(errors)[:300]}" if errors else ""))
print(("ПРОБА: " if DRY else "") + note)
if DRY:
    dbutils.notebook.exit(note)

# ── пульс — последним и безусловно ──
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                (JOB_NAME, note[:900]))
if errors:
    raise RuntimeError("журнал таблицы не прочитался: " + "; ".join(errors))
