# Databricks notebook source
# DBTITLE 1,Kabinet - Morning Report: утренняя сводка ночи — в бот одним сообщением
# Kabinet - Morning Report (19.10.2026, решение владельца), 08:00 Kyiv, под владельцем.
# Одно сообщение в основной чат: как прошла ночь (20:00 вчера — сейчас) у джоб Amazon API — наших, Дарины и Listing
# Suite: ✅ записали свои таблицы, ❌ упали или «зелёные, но без записи», ⏳ ещё идут или не запустились по расписанию;
# 429 за ночь по джобам и видам квоты; открытые тревоги. Источник — kabinet_data.amazon_run_checks (её пишет
# Kabinet - Amazon Run Check по истории таблиц и выводу прогонов) и Jobs API (что идёт сейчас). Amazon не вызывает.
# С 20.10.2026 (решение владельца) — два блока: «Техника» (джобы, 429, тревоги area = 'tech') и «Бизнес» (тревоги
# area = 'business': дефицит, остатки, заказы ждут подтверждения); блок — по incident_types.area, тип без area — в
# технику, чтобы новый тип заметили. ✅ только числом, расписаны ❌ и ⏳; из тревог — новые за ночь и все critical,
# остальное одной строкой. Каждая отправка (текст и итог) — в kabinet_data.morning_reports.
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
    cur.execute("""SELECT job_id, job_name, owner, check_write, quiet_days FROM kabinet_data.amazon_api_jobs
                   WHERE is_active""")
    JOBS = {int(r[0]): dict(zip(("job_id", "job_name", "owner", "check_write", "quiet_days"), r)) for r in cur.fetchall()}
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
                          coalesce(t.area, 'tech') AS area, i.sku, i.warehouse_name,
                          coalesce(i.created_at AT TIME ZONE 'UTC', '1970-01-01'::timestamptz) AS created,
                          coalesce(i.created_at AT TIME ZONE 'UTC' >= %s, false) AS is_new
                   FROM kabinet_data.incidents i LEFT JOIN kabinet_data.incident_types t USING (incident_type)
                   WHERE i.status <> 'resolved' AND i.resolved_at IS NULL""", (w_from,))
    OPEN = cur.fetchall()
    # продажи SKU за 30 дней по позавчера (с НДС, все каналы) — порядок имён у тревог по SKU: сначала то, что продаётся
    # больше (решение владельца 20.10.2026). По позавчера, а не по вчера: в 08:00 вчерашний день Amazon ещё не лёг
    # (Sales & Traffic приходит ~09:30), и окно было бы в 29 дней у Amazon и в 30 у остальных
    # границы — по Киеву и одним местом для запроса и подписи (CURRENT_DATE базы — UTC, расходится с 00:00 до 03:00)
    SALES_TO = now.date() - dt.timedelta(days=2)
    cur.execute("""SELECT norm_sku, sum(sales_vat_incl) FROM kabinet_data.v_sku_sales_vat_incl_daily
                   WHERE date BETWEEN %s AND %s GROUP BY 1""", (SALES_TO - dt.timedelta(days=29), SALES_TO))
    SALES30 = {str(k): float(v or 0) for k, v in cur.fetchall()}
    # те же продажи по каналу — у «нет остатка» видно, откуда продажи (20.10.2026: у трёх SKU «52+ дн» без FBA все продажи
    # Amazon оказались FBM, остальное — Leroy Merlin, Carrefour, ManoMano). Подпись канала — из справочника рынков
    cur.execute("""SELECT s.norm_sku, s.marketplace, coalesce(m.channel, s.marketplace), sum(s.sales_vat_incl)
                   FROM kabinet_data.v_sku_sales_vat_incl_daily s
                   LEFT JOIN (SELECT DISTINCT marketplace_code, channel FROM kabinet_data.v_marketplaces) m
                          ON m.marketplace_code = s.marketplace
                   WHERE s.date BETWEEN %s AND %s GROUP BY 1, 2, 3""", (SALES_TO - dt.timedelta(days=29), SALES_TO))
    SALES30_CH = {}
    for k, mk, chan, v in cur.fetchall():
        SALES30_CH.setdefault(str(k), []).append((str(mk), str(chan), float(v or 0)))
    # Amazon: FBA или FBM — по заказам за то же окно (AFN / MFN)
    cur.execute("""SELECT SUBSTRING(sku FROM '([0-9]{5,})'), marketplace_code, fulfillment_channel
                   FROM kabinet_data.orders_history
                   WHERE purchase_date::date BETWEEN %s AND %s AND order_status <> 'Canceled'
                   GROUP BY 1, 2, 3""", (SALES_TO - dt.timedelta(days=29), SALES_TO))
    AMZ_FUL = {}
    for b, mk, fc in cur.fetchall():
        if b:
            AMZ_FUL.setdefault((str(b), str(mk)), set()).add({"AFN": "FBA", "MFN": "FBM"}.get(str(fc), str(fc)))
    # последний день с остатком по SKU и складу — «без остатка N дн» (решение владельца 20.10.2026). Остаток считается
    # как в Kabinet - Stock Loader, который заводит out_of_stock: Amazon — доступное к продаже из MYI
    # (kabinet_data.fba_inventory: строка рынка ES, иначе первого, пулы EU и UK), площадки — available из stock_local.
    # Остатка за всю историю снимков не было — дни от первого снимка с «+» (история FBA — с 29.08.2026)
    cur.execute("""
        WITH per_asin AS (
            SELECT snapshot_date AS d, sku, asin, marketplace, afn_fulfillable_qty AS q,
                   row_number() OVER (PARTITION BY snapshot_date, marketplace, asin ORDER BY sku) AS rn
            FROM kabinet_data.fba_inventory),
        pool AS (
            SELECT d, sku, q, CASE WHEN marketplace = 'co.uk' THEN 'Amazon FBA UK' ELSE 'Amazon FBA EU' END AS wh,
                   row_number() OVER (PARTITION BY d, asin, marketplace = 'co.uk'
                                      ORDER BY CASE marketplace WHEN 'es' THEN 0 ELSE 1 END, marketplace) AS pool_rn
            FROM per_asin WHERE rn = 1),
        fba AS (
            SELECT b, wh, max(d) FILTER (WHERE q > 0) AS last_pos, min(d) AS first_d,
                   (SELECT max(snapshot_date) FROM kabinet_data.fba_inventory) AS last_snap
            FROM (SELECT d, SUBSTRING(sku FROM '([0-9]{5,})') AS b, wh, sum(q) AS q
                  FROM pool WHERE pool_rn = 1 GROUP BY 1, 2, 3) x
            WHERE b IS NOT NULL GROUP BY 1, 2),
        loc AS (
            SELECT SUBSTRING(s.sku FROM '([0-9]{5,})') AS b, s.warehouse_name AS wh,
                   max(s.snapshot_date) FILTER (WHERE s.quantity > 0 AND s.availability_status = 'available') AS last_pos,
                   min(s.snapshot_date) AS first_d, max(c.last_snap) AS last_snap
            FROM kabinet_data.stock_local s
            JOIN (SELECT channel, max(snapshot_date) AS last_snap FROM kabinet_data.stock_local
                  WHERE channel <> 'Amazon' GROUP BY 1) c ON c.channel = s.channel
            WHERE s.channel <> 'Amazon' GROUP BY 1, 2)
        SELECT b, wh, last_pos, first_d, last_snap FROM fba
        UNION ALL SELECT b, wh, last_pos, first_d, last_snap FROM loc""")
    # дни — до последнего снимка источника, а не до сегодня: в 08:00 сегодняшнего снимка ещё нет (решение владельца)
    OOS_HIST = {(str(b), wh): (lp, fd, ls) for b, wh, lp, fd, ls in cur.fetchall() if b}

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


_created = {}


def created_at(jid):
    """Когда джоба создана: слот раньше этого — не пропуск (19.10.2026 доборы, созданные днём, иначе дали бы
    «по расписанию 01:20, прогона нет» за ночь, когда их ещё не было)."""
    if jid not in _created:
        try:
            _created[jid] = dt.datetime.fromtimestamp(w.jobs.get(job_id=jid).created_time / 1000, dt.timezone.utc)
        except Exception as e:
            _errors.append(f"создание {JOBS[jid]['job_name']}: {type(e).__name__}")
            _created[jid] = None
    return _created[jid]


def night_slots(jid):
    """Слоты расписания джобы в окне ночи (20:00–сейчас), без «после <джобы>» и раньше создания джобы."""
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
    if out:
        born = created_at(jid)
        out = [d for d in out if born is None or d >= born]   # не прочитали — считаем слот, как раньше
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
    elif r["wrote"] is False and not J["quiet_days"]:
        # у джоб с quiet_days (Settlements, SQP) прогон без записи — норма; их «давно не пишет» ловит тревога
        # silent_success в Amazon Run Check (20.10.2026 сводка без этого назвала ❌ обычный прогон SQP)
        bad.append(f"❌ {esc(name)} {when} — зелёная, но таблицы не записаны")
    else:
        ok.append(name)                    # ✅ — только числом (решение владельца 20.10.2026)

q429 = {}
for r in RUNS:
    if r["n429"]:
        k = (r["job_name"], r["kinds"] or "")
        q429[k] = q429.get(k, 0) + int(r["n429"])

SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1}


NAMES_MAX = 5                              # имён в строке critical-тревоги, остальные — числом


def who(msg, sku, wh):
    """Кого касается тревога: из метки «[ТИП:имя]» в начале сообщения (джоба, рынок), иначе SKU и склад."""
    m = re.match(r"\[[A-Z0-9_]+:([^\]]+)\]", msg or "")
    if m:
        return m.group(1).removeprefix("Kabinet - ")
    if sku:
        return f"{sku} ({wh})" if wh else str(sku)
    return None


def channels(sku):
    """Продажи SKU за окно по каналу, больше первыми: «Leroy Merlin 1 161 · Carrefour ES 198» (до двух, остальное «…»)."""
    out = []
    for mk, chan, v in sorted(SALES30_CH.get(str(sku), []), key=lambda t: -t[2]):
        if v <= 0:
            continue
        if chan == "Amazon":
            ful = "+".join(sorted(AMZ_FUL.get((str(sku), mk), set())))
            label = f"Amazon {mk}" + (f" {ful}" if ful else "")
        else:
            label = chan + (f" {mk.split('_', 1)[1]}" if "_" in mk else "")
        out.append(f"{label} " + f"{v:,.0f}".replace(",", " "))
    return " · ".join(out[:2]) + (" · …" if len(out) > 2 else "")


def oos_days(sku, wh):
    """Сколько дней без остатка: от последнего снимка с остатком; не было за всю историю — от первого снимка с «+».
    None — истории по SKU и складу нет или остаток есть сегодня (тогда тревога вот-вот закроется)."""
    h = OOS_HIST.get((str(sku), wh)) if sku and wh else None
    if not h:
        return None
    last_pos, first_d, last_snap = h
    if last_snap is None:
        return None
    if last_pos is not None:
        n = (last_snap - last_pos).days
        return str(n) if n > 0 else None
    return f"{(last_snap - first_d).days + 1}+" if first_d else None


def alert_block(area):
    """Строки тревог блока: новые за ночь и все critical — группами по типу (новые первыми, затем важность, свежесть);
    остальное открытое — одной строкой итога по важности. Не «8 самых старых»: 10.10.2026 так в сводке сторожа восемь
    строк «нет остатка» за август закрыли свежие поломки джоб."""
    groups, rest = {}, {}
    for sev, itype, title, msg, ar, sku, wh, created, is_new in OPEN:
        if ar != area:
            continue
        sev = str(sev).lower()
        if not (is_new or sev == "critical"):
            rest[sev] = rest.get(sev, 0) + 1
            continue
        g = groups.setdefault((sev, itype), {"title": title, "n": 0, "new": 0, "last": created, "tok": None, "names": []})
        g["n"] += 1
        if sev == "critical":
            g["names"].append((created, who(msg, sku, wh), SALES30.get(str(sku)) if sku else None,
                               oos_days(sku, wh) if itype == "out_of_stock" else None, sku))
        g["new"] += 1 if is_new else 0
        if created >= g["last"]:
            g["last"] = created
            m = re.match(r"\[([^\]]+)\]", msg or "")
            g["tok"] = m.group(1) if m else None
    top = sorted(groups.items(), key=lambda kv: (-kv[1]["new"], -SEV.get(kv[0][0], 0), -kv[1]["last"].timestamp()))
    out = []
    for (sev, itype), g in top:
        line = (f"• {esc(g['title'])} ({esc(sev)})" + (f" ×{g['n']}" if g["n"] > 1 else "")
                + (f", новых за ночь {g['new']}" if g["new"] else ""))
        # critical — всегда с именами: джоба / рынок / SKU (решение владельца 20.10.2026); свежие первыми, повтор имени
        # не дублируется, «и ещё N» — от числа тревог группы, чтобы сходилось с ×n
        # у тревог по SKU («нет остатка») — по продажам за 30 дней, больше первыми, рядом сумма; остальные — свежие первыми
        by_sales = any(t[2] is not None for t in g["names"])
        order = (sorted(g["names"], key=lambda t: (-(t[2] or 0), -t[0].timestamp())) if by_sales
                 else sorted(g["names"], key=lambda t: t[0], reverse=True))
        names, seen = [], set()
        for _c, x, s30, days, _sku in order:
            if x and x not in seen:
                seen.add(x)
                extra = []
                if by_sales and s30:                            # «SKU (склад)» → «SKU (склад, 9 555 €: …, …)»
                    _ch = channels(_sku) if _sku and len(names) < 3 else ""   # каналы — у первых трёх SKU
                    extra.append(f"{s30:,.0f}".replace(",", " ") + " €" + (f": {_ch}" if _ch else ""))
                if days:
                    extra.append(f"без остатка {days} дн")
                if extra:
                    x = x[:-1] + ", " + ", ".join(extra) + ")" if x.endswith(")") else f"{x} ({', '.join(extra)})"
                names.append(esc(x))
        shown = names[:NAMES_MAX]
        if shown:
            line += (f" — по продажам за 30 дн по {SALES_TO:%d.%m} (с НДС, все каналы)" if by_sales else "") \
                + ": " + ", ".join(shown) + (
                f" и ещё {g['n'] - len(shown)}" if g["n"] > len(shown) else "")
        elif g["tok"] and g["n"] == 1:
            line += f" — <code>{esc(g['tok'])}</code>"
        out.append(line)
    if rest:
        out.append("• ещё открыто: " + ", ".join(f"{s_} {rest[s_]}" for s_ in ("critical", "high", "medium", "low")
                                                 if rest.get(s_)))
    return out


# ── текст ──
lines = [f"🌅 <b>Ночь {w_from:%d.%m} 20:00 → {now:%d.%m %H:%M}</b>"]
if CHECK_MAX_H is None:
    lines.append("⚠️ у проверки прогонов (Amazon Run Check) не задан порог — ни правила здоровья, ни пульса")
elif CHECK_AGE_H is None or CHECK_AGE_H > CHECK_MAX_H:
    lines.append(f"⚠️ проверка прогонов (Amazon Run Check) не работала "
                 + (f"{CHECK_AGE_H:.0f} ч" if CHECK_AGE_H is not None else "ни разу") + " — данные ниже неполные")
lines.append("🛠 <b>Техника</b>")
lines.append(f"Джобы Amazon API: ✅ {len(ok)} · ❌ {len(bad)} · ⏳ {len(wait)}")
lines += bad + wait
if q429:
    tot = sum(q429.values())
    lines.append(f"🧮 <b>429 за ночь: {tot}</b> — " + "; ".join(
        f"{esc(j)} ×{n}" + (f" ({esc(k)})" if k else "") for (j, k), n in sorted(q429.items(), key=lambda kv: -kv[1])))
else:
    lines.append("🧮 429 за ночь: 0")
_tech = alert_block("tech")
lines += ["🔔 Тревоги:"] + _tech if _tech else ["🔔 Тревог нет"]
_biz = alert_block("business")
lines.append("💼 <b>Бизнес</b>")
lines += _biz if _biz else ["Тревог нет"]
if _errors:
    lines.append("⚙️ сбои сводки: " + esc("; ".join(_errors)[:300]))
# обрезка по строкам, не посреди тега: оборванный <b> Telegram с parse_mode=HTML не примет вовсе
text = ""
for i, ln in enumerate(lines):
    if len(text) + len(ln) + 1 > LIMIT - 20:
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

# ── текст отправки — в журнал (своё соединение); сбой записи — в пульс и падение после него ──
_save_err = None
try:
    with pg() as c, c.cursor() as cur:
        cur.execute("""INSERT INTO kabinet_data.morning_reports (report_date, text, sent, error)
                       VALUES (%s, %s, %s, %s)""", (now.date(), text, _send_err is None, _send_err))
except Exception as e:
    _save_err = f"{type(e).__name__}: {str(e)[:200]}"

note = (f"✅ {len(ok)} ❌ {len(bad)} ⏳ {len(wait)}, 429 {sum(q429.values())}, тревог {len(OPEN)}"
        + (f"; не отправлено: {_send_err}" if _send_err else "") + (f"; сбои: {'; '.join(_errors)[:200]}" if _errors else "")
        + (f"; журнал не записан: {_save_err}" if _save_err else ""))
with pg() as c, c.cursor() as cur:
    cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                   VALUES (%s, now(), %s, 26)
                   ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (JOB_NAME, note))
print(f"💓 {JOB_NAME}: {note}")
if _send_err or _save_err:
    raise RuntimeError(f"{JOB_NAME}: " + "; ".join(x for x in (f"сводка не ушла — {_send_err}" if _send_err else "",
                                                             f"журнал не записан — {_save_err}" if _save_err else "") if x))
