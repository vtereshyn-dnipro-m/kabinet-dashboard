# Databricks notebook source
# DBTITLE 1,Kabinet - Запасной прогон после Ledger Summary: страховка вечерней цепочки
# Kabinet - Запасной прогон после Ledger Summary — 18:30 Kyiv (с 12.10.2026)
#
# Вечерние Stock Loader и Coverage Projection запускает джоба «Kabinet - После Ledger Summary» — по записи Дарины в
# dnipro_m.raw_amazon_fba_inventory_ledger_summary (вечерний прогон её джобы, сейчас 16:40, длится 8–9 мин). Если
# запись не пришла (её джоба упала, перенесена, Amazon не отдал день) или триггер не сработал, вечернего прогона у нас
# не было бы вовсе. Эта ячейка в 18:30 решает, нужен ли запасной прогон, и сообщает задачам джобы через task value
# need_run; сами Stock Loader и Coverage запускают задачи run_job_task той же джобы (условие по need_run).
#
#   запись Ledger сегодня после 10:00 UTC была и цепочка отработала → ничего не делаем, открытую тревогу закрываем;
#   записи не было                        → запасной прогон + тревога «Ledger не обновился, остатки FBA вчерашние»;
#   запись была, а цепочка не отработала → запасной прогон + тревога «цепочка не сработала».
#
# 10:00 UTC — та же граница, что в условии основной цепочки ({{job.start_time.hour}} — UTC, проверено 12.10.2026):
# утренняя запись (10:40 Kyiv = 07:40/08:40 UTC) вечерней не считается — свежего дня в ней нет.
# Тревога — инцидент ledger_evening (source watchdog, одна на всё, [LEDGER_EVENING]) и сообщение в бот сразу: сторож
# ходит раз в сутки в 13:00, и вечерняя тревога дошла бы на следующий день. Закрывает её этот же ноутбук, когда
# вечерняя запись снова пришла. Метка пульса — последней и безусловно.

# COMMAND ----------

import json
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Запасной прогон после Ledger Summary"
CHAIN_JOB = "Kabinet - После Ledger Summary"
LEDGER = "dnipro_m.dnipro_m.raw_amazon_fba_inventory_ledger_summary"
EVENING_UTC_HOUR = 10
TOKEN = "[LEDGER_EVENING]"
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"

w = WorkspaceClient()
now = dt.datetime.now(dt.timezone.utc)
cut = now.replace(hour=EVENING_UTC_HOUR, minute=0, second=0, microsecond=0)

# ── 1. была ли вечерняя запись Ledger ──
hist = spark.sql(f"SELECT unix_timestamp(timestamp) AS e, operation FROM (DESCRIBE HISTORY {LEDGER} LIMIT 30)").collect()
writes = [h.e for h in hist if h.operation in ("WRITE", "DELETE", "MERGE", "UPDATE", "CREATE OR REPLACE TABLE AS SELECT",
                                                "CREATE TABLE AS SELECT", "REPLACE TABLE AS SELECT")]
last_write = dt.datetime.fromtimestamp(max(writes), dt.timezone.utc) if writes else None
ledger_fresh = last_write is not None and last_write >= cut

# ── 2. отработала ли цепочка: прогон после границы, где Stock Loader дошёл до конца или ещё идёт ──
chain_state = "нет прогона"
chain_id = next((j.job_id for j in w.jobs.list(name=CHAIN_JOB)), None)
if chain_id:
    for r in w.jobs.list_runs(job_id=chain_id, start_time_from=int(cut.timestamp() * 1000), expand_tasks=True):
        for t in r.tasks or []:
            if t.task_key != "stock_loader":
                continue
            life = str(getattr(t.state.life_cycle_state, "value", t.state.life_cycle_state) or "")
            res = str(getattr(t.state.result_state, "value", t.state.result_state) or "")
            if life in ("PENDING", "QUEUED", "RUNNING", "BLOCKED", "WAITING_FOR_RETRY"):
                chain_state = "идёт"
            elif res == "SUCCESS" and chain_state != "идёт":
                chain_state = "ок"
            elif chain_state == "нет прогона":
                chain_state = f"упал ({res or life})"
else:
    chain_state = "джоба цепочки не найдена"
chain_ok = chain_state in ("ок", "идёт")

need_run = not (ledger_fresh and chain_ok)
_kyiv = lambda x: x.astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m %H:%M") if x else "—"
if not ledger_fresh:
    severity = "high"
    msg = (f"{TOKEN} Ledger Summary не обновился до 18:30: последняя запись {_kyiv(last_write)} (Киев). Остатки FBA "
           f"вчерашние. Запасной прогон Stock Loader и Coverage запущен на том, что есть. Проверить джобу «FBA Inventory "
           f"Ledger Summary for Tableau».")
elif not chain_ok:
    severity = "medium"
    msg = (f"{TOKEN} Ledger Summary обновился ({_kyiv(last_write)} Киев), но цепочка «{CHAIN_JOB}» не отработала: "
           f"{chain_state}. Запасной прогон Stock Loader и Coverage запущен. Проверить триггер джобы цепочки.")
else:
    severity, msg = None, None
print(f"Ledger: последняя запись {_kyiv(last_write)} Киев, вечерняя={ledger_fresh}; цепочка: {chain_state}; запасной прогон: {need_run}")
dbutils.jobs.taskValues.set(key="need_run", value="true" if need_run and not DRY else "false")

# ── 3. тревога: инцидент + сообщение в бот; закрытие, когда всё в порядке ──
_cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                      dbname="databricks_postgres", user=w.current_user.me().user_name, password=_cred.token,
                      sslmode="require")
send_error = None
with pg, pg.cursor() as cur:
    cur.execute("""SELECT id FROM kabinet_data.incidents WHERE incident_type = 'ledger_evening'
                   AND status <> 'resolved' AND message LIKE %s""", (TOKEN + "%",))
    open_ids = [r[0] for r in cur.fetchall()]
    if DRY:
        print(f"проба: инцидент {'создать/обновить' if msg else 'закрыть' if open_ids else 'не трогать'}, бот — нет")
    elif msg:
        if open_ids:
            cur.execute("UPDATE kabinet_data.incidents SET message = %s, severity = %s WHERE id = ANY(%s)",
                        (msg, severity, open_ids))
        else:
            cur.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, source)
                           VALUES ('ledger_evening', %s, %s, 'open', 'watchdog')""", (severity, msg))
        try:
            r = requests.post(f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                              json={"chat_id": dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"),
                                    "text": "🔴 <b>Вечерние остатки FBA</b>\n" + msg.replace(TOKEN + " ", ""),
                                    "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=30)
            if not r.ok:
                send_error = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            send_error = f"{type(e).__name__}: {str(e)[:200]}"
        if send_error:
            # прогон здесь НЕ роняем: упавшая проверка отменила бы и запасной прогон, ради которого она есть. Сбой
            # отправки остаётся в тексте инцидента — его покажет дневная сводка сторожа — и в метке пульса
            cur.execute("UPDATE kabinet_data.incidents SET message = message || %s WHERE incident_type = 'ledger_evening' "
                        "AND status <> 'resolved' AND message LIKE %s",
                        (f" В бот сразу не ушло: {send_error}", TOKEN + "%"))
    elif open_ids:
        cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                       resolved_by = 'watchdog-autoclose: вечерняя запись Ledger пришла, цепочка отработала'
                       WHERE id = ANY(%s)""", (open_ids,))

# ── метка пульса — последней и безусловно (кроме пробы: метка без джобы выглядела бы мёртвой джобой) ──
note = (f"Ledger {_kyiv(last_write)}; цепочка: {chain_state}; запасной прогон: {'да' if need_run else 'нет'}"
        + (f"; тревога в бот НЕ ушла: {send_error}" if send_error else ""))
print(f"💓 {JOB_NAME}: {note}" + (" (проба, метка не пишется)" if DRY else ""))
with pg, pg.cursor() as cur:
    if DRY:
        cur.execute("SELECT 1")
    else:
        cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                       VALUES (%s, now(), %s, 30)
                       ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                    (JOB_NAME, note))
pg.close()

if DRY:
    dbutils.notebook.exit(json.dumps({"ledger_last_write_kyiv": _kyiv(last_write), "ledger_fresh": ledger_fresh,
                                      "chain": chain_state, "need_run": need_run, "message": msg}, ensure_ascii=False))
