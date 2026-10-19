# Databricks notebook source
# DBTITLE 1,Kabinet - Amazon Auth Guard: ошибка авторизации Amazon — в бот сразу
# Kabinet - Amazon Auth Guard (с 13.10.2026), каждые 15 минут.
#
# Зачем отдельная джоба. 13.10.2026 старый LWA client secret SP-API истёк: реплика Sales & Traffic упала в 08:02 и
# 11:00 с «The LWA secret token you provided has expired», а в бот это пришло только в 13:09 — дневной сводкой сторожа
# и чужими словами («запасная реплика не отработала 26 ч», «сессии устарели»). Сторож ходит раз в сутки и про причину
# падения не знает. Ошибка авторизации — другое событие: её не исправит следующий прогон, а остановит все загрузчики
# Amazon сразу, поэтому она должна дойти до бота в течение 15 минут и своими словами.
#
# Две проверки:
#   1) обмен LWA по ключам из Databricks (скоуп amazon-sp-api): SP-API (lwa-app-id / lwa-client-secret / refresh-token)
#      и Amazon Ads (ads_lwa_*). Сломанный ключ виден ДО того, как упадёт первый загрузчик;
#   2) упавшие за последние 2 часа прогоны ЛЮБЫХ джоб воркспейса (наших и Дарины): если в тексте ошибки — авторизация
#      Amazon (401/403 Unauthorized, invalid_client, invalid_grant, «expired»), тревога с именем джобы и текстом.
#      С 16.10.2026 тревога уходит и подписчикам бота тревог (kabinet_data.telegram_subscribers) — то же, что владельцу.
# Тревога — инцидент amazon_auth (source watchdog, по одному на ключ / джобу: [AMZAUTH:…]) и сообщение в бот сразу, один
# раз при открытии. Закрывается здесь же: ключ снова обменивается / у джобы появился успешный прогон после падения.
# Значения ключей не выводятся и не пишутся никуда. Метка пульса — последней и безусловно.

# COMMAND ----------

import json, re
import datetime as dt
from zoneinfo import ZoneInfo
import psycopg2, requests
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Amazon Auth Guard"


def tg_to_subscribers(text):
    """Копия тревоги подписчикам бота (kabinet_data.telegram_subscribers, status = 'active': /start в
    @kabinet_dm_alerts_bot и разрешение владельца). Основной чат (владелец) шлёт вызывающий код как раньше и он
    подписан всегда. Подписчикам — лучшим усилием: не дошло — причины в ответе, прогон из-за них не падает."""
    import psycopg2 as _tg_pg, requests as _tg_rq
    from databricks.sdk import WorkspaceClient as _TgWC
    try:
        _tg_w = _TgWC()
        _tg_c = _tg_pg.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                               dbname="databricks_postgres", user=_tg_w.current_user.me().user_name, sslmode="require",
                               password=_tg_w.postgres.generate_database_credential(
                                   endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
        try:
            with _tg_c.cursor() as _tg_cur:
                _tg_cur.execute("SELECT chat_id FROM kabinet_data.telegram_subscribers WHERE status = 'active'")
                _tg_subs = [str(r[0]) for r in _tg_cur.fetchall()]
        finally:
            _tg_c.close()
    except Exception as e:
        return [f"подписчики не прочитались: {type(e).__name__}: {str(e)[:120]}"]
    _tg_main = str(dbutils.secrets.get("kabinet-alerts", "telegram-chat-id")).strip()
    _tg_tok = dbutils.secrets.get("kabinet-alerts", "telegram-bot-token")
    _tg_errs = []
    for _tg_chat in _tg_subs:
        if _tg_chat == _tg_main:
            continue
        try:
            _tg_r = _tg_rq.post(f"https://api.telegram.org/bot{_tg_tok}/sendMessage",
                                json={"chat_id": _tg_chat, "text": text[:4000], "parse_mode": "HTML",
                                      "disable_web_page_preview": True}, timeout=30)
            if not _tg_r.ok:
                _tg_errs.append(f"подписчик {_tg_chat}: {_tg_r.status_code} {_tg_r.text[:100]}")
        except Exception as e:
            _tg_errs.append(f"подписчик {_tg_chat}: {type(e).__name__}")
    return _tg_errs


SCOPE = "amazon-sp-api"
# признак ошибки авторизации и признак, что речь об Amazon (у SendCloud и Odoo тоже бывают 401 — это не наше событие)
AUTH_RE = re.compile(r"(HTTP|status|code|Error|createReport|createQuery|get\w*)\W{0,4}40[13]\b[\s\S]{0,160}?"
                     r"(Unauthori[sz]ed|Access to requested resource is denied|expired|invalid)|invalid_client|invalid_grant|"
                     r"unauthorized_client|token you provided has expired|security token included in the request is "
                     r"(expired|invalid)", re.I)
AMZ_RE = re.compile(r"LWA|amazon|sellingpartner|SP-API|advertising-api|createReport|createQuery|Data Kiosk", re.I)
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
dbutils.widgets.text("lookback_h", "2")       # шире — только для проб
LOOKBACK_H = float(dbutils.widgets.get("lookback_h") or 2)
K = ZoneInfo("Europe/Kyiv")
w = WorkspaceClient()
now = dt.datetime.now(dt.timezone.utc)
problems = {}      # токен → (severity, текст)
checked = []

# ── 1. обмен LWA ──
def _lwa(cid_key, sec_key, ref_key, label):
    try:
        r = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type": "refresh_token", "refresh_token": dbutils.secrets.get(SCOPE, ref_key),
            "client_id": dbutils.secrets.get(SCOPE, cid_key), "client_secret": dbutils.secrets.get(SCOPE, sec_key)},
            timeout=30)
    except Exception as e:
        # сеть или Amazon недоступны — это не ключ; пишем в пульс, тревогу не заводим
        checked.append(f"{label}: нет ответа ({type(e).__name__})")
        return
    if r.status_code == 200 and r.json().get("access_token"):
        checked.append(f"{label}: ок")
        return
    try:
        j = r.json()
    except Exception:
        j = {}
    err = f"HTTP {r.status_code} {j.get('error') or ''}: {(j.get('error_description') or r.text)[:200]}"
    checked.append(f"{label}: ОШИБКА")
    problems[f"[AMZAUTH:{label}]"] = ("critical", f"{label}: обмен refresh token на access token не проходит — {err}. "
                                                  f"Все загрузчики с этим ключом остановятся. Заменить ключ в трёх местах: "
                                                  f"Databricks {SCOPE}, Streamlit Secrets Listing Suite и Кабинета.")


_lwa("lwa-app-id", "lwa-client-secret", "refresh-token", "SP-API")
_lwa("ads_lwa_client_id", "ads_lwa_client_secret", "ads_lwa_refresh_token", "Amazon Ads")

# ── 2. упавшие прогоны с ошибкой авторизации ──
# смотрим 2 часа назад, но тревожим, только пока у джобы нет успешного прогона после падения: иначе после починки
# старое падение ещё два часа открывало бы закрытую тревогу заново
since_ms = int((now - dt.timedelta(hours=LOOKBACK_H)).timestamp() * 1000)
seen_jobs = set()
for r in w.jobs.list_runs(start_time_from=since_ms, completed_only=True, expand_tasks=True):
    res = str(getattr(r.state.result_state, "value", r.state.result_state) or "")
    if res in ("SUCCESS", "SKIPPED", "EXCLUDED", "") or r.job_id in seen_jobs:
        continue
    for t in r.tasks or []:
        tres = str(getattr(t.state.result_state, "value", t.state.result_state) or "")
        if tres == "SUCCESS" or t.run_job_task:      # падение дочерней джобы найдём в её собственном прогоне
            continue
        try:
            o = w.jobs.get_run_output(t.run_id)
            text = f"{o.error or ''}\n{o.error_trace or ''}"
        except Exception:
            continue
        if not (AUTH_RE.search(text) and AMZ_RE.search(text)):
            continue
        seen_jobs.add(r.job_id)
        if r.job_id:
            last = next(iter(w.jobs.list_runs(job_id=r.job_id, completed_only=True, limit=1)), None)
            if last is not None and str(getattr(last.state.result_state, "value", "")) == "SUCCESS":
                break                                # после падения уже был успешный прогон
        try:
            jname = w.jobs.get(r.job_id).settings.name if r.job_id else r.run_name
        except Exception:
            jname = r.run_name or str(r.job_id)
        detail = re.search(r'"details"\s*:\s*"([^"]+)"', text) or re.search(r'"error_description"\s*:\s*"([^"]+)"', text)
        snippet = (detail.group(1) if detail else (o.error or text).strip().replace("\n", " "))[:260]
        when = dt.datetime.fromtimestamp(r.start_time / 1000, K).strftime("%d.%m %H:%M")
        problems[f"[AMZAUTH:{jname}]"] = ("high", f"{jname}: прогон {when} упал на авторизации Amazon — {snippet}")
        break

# ── 3. инциденты и бот ──
_cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                      dbname="databricks_postgres", user=w.current_user.me().user_name, password=_cred.token,
                      sslmode="require")
sent, send_err, closed, sub_err = [], [], [], []
with pg, pg.cursor() as cur:
    cur.execute("""SELECT id, message FROM kabinet_data.incidents
                   WHERE incident_type = 'amazon_auth' AND status <> 'resolved'""")
    open_inc = {}
    for iid, msg in cur.fetchall():
        tok = re.match(r"\[AMZAUTH:[^\]]+\]", msg or "")
        if tok:
            open_inc[tok.group(0)] = iid
    new_texts = []
    for tok, (sev, text) in problems.items():
        msg = f"{tok} {text}"
        if tok in open_inc:
            if not DRY:
                cur.execute("UPDATE kabinet_data.incidents SET message = %s, severity = %s WHERE id = %s",
                            (msg, sev, open_inc[tok]))
            continue
        new_texts.append((tok, sev, text))
        if not DRY:
            cur.execute("""INSERT INTO kabinet_data.incidents (incident_type, severity, message, status, source)
                           VALUES ('amazon_auth', %s, %s, 'open', 'watchdog')""", (sev, msg))
    # одно сообщение на прогон: когда ломается ключ, падают все загрузчики разом, и двадцать сообщений подряд
    # читать никто не станет. Ключи — первыми: это причина, джобы — следствие
    new_texts.sort(key=lambda x: x[1] != "critical")
    if new_texts and not DRY:
        def _send(chat, items):
            body = "\n\n".join("• " + x[2] for x in items).replace("&", "&amp;").replace("<", "&lt;")
            try:
                rr = requests.post(f"https://api.telegram.org/bot{dbutils.secrets.get('kabinet-alerts', 'telegram-bot-token')}/sendMessage",
                                   json={"chat_id": chat, "text": ("🔴 <b>Авторизация Amazon</b>\n" + body)[:4000],
                                         "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=30)
                return None if rr.ok else f"{rr.status_code}: {rr.text[:150]}"
            except Exception as e:
                import re as _re_tok   # requests кладёт URL с токеном бота в текст исключения — вырезаем до записи
                _err_text = _re_tok.sub(r"bot\d+:[\w-]+", "bot<токен>", str(e))
                return f"{type(e).__name__}: {_err_text[:150]}"

        err = _send(dbutils.secrets.get("kabinet-alerts", "telegram-chat-id"), new_texts)
        if err:
            send_err.append(err)
        else:
            sent = [x[0] for x in new_texts]
        # копия подписчикам бота тревог (kabinet_data.telegram_subscribers) — то же сообщение, что владельцу; их сбои —
        # в заметку пульса, прогон из-за них не падает
        _body = "\n\n".join("• " + x[2] for x in new_texts).replace("&", "&amp;").replace("<", "&lt;")
        sub_err = tg_to_subscribers(("🔴 <b>Авторизация Amazon</b>\n" + _body)[:4000])
        if send_err:
            # молчание канала должно быть красным: причина — в тексте инцидента (её покажет дневная сводка сторожа),
            # а прогон падает после пульса
            for tok, _, _ in new_texts:
                cur.execute("UPDATE kabinet_data.incidents SET message = message || %s WHERE incident_type = 'amazon_auth' "
                            "AND status <> 'resolved' AND message LIKE %s", (f" В бот сразу не ушло: {send_err[0]}", tok + "%"))
    elif DRY:
        sent = [x[0] for x in new_texts]
    # закрытие: ключ снова обменивается; у джобы после падения был успешный прогон
    for tok, iid in open_inc.items():
        if tok in problems:
            continue
        label = tok[len("[AMZAUTH:"):-1]
        ok_now = label in ("SP-API", "Amazon Ads") and f"{label}: ок" in checked
        if not ok_now and label not in ("SP-API", "Amazon Ads"):
            try:
                jid = next((j.job_id for j in w.jobs.list(name=label)), None)
                last = next(iter(w.jobs.list_runs(job_id=jid, completed_only=True, limit=1)), None) if jid else None
                ok_now = last is not None and str(getattr(last.state.result_state, "value", "")) == "SUCCESS"
            except Exception:
                ok_now = False
        if ok_now and not DRY:
            cur.execute("""UPDATE kabinet_data.incidents SET status = 'resolved', resolved_at = now(),
                           resolved_by = 'watchdog-autoclose: авторизация Amazon снова проходит' WHERE id = %s""", (iid,))
            closed.append(tok)

note = ("; ".join(checked) + f"; тревог {len(problems)}, отправлено {len(sent)}, закрыто {len(closed)}"
        + (f"; в бот НЕ ушло: {', '.join(send_err)}" if send_err else "")
        + (f"; подписчикам не ушло: {'; '.join(sub_err)[:200]}" if sub_err else ""))
print(("ПРОБА: " if DRY else "") + note)
with pg, pg.cursor() as cur:
    if not DRY:
        cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                       VALUES (%s, now(), %s, 1)
                       ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                    (JOB_NAME, note[:900]))
pg.close()
if send_err:
    # молчание канала должно быть красным: прогон падает ПОСЛЕ пульса — тогда это видно и в job_health сторожа
    raise RuntimeError(f"тревога авторизации Amazon не ушла в бот: {send_err}")
if DRY:
    dbutils.notebook.exit(json.dumps({"checked": checked, "new": sent, "problems": {k: v[1][:200] for k, v in problems.items()}}, ensure_ascii=False))
