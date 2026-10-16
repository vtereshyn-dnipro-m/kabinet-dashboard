# Databricks notebook source
# DBTITLE 1,Kabinet - Alerts Bot: подписка на тревоги через @kabinet_dm_alerts_bot
# Kabinet - Alerts Bot (с 16.10.2026, решение владельца), каждые 10 минут.
#
# Подписка на тревоги через бота вместо отдельного секрета на каждого получателя:
#   /start  — заявка: человеку «заявка у владельца», владельцу (основной чат kabinet-alerts/telegram-chat-id) — сообщение
#             с кнопками «Разрешить» / «Отклонить»;
#   кнопка  — решение пишется в kabinet_data.telegram_subscribers (кто и когда), человеку — ответ. Разрешённый получает
#             те же тревоги, что владелец: каждая джоба-отправитель после основного чата шлёт копию активным подписчикам
#             (функция tg_to_subscribers в каждом ноутбуке);
#   /stop   — отписка (status = stopped). Новая /start — снова через разрешение.
# Владелец (основной чат) подписан всегда: его в таблице нет, отписаться нельзя. Принимаются только личные чаты.
# Кнопки слушаем только из основного чата. Обновления читаем getUpdates (вебхука у бота нет: для него нужен публичный
# HTTPS-приёмник), смещение — kabinet_data.telegram_bot_state, сдвигается только после записи решений в базу.
# Параметр dry_run=1 — прочитать обновления и показать, что было бы сделано, ничего не подтверждая и не отправляя.
# Метка пульса — последней и безусловно; не ушло сообщение владельцу — прогон падает после неё.

# COMMAND ----------

import html
import json
import datetime as dt
import psycopg2
import requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Alerts Bot"
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
TOKEN = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")
OWNER = str(dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")).strip()
API = f"https://api.telegram.org/bot{TOKEN}"
w = WorkspaceClient()


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


def tg(method, **payload):
    if DRY and method != "getUpdates":
        print(f"  [проба] {method}: {json.dumps(payload, ensure_ascii=False)[:200]}")
        return {"ok": True, "result": {}}
    r = requests.post(f"{API}/{method}", json=payload, timeout=40)
    try:
        return r.json()
    except Exception:
        return {"ok": False, "description": f"HTTP {r.status_code}"}


def who(u):
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or str(u.get("id"))
    return name + (f" (@{u['username']})" if u.get("username") else "")


with pg() as c, c.cursor() as cur:
    cur.execute("SELECT value FROM kabinet_data.telegram_bot_state WHERE key = 'update_offset'")
    row = cur.fetchone()
offset = int(row[0]) if row and row[0] else 0

upd = tg("getUpdates", offset=offset, timeout=0, limit=100, allowed_updates=["message", "callback_query"])
if not upd.get("ok"):
    raise RuntimeError(f"getUpdates: {upd.get('description')}")
updates = upd.get("result") or []

actions, owner_errors, notes = [], [], []
now = dt.datetime.now(dt.timezone.utc)
with pg() as c, c.cursor() as cur:
    for u in updates:
        offset = max(offset, u["update_id"] + 1)
        msg, cb = u.get("message"), u.get("callback_query")
        if msg and msg.get("text"):
            chat, frm = msg["chat"], msg.get("from") or {}
            cmd = msg["text"].strip().split()[0].split("@")[0].lower()
            cid = str(chat["id"])
            if chat.get("type") != "private":
                continue                                     # тревоги — только в личные чаты; группы молча пропускаем
            if cmd not in ("/start", "/stop"):
                tg("sendMessage", chat_id=cid, text="Команды: /start — подписаться на тревоги Кабинета, /stop — отписаться.")
                continue
            if cid == OWNER:
                tg("sendMessage", chat_id=cid, text="Вы владелец канала тревог — подписаны всегда, отписка не предусмотрена.")
                continue
            cur.execute("SELECT status, requested_at FROM kabinet_data.telegram_subscribers WHERE chat_id = %s", (int(cid),))
            cur_row = cur.fetchone()
            status = cur_row[0] if cur_row else None
            if cmd == "/stop":
                if status in ("active", "pending"):
                    cur.execute("""UPDATE kabinet_data.telegram_subscribers SET status = 'stopped', stopped_at = now(),
                                   updated_at = now() WHERE chat_id = %s""", (int(cid),))
                    tg("sendMessage", chat_id=cid, text="Вы отписаны от тревог Кабинета. /start — подписаться снова (через разрешение).")
                    r = tg("sendMessage", chat_id=OWNER, text=f"ℹ️ Отписался от тревог: {who(frm)}")
                    actions.append(f"stop {cid}")
                else:
                    tg("sendMessage", chat_id=cid, text="Вы не подписаны. /start — подать заявку.")
                continue
            # /start
            if status == "active":
                tg("sendMessage", chat_id=cid, text="Вы уже подписаны на тревоги Кабинета. /stop — отписаться.")
                continue
            if status == "pending" and cur_row[1] and now - cur_row[1] < dt.timedelta(hours=24):
                tg("sendMessage", chat_id=cid, text="Заявка уже у владельца — ответ придёт сюда.")
                continue
            cur.execute("""INSERT INTO kabinet_data.telegram_subscribers (chat_id, name, username, status, requested_at, updated_at)
                           VALUES (%s, %s, %s, 'pending', now(), now())
                           ON CONFLICT (chat_id) DO UPDATE SET name = EXCLUDED.name, username = EXCLUDED.username,
                               status = 'pending', requested_at = now(), approved_by = NULL, approved_at = NULL,
                               stopped_at = NULL, updated_at = now()""",
                        (int(cid), who(frm), frm.get("username")))
            r = tg("sendMessage", chat_id=OWNER, parse_mode="HTML",
                   text=f"🔔 <b>Заявка на тревоги Кабинета</b>\n{html.escape(who(frm))}, chat_id {cid}",
                   reply_markup={"inline_keyboard": [[{"text": "✅ Разрешить", "callback_data": f"sub:ok:{cid}"},
                                                      {"text": "❌ Отклонить", "callback_data": f"sub:no:{cid}"}]]})
            if not r.get("ok"):
                owner_errors.append(f"заявка {cid}: {r.get('description')}")
            tg("sendMessage", chat_id=cid, text="Заявка отправлена владельцу. Когда он разрешит, сюда начнут приходить тревоги Кабинета.")
            actions.append(f"request {cid}")
        elif cb:
            data, frm = cb.get("data") or "", cb.get("from") or {}
            src_chat = str(((cb.get("message") or {}).get("chat") or {}).get("id"))
            if not data.startswith("sub:") or src_chat != OWNER:
                tg("answerCallbackQuery", callback_query_id=cb["id"], text="Решение принимается только в чате владельца.")
                continue
            _, verdict, cid = data.split(":", 2)
            cur.execute("SELECT status, name FROM kabinet_data.telegram_subscribers WHERE chat_id = %s", (int(cid),))
            cur_row = cur.fetchone()
            if not cur_row or cur_row[0] != "pending":
                tg("answerCallbackQuery", callback_query_id=cb["id"],
                   text=f"Заявки уже нет (статус: {cur_row[0] if cur_row else 'нет'}).")
                continue
            new_status = "active" if verdict == "ok" else "rejected"
            cur.execute("""UPDATE kabinet_data.telegram_subscribers SET status = %s, approved_by = %s, approved_at = now(),
                           updated_at = now() WHERE chat_id = %s""", (new_status, who(frm), int(cid)))
            tg("answerCallbackQuery", callback_query_id=cb["id"], text="Разрешено" if verdict == "ok" else "Отклонено")
            mark = "✅ Разрешено" if verdict == "ok" else "❌ Отклонено"
            tg("editMessageText", chat_id=OWNER, message_id=cb["message"]["message_id"], parse_mode="HTML",
               text=f"{mark}: {html.escape(cur_row[1] or cid)} — {html.escape(who(frm))}, {now:%d.%m %H:%M} UTC")
            tg("sendMessage", chat_id=cid, text=(
                "Подписка включена: сюда будут приходить те же тревоги Кабинета, что и владельцу. /stop — отписаться."
                if verdict == "ok" else "Заявка на тревоги Кабинета отклонена."))
            actions.append(f"{new_status} {cid}")
    if DRY:
        c.rollback()
    else:
        cur.execute("""INSERT INTO kabinet_data.telegram_bot_state (key, value, updated_at) VALUES ('update_offset', %s, now())
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""", (str(offset),))

with pg() as c, c.cursor() as cur:
    cur.execute("SELECT count(*) FILTER (WHERE status = 'active'), count(*) FILTER (WHERE status = 'pending') "
                "FROM kabinet_data.telegram_subscribers")
    n_active, n_pending = cur.fetchone()
note = (f"обновлений {len(updates)}, действий {len(actions)}" + (f" ({', '.join(actions)[:300]})" if actions else "")
        + f"; подписчиков {n_active}, заявок {n_pending}" + (f"; владельцу НЕ ушло: {owner_errors}" if owner_errors else ""))
print(("ПРОБА: " if DRY else "") + note)
if DRY:
    dbutils.notebook.exit(note)

# ── пульс — последним и безусловно ──
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                (JOB_NAME, note[:900]))
if owner_errors:
    raise RuntimeError(f"заявка не дошла до владельца: {owner_errors}")
