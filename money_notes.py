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

def settled_last(conn, _unused=None) -> pd.Timestamp:
    """Последний день, который полон по ВСЕМ каналам, где за него есть строки.

    Задержка у каналов разная (замер 06.10.2026 по истории версий сырья за 7 дней — больше Delta не
    хранит): у Amazon день дозаполняется, пока загрузчик перечитывает последние три дня (на D+1 —
    98,7 % окончательной суммы, худший день 96 %, окончательно на D+3); у Leroy Merlin, ManoMano и
    Carrefour день полон с первой загрузки (100 % на D+1). Поэтому настройка — по площадке:
    `reorder_params.kpi_day_settle_days_<площадка>` (amz, lm, mm, cf), запасная — `kpi_day_settle_days`.

    День D неполон, если у какого-то канала есть строки за D, загруженные раньше D + задержка этого
    канала. Граница — день перед самым ранним неполным. Канал, у которого за D строк нет (тихий день,
    ManoMano FR), границу не двигает: его молчание — не «не догрузилось», а «не продавал»."""
    cur = conn.cursor()
    cur.execute("""
        WITH mk AS (
            SELECT DISTINCT upper(v.marketplace_code) AS code, lower(p.short_name) AS plat
            FROM kabinet_data.v_marketplaces v
            JOIN kabinet_data.platforms p ON p.full_name = v.channel),
        per AS (
            SELECT mk.plat, e.sales_date, max(e.updated_at) AS loaded
            FROM kabinet_data.economics_summary e
            JOIN mk ON mk.code = upper(e.marketplace)
            WHERE e.sales_date >= CURRENT_DATE - 30
            GROUP BY 1, 2),
        lag AS (
            SELECT per.*, COALESCE(
                (SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'kpi_day_settle_days_' || per.plat),
                (SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'kpi_day_settle_days'),
                2) AS settle
            FROM per)
        SELECT min(sales_date) FILTER (WHERE loaded::date < sales_date + settle), max(sales_date) FROM lag
    """)
    first_open, last_any = cur.fetchone()
    if last_any is None:
        return pd.NaT
    if first_open is None:
        return pd.Timestamp(last_any)
    return pd.Timestamp(first_open) - pd.Timedelta(days=1)


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
