# money_notes.py — каждая цифра объясняет себя сама (решение владельца 06.10.2026)
"""Одна функция подписей на весь Кабинет, чтобы «с НДС · Amazon · по дате заказа» звучало одинаково на
«Обзоре», в «Деньгах», «Рекламе», «Остатках» и в недельном отчёте.

Три вещи:

1. **Подпись под денежной карточкой** — видимая, мелким шрифтом: с НДС или без · какие каналы · по какой
   дате (+ уточнение: «после возвратов»). Подсказка ⓘ остаётся, но её первая фраза — всегда «С НДС.» или
   «Без НДС.»: `money_metric` дописывает её сам, если текст сам этого не говорит.
2. **Сравнение периодов** — только одинаковые ПОЛНЫЕ периоды. Последний день Amazon догружается: экономика
   за вчера приходит утром неполной и дозаполняется следующими прогонами (06.10.2026: 05.10 — 988 € против
   1 512 € в витрине, отношение 0,65 при обычных 0,76–0,82). Поэтому период кончается на последнем
   «отлежавшемся» дне (`settled_last`), а прошлый период — столько же дней встык перед текущим.
   Подпись дельты называет, с чем сравниваем: «−30,2 % к 27.09–30.09».
3. **Подпись над графиком** — что показано: величина · НДС · каналы · дата · период.

Отношение «экономика / витрина» как признак неполного дня НЕ годится: на двух месяцах каждый десятый
обычный день ниже 0,66. Признак — время загрузки: день D считается полным, если его строки загружены не
раньше D + `kpi_day_settle_days` (настройка в `reorder_params`, по умолчанию 2).
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

def settle_days(conn) -> int:
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'kpi_day_settle_days'")
        r = cur.fetchone()
        return int(r[0]) if r else 2
    except Exception:
        return 2


def settled_last(conn, amazon_codes) -> pd.Timestamp:
    """Последний полный день экономики Amazon: строки дня загружены не раньше D + kpi_day_settle_days.

    Каналы Mirakl приходят сразу и полными, поэтому граница — по Amazon (как у `util.data_boundary`).
    Нет строк Amazon — NaT, и вызывающий берёт свою обычную границу."""
    codes = sorted({str(c).strip().upper() for c in (amazon_codes or []) if str(c).strip()})
    if not codes:
        return pd.NaT
    n = settle_days(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT max(sales_date) FROM (
            SELECT sales_date, max(updated_at) AS loaded
            FROM kabinet_data.economics_summary
            WHERE upper(marketplace) = ANY(%s) AND sales_date >= CURRENT_DATE - 120
            GROUP BY sales_date) d
        WHERE loaded::date >= sales_date + %s
    """, (codes, n))
    r = cur.fetchone()
    return pd.Timestamp(r[0]) if r and r[0] is not None else pd.NaT


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
