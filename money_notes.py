# money_notes.py — каждая цифра объясняет себя сама (решение владельца 06.10.2026)
"""Одна функция подписей на весь Кабинет, чтобы «с НДС · Amazon · по дате заказа» звучало одинаково на
«Обзоре», в «Деньгах», «Рекламе», «Остатках» и в недельном отчёте.

Три вещи:

1. **Подпись под денежной карточкой** — видимая, мелким шрифтом: с НДС или без · какие каналы · по какой
   дате (+ уточнение: «после возвратов»). Подсказка ⓘ остаётся, но её первая фраза — всегда «С НДС.» или
   «Без НДС.»: `money_metric` дописывает её сам, если текст сам этого не говорит.
2. **Сравнение периодов** — только одинаковые ПОЛНЫЕ периоды. Текущий период кончается на последнем
   «отлежавшемся» дне (`settled_last`), прошлый — столько же дней встык перед текущим. Подпись дельты
   называет, с чем сравниваем: «−30,2 % к 27.09–30.09». Главное здесь — РАВНАЯ длина: −38 % «Выручки» за
   01–05.10 дало сравнение четырёх дней данных с пятью, а не недогруженный день.
3. **Подпись над графиком** — что показано: величина · НДС · каналы · дата · период.

Когда день «полон» — замер 06.10.2026 по истории версий сырья (Delta хранит 7 дней): у Amazon загрузчик
перечитывает последние три дня, и на D+1 у дня 98,7 % окончательной суммы (худший 96 %), окончательно — на D+3;
у Leroy Merlin, ManoMano и Carrefour — 100 % с первой загрузки. Поэтому задержка — по площадке:
`reorder_params.kpi_day_settle_days_<amz|lm|mm|cf>`. Отношение «экономика / витрина» как признак НЕ годится:
каждый десятый обычный день ниже 0,66 — так и 05.10 с его 0,65 оказался нормальным днём, а не недогруженным.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from i18n import t

VAT_INCL, VAT_EXCL, VAT_NONE = "incl", "excl", None


def note(vat: str | None, channels: str, basis: str | None = None, extra: str | None = None) -> str:
    """«с НДС · Amazon · по дате заказа · после возвратов». Части — ключи словаря `mn.*`, чтобы на всех
    страницах одно и то же называлось одними словами."""
    parts = []
    if vat:
        parts.append(t(f"mn.vat.{vat}"))
    if channels:
        parts.append(t(f"mn.ch.{channels}") if not channels.startswith("=") else channels[1:])
    if basis:
        parts.append(t(f"mn.basis.{basis}"))
    if extra:
        parts.append(extra)
    return " · ".join(parts)


def help_with_vat(vat: str | None, text: str | None) -> str | None:
    """Подсказка, которая явно говорит «С НДС» / «Без НДС» первой фразой."""
    if not vat:
        return text
    lead = t(f"mn.help_lead.{vat}")
    body = (text or "").strip()
    low = body.lower()
    if low.startswith(lead.lower().rstrip(".")):
        return body
    return f"{lead} {body}".strip()


def money_metric(col, label: str, value: str, *, vat: str | None, channels: str, basis: str | None = None,
                 extra: str | None = None, help: str | None = None, delta=None, delta_color: str = "normal",
                 **metric_kw):
    """Карточка с видимой подписью под цифрой. `col` — колонка или контейнер; прочие параметры
    (`delta_arrow` и т. п.) уходят в `st.metric` как есть."""
    col.metric(label, value, delta=delta, delta_color=delta_color, help=help_with_vat(vat, help), **metric_kw)
    col.caption(note(vat, channels, basis, extra))


def chart_note(what: str, vat: str | None, channels: str, basis: str | None, d_from=None, d_to=None,
               extra: str | None = None, where=None) -> None:
    """Мелкая подпись НАД графиком: что показано, НДС, каналы, дата, период."""
    per = ""
    if d_from is not None and d_to is not None:
        f, to = pd.Timestamp(d_from), pd.Timestamp(d_to)
        fmt = "%d.%m.%Y" if f.year != to.year else "%d.%m"
        per = f"{f.strftime(fmt)}–{to.strftime('%d.%m.%Y')}"
    txt = " · ".join(p for p in (what, note(vat, channels, basis, extra), per) if p)
    (where or st).caption(txt)


# ── полные дни и сравнение ────────────────────────────────────────────────────

@dataclass
class DayStatus:
    settled: pd.Timestamp       # последний день, полный по всем действующим каналам
    provisional: pd.Timestamp   # первый день, который площадка ещё может уточнить (NaT — таких нет)
    gap_pct: float              # на сколько, по замеру, предварительный день может сдвинуться
    today: pd.Timestamp = pd.NaT   # сегодня по Киеву — по базе, а не по часам сервера (он живёт в UTC)


_DAY_STATUS_SQL = """
    WITH mk AS (
        SELECT DISTINCT upper(v.marketplace_code) AS code, lower(p.short_name) AS plat
        FROM kabinet_data.v_marketplaces v
        JOIN kabinet_data.platforms p ON p.full_name = v.channel),
    runs AS (
        SELECT mk.plat, max(e.updated_at) AS last_run, max(e.sales_date) AS last_day
        FROM kabinet_data.economics_summary e
        JOIN mk ON mk.code = upper(e.marketplace)
        WHERE e.sales_date >= CURRENT_DATE - 30
        GROUP BY 1),
    p AS (SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'kpi_%%')
    SELECT r.plat,
           -- updated_at — UTC без зоны: сначала назвать зону, потом перевести в Киев
           (r.last_run AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::date AS run_day,
           r.last_day,
           COALESCE((SELECT value::int FROM p WHERE key = 'kpi_day_settle_days_' || r.plat),
                    (SELECT value::int FROM p WHERE key = 'kpi_day_settle_days'), 2) AS settle,
           COALESCE((SELECT value::int FROM p WHERE key = 'kpi_day_final_days_' || r.plat),
                    (SELECT value::int FROM p WHERE key = 'kpi_day_settle_days_' || r.plat),
                    (SELECT value::int FROM p WHERE key = 'kpi_day_settle_days'), 2) AS final,
           COALESCE((SELECT value::numeric FROM p WHERE key = 'kpi_day_provisional_gap_pct_' || r.plat), 0) AS gap,
           COALESCE((SELECT value::int FROM p WHERE key = 'kpi_channel_active_days'), 3) AS active_days,
           (now() AT TIME ZONE 'Europe/Kyiv')::date AS today
    FROM runs r
"""


def day_status(conn) -> DayStatus:
    """Граница полных дней и «предварительные» дни — по времени ПОСЛЕДНЕЙ загрузки каждого канала.

    Задержка у каналов разная (замер 06.10.2026 по истории версий сырья — Delta хранит 7 дней): у Amazon
    загрузчик перечитывает последние три дня, на D+1 у дня 98,7 % окончательной суммы (худший 96 %),
    окончательно — после загрузки D+3; у Leroy Merlin, ManoMano и Carrefour — 100 % с первой загрузки.
    Настройки по площадке в `reorder_params`: `kpi_day_settle_days_<amz|lm|mm|cf>` — через сколько суток
    после дня он идёт в цифры (Amazon 1, решение владельца 06.10.2026), `kpi_day_final_days_<…>` — когда
    перестаёт уточняться (Amazon 3), `kpi_day_provisional_gap_pct_<…>` — на сколько может уточниться (1 %).

    Почему по ЗАПУСКУ, а не по строкам дня: строк за день может не быть по двум разным причинам — канал не
    продавал или его загрузчик ещё не прошёл. Утром до 12:30 строк Amazon и Leroy Merlin за вчера нет, а
    ManoMano и Carrefour (09:00 и 09:30) уже есть; правило «по строкам» объявило бы вчера полным, и период
    сравнил бы неполный день с полным. По запуску день D полон, только когда КАЖДЫЙ действующий канал
    загружался не раньше D + своя задержка. Канал, не загружавшийся дольше `kpi_channel_active_days` (3),
    границу не держит: мёртвый загрузчик ловят сторож и паспорт, а страница не должна застыть вместе с ним."""
    cur = conn.cursor()
    cur.execute(_DAY_STATUS_SQL)
    rows = cur.fetchall()
    if not rows:
        return DayStatus(pd.NaT, pd.NaT, 0.0)
    today = rows[0][-1]
    settled, prov, gap = None, None, 0.0
    for plat, run_day, last_day, settle, final, g, active_days, _today in rows:
        if (today - run_day).days > active_days:
            continue
        s_ = run_day - timedelta(days=int(settle))
        settled = s_ if settled is None else min(settled, s_)
        if int(final) > int(settle):
            p_ = run_day - timedelta(days=int(final) - 1)   # перечитан на загрузке D+final — уже окончателен
            prov = p_ if prov is None else min(prov, p_)
            gap = max(gap, float(g or 0))
    return DayStatus(pd.Timestamp(settled) if settled else pd.NaT,
                     pd.Timestamp(prov) if prov else pd.NaT, gap, pd.Timestamp(today))


def settled_last(conn, _unused=None) -> pd.Timestamp:
    """Последний полный день — см. `day_status`."""
    return day_status(conn).settled


def provisional_text(st_: DayStatus, cur_from, cur_to) -> str:
    """«вчера (05.10) предварительно, Amazon может уточнить до ~1 %» — для дней периода, которые площадка ещё
    перечитывает. Пусто, если таких дней в периоде нет."""
    if pd.isna(st_.provisional) or cur_to is None or pd.isna(cur_to):
        return ""
    f = max(pd.Timestamp(st_.provisional), pd.Timestamp(cur_from))
    to = pd.Timestamp(cur_to)
    if f > to:
        return ""
    yesterday = (st_.today if pd.notna(st_.today) else pd.Timestamp(date.today())) - pd.Timedelta(days=1)
    if f == to:
        days = t("mn.prov_yesterday", d=to.strftime("%d.%m")) if to == yesterday else to.strftime("%d.%m")
    else:
        days = f"{f.strftime('%d.%m')}–{to.strftime('%d.%m')}"
    txt = t("mn.provisional", days=days, gap=f"{st_.gap_pct:g}")
    return txt[:1].upper() + txt[1:]   # идёт второй фразой в строке про период


@dataclass
class Window:
    cur_from: pd.Timestamp
    cur_to: pd.Timestamp
    prev_from: pd.Timestamp
    prev_to: pd.Timestamp
    days: int
    cut_from: pd.Timestamp | None   # первый день, отрезанный как неполный (None — ничего не резали)


def windows(d_from, d_to, last_full) -> Window:
    """Текущий период — [d_from, min(d_to, last_full)], прошлый — столько же дней встык перед ним."""
    f = pd.Timestamp(d_from)
    to = pd.Timestamp(d_to)
    cut = None
    if pd.notna(last_full) and pd.Timestamp(last_full) < to:
        cut = pd.Timestamp(last_full) + pd.Timedelta(days=1)
        to = pd.Timestamp(last_full)
    n = max((to - f).days + 1, 0)
    return Window(f, to, f - pd.Timedelta(days=n), f - pd.Timedelta(days=1), n, cut)


def delta_text(cur_val: float, prev_val: float, w: Window, prev_days_with_data: int | None = None) -> str | None:
    """«−30,2 % к 27.09–30.09». Нет полного прошлого периода (данных меньше, чем дней) — None: сравнение
    с половиной периода показало бы рост или обвал, которого не было."""
    if w.days <= 0 or not prev_val or prev_val <= 0:
        return None
    if prev_days_with_data is not None and prev_days_with_data < w.days:
        return None
    pct = (cur_val - prev_val) / prev_val * 100
    return t("mn.delta_vs", p=f"{pct:+.1f}",
             f=w.prev_from.strftime("%d.%m"), to=w.prev_to.strftime("%d.%m"))
