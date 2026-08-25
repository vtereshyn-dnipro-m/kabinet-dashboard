# pages/7_Reviews.py — Отзывы: монитор запросов на отзывы (Request a Review)
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.9rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("rev.title"))
st.caption(t("rev.caption"))

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"
AMBER = "#f2b134"
GREY = "#9aa4b2"

# цвета статусов покрытия — совпадают в бейдже, прогресс-баре и легенде
ST_COLOR = {"ok": GREEN, "catching": AMBER, "missed": ACCENT, "maturing": GREY}

# панель инструментов Plotly не нужна пользователю дашборда
PLOTLY_CFG = {"displayModeBar": False}

# окно отправки: заказы 8–33 дней от даты покупки
AGE_MIN, AGE_MAX = 8, 33

# время в базе в UTC. Показываем по Мадриду: покупатели и маркетплейсы
# европейские, и решения о времени отправки принимаются в их часовом поясе
TZ = ZoneInfo("Europe/Madrid")

# домены Amazon по каналу продаж — ссылка на листинг строится по стране
# Короткий код рынка для карточек. «Amazon.com.be» в узкую карточку не
# влезает и обрезается до «Amaz…» — по такой подписи страну не опознать.
# Полное название уходит в подсказку карточки
CHANNEL_CODE = {
    "Amazon.es": "ES", "Amazon.de": "DE", "Amazon.fr": "FR", "Amazon.it": "IT",
    "Amazon.nl": "NL", "Amazon.com.be": "BE", "Amazon.se": "SE",
    "Amazon.pl": "PL", "Amazon.co.uk": "UK", "Amazon.ie": "IE",
}


def channel_code(ch) -> str:
    """Короткий код рынка. Незнакомый канал отдаём как есть — лучше
    длинная подпись, чем потерянная строка."""
    key = str(ch or "").strip()
    return CHANNEL_CODE.get(key, key or "—")


CHANNEL_DOMAIN = {
    "Amazon.es": "amazon.es", "Amazon.de": "amazon.de", "Amazon.fr": "amazon.fr",
    "Amazon.it": "amazon.it", "Amazon.nl": "amazon.nl", "Amazon.com.be": "amazon.com.be",
    "Amazon.se": "amazon.se", "Amazon.pl": "amazon.pl", "Amazon.co.uk": "amazon.co.uk",
    "Amazon.ie": "amazon.ie",
}


# ═══════════════════════════════════════════════════════════════════
# ДАННЫЕ
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def table_exists(name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'kabinet_data' AND table_name = %s
        """, (name,))
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_health() -> dict:
    """Сводка состояния рассылки."""
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT
              COUNT(*) FILTER (WHERE status='sent'
                               AND (sent_at AT TIME ZONE 'Europe/Madrid')::date
                                   = (NOW() AT TIME ZONE 'Europe/Madrid')::date) AS today,
              COUNT(*) FILTER (WHERE status='sent'
                               AND sent_at >= NOW() - INTERVAL '7 days')      AS sent7,
              COUNT(*) FILTER (WHERE status='failed'
                               AND checked_at >= NOW() - INTERVAL '7 days')   AS failed7,
              COUNT(*) FILTER (WHERE status='skipped_return')                 AS skipped,
              MAX(sent_at) FILTER (WHERE status='sent')                       AS last_sent,
              COUNT(*)                                                        AS total_rows
            FROM kabinet_data.review_request_log
        """, conn)
    finally:
        conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}


@st.cache_data(ttl=600)
def load_pool() -> pd.DataFrame:
    """Кандидаты в окне, по которым запрос ещё не отправляли."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT o.sales_channel,
                   DATE_PART('day', NOW() - o.purchase_date)::int AS age_days,
                   COUNT(DISTINCT o.order_id)                     AS orders
            FROM kabinet_data.orders_history o
            WHERE o.order_status = 'Shipped'
              AND o.sales_channel LIKE 'Amazon.%%'
              AND o.purchase_date BETWEEN NOW() - INTERVAL '{AGE_MAX} days'
                                      AND NOW() - INTERVAL '{AGE_MIN} days'
              AND NOT EXISTS (
                  SELECT 1 FROM kabinet_data.review_request_log l
                  WHERE l.amazon_order_id = o.order_id
              )
            GROUP BY 1, 2
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_coverage(days: int) -> pd.DataFrame:
    """Покрытие по дате заказа: сколько заказов и сколько обработано."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            WITH ord AS (
                SELECT purchase_date::date AS day,
                       sales_channel,
                       COUNT(DISTINCT order_id) AS orders
                FROM kabinet_data.orders_history
                WHERE order_status = 'Shipped'
                  AND sales_channel LIKE 'Amazon.%%'
                  AND purchase_date >= NOW() - INTERVAL '{days} days'
                GROUP BY 1, 2
            ),
            req AS (
                SELECT o.purchase_date::date AS day,
                       o.sales_channel,
                       COUNT(DISTINCT l.amazon_order_id)
                           FILTER (WHERE l.status = 'sent')            AS sent,
                       COUNT(DISTINCT l.amazon_order_id)
                           FILTER (WHERE l.status = 'no_action')       AS no_action,
                       COUNT(DISTINCT l.amazon_order_id)
                           FILTER (WHERE l.status = 'skipped_return')  AS skipped,
                       COUNT(DISTINCT l.amazon_order_id)
                           FILTER (WHERE l.status = 'failed')          AS errors
                FROM kabinet_data.review_request_log l
                JOIN kabinet_data.orders_history o
                  ON o.order_id = l.amazon_order_id
                WHERE o.purchase_date >= NOW() - INTERVAL '{days} days'
                GROUP BY 1, 2
            )
            SELECT ord.day, ord.sales_channel, ord.orders,
                   COALESCE(req.sent, 0)       AS sent,
                   COALESCE(req.no_action, 0)  AS no_action,
                   COALESCE(req.skipped, 0)    AS skipped,
                   COALESCE(req.errors, 0)     AS errors
            FROM ord
            LEFT JOIN req USING (day, sales_channel)
            ORDER BY ord.day DESC
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_daily(days: int) -> pd.DataFrame:
    """Объём проверок и отправок по дням."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT COALESCE(sent_at, checked_at)::date AS day,
                   COUNT(*) FILTER (WHERE status='sent')            AS sent,
                   COUNT(*) FILTER (WHERE status='no_action')       AS no_action,
                   COUNT(*) FILTER (WHERE status='skipped_return')  AS skipped,
                   COUNT(*) FILTER (WHERE status='failed')          AS failed
            FROM kabinet_data.review_request_log
            WHERE COALESCE(sent_at, checked_at) >= NOW() - INTERVAL '{days} days'
            GROUP BY 1 ORDER BY 1
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_age_stats() -> pd.DataFrame:
    """Доля разрешённых Amazon запросов по возрасту заказа."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT order_age_days AS age,
                   COUNT(*)                                  AS checked,
                   COUNT(*) FILTER (WHERE status='sent')     AS sent
            FROM kabinet_data.review_request_log
            WHERE order_age_days IS NOT NULL
              AND status IN ('sent', 'no_action')
            GROUP BY 1 ORDER BY 1
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_bsr_daily(days: int) -> pd.DataFrame:
    """Сколько товаров поднялось и опустилось в категории за каждый день.
    Медиану по всем не считаем: один товар взлетел с 900 места на 8, другой
    рухнул, а усреднённая линия почти не шевельнулась бы."""
    if not table_exists("asin_bsr_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            WITH d AS (
                SELECT asin, marketplace, snapshot_date, rank,
                       LAG(rank) OVER (PARTITION BY asin, marketplace
                                       ORDER BY snapshot_date) AS rank_prev
                FROM kabinet_data.asin_bsr_daily
                WHERE rank IS NOT NULL
                  AND snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
            )
            SELECT snapshot_date,
                   -- меньше номер значит выше в категории
                   COUNT(*) FILTER (WHERE rank < rank_prev) AS moved_up,
                   COUNT(*) FILTER (WHERE rank > rank_prev) AS moved_down,
                   COUNT(*) FILTER (WHERE rank = rank_prev) AS unchanged,
                   COUNT(*)                                 AS items
            FROM d
            WHERE rank_prev IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_bsr_totals(days: int) -> dict:
    """Итог за период: сколько поднялось, опустилось, и по скольким
    товарам Amazon вообще даёт место в категории."""
    if not table_exists("asin_bsr_daily"):
        return {}
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            WITH bounds AS (
                SELECT MIN(snapshot_date) AS d0, MAX(snapshot_date) AS d1
                FROM kabinet_data.asin_bsr_daily
                WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
            ),
            pairs AS (
                SELECT b.asin, b.marketplace,
                       MAX(CASE WHEN b.snapshot_date = x.d0 THEN b.rank END) AS r0,
                       MAX(CASE WHEN b.snapshot_date = x.d1 THEN b.rank END) AS r1
                FROM kabinet_data.asin_bsr_daily b
                CROSS JOIN bounds x
                WHERE b.rank IS NOT NULL
                  AND b.snapshot_date IN (x.d0, x.d1)
                GROUP BY 1, 2
            )
            SELECT COUNT(*) FILTER (WHERE r1 < r0) AS up,
                   COUNT(*) FILTER (WHERE r1 > r0) AS down,
                   COUNT(*)                        AS tracked
            FROM pairs
            WHERE r0 IS NOT NULL AND r1 IS NOT NULL
        """, conn)
        return df.iloc[0].to_dict() if not df.empty else {}
    except Exception:
        return {}
    finally:
        conn.close()


# расписание разнесли 19 августа: всё, что раньше, шло одним прогоном
# и в сравнение не годится — там сидит разбор старых заказов с долей 3-21%
SLOT_SPLIT_DATE = "2026-08-19"


@st.cache_data(ttl=600)
def load_by_slot(days: int) -> pd.DataFrame:
    """Сравнение расписаний отправки. Смотрим долю разрешённых запросов,
    а не прирост отзывов: первое видно сразу, второе при нашем объёме
    неотличимо от случайности.

    Считаем только с даты разделения расписаний. До неё все запросы шли
    одним прогоном, и утренняя группа вобрала бы в себя две недели разбора
    накопленного — сравнение показало бы разницу, которой нет."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT COALESCE(send_slot, 'morning_default') AS slot,
                   checked_at::date AS day,
                   COUNT(*)                                   AS checked,
                   COUNT(*) FILTER (WHERE status = 'sent')     AS sent
            FROM kabinet_data.review_request_log
            WHERE checked_at >= GREATEST(
                      CURRENT_DATE - INTERVAL '{days} days',
                      DATE '{SLOT_SPLIT_DATE}')
              AND status IN ('sent', 'no_action')
            GROUP BY 1, 2 ORDER BY 2
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_by_hour(days: int) -> pd.DataFrame:
    """Во сколько уходили запросы — по местному времени маркетплейсов.
    Пока все отправки в один час, но данные копятся: через месяц-другой
    можно будет сравнивать, если появится разброс."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT EXTRACT(HOUR FROM sent_at AT TIME ZONE 'Europe/Madrid')::int
                       AS hour,
                   marketplace,
                   COUNT(*) AS sent
            FROM kabinet_data.review_request_log
            WHERE status = 'sent'
              AND sent_at >= NOW() - INTERVAL '{days} days'
            GROUP BY 1, 2 ORDER BY 1
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_by_asin(days: int) -> pd.DataFrame:
    """По каким товарам уходили запросы."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT o.asin,
                   MAX(o.sales_channel) AS sales_channel,
                   MAX(s.product_name)  AS product_name,
                   COUNT(DISTINCT l.amazon_order_id)
                       FILTER (WHERE l.status='sent')      AS sent,
                   COUNT(DISTINCT l.amazon_order_id)
                       FILTER (WHERE l.status='no_action') AS no_action
            FROM kabinet_data.review_request_log l
            JOIN kabinet_data.orders_history o
              ON o.order_id = l.amazon_order_id
            LEFT JOIN (
                SELECT asin, MAX(product_name) AS product_name
                FROM kabinet_data.stock_local
                WHERE asin IS NOT NULL
                GROUP BY asin
            ) s ON s.asin = o.asin
            WHERE COALESCE(l.sent_at, l.checked_at) >= NOW() - INTERVAL '{days} days'
              AND o.asin IS NOT NULL
            GROUP BY o.asin
            HAVING COUNT(DISTINCT l.amazon_order_id) FILTER (WHERE l.status='sent') > 0
            ORDER BY sent DESC
        """, conn)
    finally:
        conn.close()


# Опорное окно для состава корзины и пороги «скачка». Состав считается по
# нему и НЕ зависит от периода, выбранного на странице: иначе метрики
# перестают быть сравнимыми между периодами
BASKET_DAYS = 90
JUMP_TOL = 0.25   # доля от медианы, выше которой суточное изменение — подмена набора
JUMP_MIN = 5      # абсолютный пол, чтобы не ловить шум на товарах с единицами отзывов


@st.cache_data(ttl=600)
def load_reviews_basket() -> pd.DataFrame:
    """Состав корзины и текущее число отзывов по каждой паре ASIN+маркетплейс.

    Считается по опорному окну и не зависит от выбранного периода. Раньше
    состав пересчитывался под каждый период, и метрики переставали быть
    сравнимыми: «Отзывов всего» за 30 дней выходило МЕНЬШЕ, чем за 14.

    Причина была в критерии стабильности. Он смотрел на размах за окно:
    размах больше 20% от максимума — ряд считался скачущим. Но за месяц
    нормальный товар прибавляет больше 20%, поэтому на длинном окне из
    корзины вылетали именно здоровые растущие позиции, и сумма падала.

    Здесь признак подмены набора — СУТОЧНЫЙ скачок, а не рост за период.
    Amazon показывает то отзывы страны, то все европейские, и число прыгает
    в разы за день; обычный товар набирает единицы отзывов в сутки."""
    if not table_exists("asin_reviews_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            SELECT asin, marketplace, snapshot_date, review_count
            FROM kabinet_data.asin_reviews_daily
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{BASKET_DAYS} days'
              AND review_count IS NOT NULL
            ORDER BY asin, marketplace, snapshot_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return pd.DataFrame()

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce")
    df = df.dropna(subset=["review_count"])
    if df.empty:
        return pd.DataFrame()

    keys = [df["asin"], df["marketplace"]]
    g = df.groupby(["asin", "marketplace"], sort=False)

    jump = df.groupby(["asin", "marketplace"], sort=False)["review_count"].diff()
    jump = jump.abs().groupby(keys).max()
    med = g["review_count"].median()
    steady = jump.fillna(0) <= np.maximum(JUMP_MIN, med * JUMP_TOL)

    # пара должна присутствовать почти во все дни, что её вообще собирают:
    # долю считаем от её собственного срока наблюдения, иначе товар,
    # добавленный неделю назад, не наберёт 80% опорного окна
    dates = np.sort(df["snapshot_date"].unique())
    span = g["snapshot_date"].agg(first="min", last="max", n="nunique")
    expected = (np.searchsorted(dates, span["last"], "right")
                - np.searchsorted(dates, span["first"], "left"))
    present = span["n"] >= np.maximum(2, (expected * 0.8).astype(int))

    out = (g.tail(1)
            .set_index(["asin", "marketplace"])[["snapshot_date", "review_count"]]
            .rename(columns={"snapshot_date": "last_date",
                             "review_count": "last_count"}))
    out = out[present.reindex(out.index).fillna(False).to_numpy()]
    out["stable"] = steady.reindex(out.index).fillna(False).to_numpy()
    return out.reset_index()


@st.cache_data(ttl=600)
def load_reviews_dynamics(days: int = 30) -> pd.DataFrame:
    """История количества отзывов по ASIN. Нестабильные ряды отсеиваем:
    Amazon иногда показывает отзывы страны, иногда все европейские, и число
    скачет — такие пары в динамику не берём."""
    if not table_exists("asin_reviews_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            SELECT asin, marketplace, snapshot_date, review_count, rating
            FROM kabinet_data.asin_reviews_daily
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
              AND review_count IS NOT NULL
            ORDER BY snapshot_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])

    # первые дни сбора скрапер трекал единицы товаров — такие даты
    # исказят картину. Обрезаем только «разгон» в начале: неполный охват
    # в середине или в конце окна — это сбой сборщика, а не повод выкинуть
    # день целиком.
    #
    # Раньше порог считался от МАКСИМУМА за окно, и это молча съедало
    # свежие дни: набор отслеживаемых ASIN сократился — новый день не
    # добирает половину исторического пика и исчезает вместе со всей
    # правой частью графика. Медиана к такому устойчива.
    ramp = load_ramp_up_end()
    if ramp is not None:
        df = df[df["snapshot_date"] >= ramp]

    if df.empty:
        return df

    # Состав корзины и признак стабильности берём готовыми из опорного окна.
    # Внутри выбранного периода их считать нельзя: и присутствие, и размах
    # зависят от длины окна, а значит метрики перестают быть сравнимыми
    # между периодами — ровно этим «Отзывов всего» и убывало при расширении
    basket = load_reviews_basket()
    if basket.empty:
        return pd.DataFrame()
    df = df.merge(basket[["asin", "marketplace", "stable"]],
                  on=["asin", "marketplace"])
    return df


@st.cache_data(ttl=600)
def load_reviews_span() -> tuple:
    """Первая и последняя дата с данными в asin_reviews_daily, как есть.

    Первая нужна, чтобы честно сказать: окно шире накопленной истории
    ничего не добавляет. Последняя — чтобы отличить «график обрезал»
    от «сборщик ещё не отработал за сегодня»."""
    if not table_exists("asin_reviews_daily"):
        return None, None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MIN(snapshot_date), MAX(snapshot_date) "
                    "FROM kabinet_data.asin_reviews_daily "
                    "WHERE review_count IS NOT NULL")
        row = cur.fetchone()
        if not row or row[0] is None:
            return None, None
        return pd.Timestamp(row[0]), pd.Timestamp(row[1])
    except Exception:
        return None, None
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_ramp_up_end() -> pd.Timestamp | None:
    """С какой даты охват сбора стал полным.

    Считается по опорному окну и НЕ зависит от выбранного периода. Раньше
    «разгон» искали внутри выбранного окна, и это съедало дни: на семи днях
    первый же день с неполным охватом оказывался началом окна, обрезался
    вместе с медианой, посчитанной по четырём точкам, и от недели
    оставалось три дня."""
    if not table_exists("asin_reviews_daily"):
        return None
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            SELECT snapshot_date, COUNT(*) AS n
            FROM kabinet_data.asin_reviews_daily
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{BASKET_DAYS} days'
              AND review_count IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """, conn)
    except Exception:
        return None
    finally:
        conn.close()
    if df.empty or len(df) <= 3:
        return None
    per_day = df.set_index(pd.to_datetime(df["snapshot_date"]))["n"]
    ok = per_day[per_day >= per_day.median() * 0.5]
    return ok.index.min() if len(ok) >= 3 else None


@st.cache_data(ttl=600)
def load_reviews_last_snapshot() -> pd.Timestamp | None:
    """Самая свежая дата в asin_reviews_daily — как есть, без фильтров.
    Нужна, чтобы поймать обратный случай: данные в таблице есть, но их
    съели фильтры стабильности. Тогда график молча обрывается, и человек
    видит «свежих данных нет» там, где на самом деле «данные не прошли
    отбор» — это разные проблемы и чинятся они по-разному."""
    if not table_exists("asin_reviews_daily"):
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(snapshot_date) "
                    "FROM kabinet_data.asin_reviews_daily "
                    "WHERE review_count IS NOT NULL")
        row = cur.fetchone()
        return pd.Timestamp(row[0]) if row and row[0] else None
    except Exception:
        return None
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_sent_by_day(days: int = 30) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT sent_at::date AS day, COUNT(*) AS sent
            FROM kabinet_data.review_request_log
            WHERE status = 'sent'
              AND sent_at >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY 1 ORDER BY 1
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def _bar(pct, color: str, dash: bool = False) -> str:
    """Полоса покрытия: заполненная часть + подпись процента."""
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return (f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<div style="flex:1;height:8px;background:var(--surface-0);'
                f'border-radius:4px;"></div>'
                f'<span style="font-size:12px;color:var(--text-muted);'
                f'min-width:34px;text-align:right;">—</span></div>')
    w = max(0, min(100, float(pct)))
    return (f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<div style="flex:1;height:8px;background:var(--surface-0);'
            f'border-radius:4px;overflow:hidden;">'
            f'<div style="width:{w:.0f}%;height:100%;background:{color};'
            f'border-radius:4px;"></div></div>'
            f'<span style="font-size:12px;color:var(--text-secondary);'
            f'min-width:34px;text-align:right;">{w:.0f}%</span></div>')


def _badge(label: str, key: str) -> str:
    """Статус цветным бейджем в стиле Кабинета."""
    bg = {"ok": "var(--bg-success)", "catching": "var(--bg-warning)",
          "missed": "var(--bg-danger)", "maturing": "var(--surface-0)"}.get(key, "")
    fg = {"ok": "var(--text-success)", "catching": "var(--text-warning)",
          "missed": "var(--text-danger)", "maturing": "var(--text-secondary)"}.get(key, "")
    return (f'<span style="background:{bg};color:{fg};font-size:12px;'
            f'padding:3px 10px;border-radius:var(--radius);'
            f'white-space:nowrap;">{label}</span>')


def _legend() -> str:
    """Легенда статусов одной строкой под таблицей."""
    items = [
        (ST_COLOR["ok"], t("rev.st.ok"), t("rev.legend.ok_short")),
        (ST_COLOR["catching"], t("rev.st.catching"), t("rev.legend.catching_short")),
        (ST_COLOR["missed"], t("rev.st.missed"), t("rev.legend.missed_short")),
        (ST_COLOR["maturing"], t("rev.st.maturing"),
         t("rev.legend.maturing_short").format(min=AGE_MIN)),
    ]
    cells = "".join(
        f'<span style="display:flex;align-items:center;gap:6px;">'
        f'<span style="width:9px;height:9px;border-radius:2px;background:{c};'
        f'flex-shrink:0;"></span>{name} — {desc}</span>'
        for c, name, desc in items)
    return (f'<div style="display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:10px;'
            f'padding-top:10px;border-top:0.5px solid var(--border);font-size:12px;'
            f'color:var(--text-secondary);">{cells}</div>')


def _coverage_table(rows: list, with_marketplace: bool,
                    sort_col: str, sort_dir: str) -> str:
    """HTML-таблица покрытия: полоса прогресса + бейдж статуса."""
    head_cols = [(t("rev.col.date"), "104px", "left", "day")]
    if with_marketplace:
        head_cols.append((t("rev.col.marketplace"), "124px", "left", None))
    head_cols += [
        (t("rev.col.orders"), "76px", "right", "orders"),
        (t("rev.col.sent"), "90px", "right", "sent"),
        (t("rev.col.no_action"), "104px", "right", "no_action"),
        (t("rev.col.coverage"), None, "left", "coverage"),
        (t("rev.col.status"), "104px", "left", None),
    ]

    HINTS = {
        "no_action": t("rev.col.no_action_help"),
        "coverage": t("rev.col.coverage_help"),
    }

    def _th(name, w, al, field):
        style = (f'font-weight:400;padding:0 0 8px;text-align:{al};'
                 + (f'width:{w};' if w else ''))
        hint = HINTS.get(field)
        if hint:
            name = (f'<span title="{hint}" style="border-bottom:1px dotted '
                    f'var(--text-muted);cursor:help;">{name}</span>')
        if not field:
            return f'<th style="{style}">{name}</th>'
        active = field == sort_col
        # повторный клик по активной колонке разворачивает порядок
        nxt = "asc" if (active and sort_dir == "desc") else "desc"
        arrow = ("" if not active
                 else ' <span style="font-size:10px;">'
                      + ("&#9660;" if sort_dir == "desc" else "&#9650;")
                      + "</span>")
        color = "var(--text-primary)" if active else "var(--text-secondary)"
        return (f'<th style="{style}"><a href="?sort={field}&dir={nxt}" '
                f'target="_self" style="color:{color};text-decoration:none;'
                f'cursor:pointer;">{name}{arrow}</a></th>')

    th = "".join(_th(*c) for c in head_cols)

    tr = []
    for r in rows:
        cells = [f'<td style="padding:9px 0;color:var(--text-secondary);">{r["day"]}</td>']
        if with_marketplace:
            cells.append(f'<td style="padding:9px 0;color:var(--text-secondary);">'
                         f'{r["marketplace"]}</td>')
        cells += [
            f'<td style="padding:9px 0;text-align:right;">{r["orders"]}</td>',
            f'<td style="padding:9px 0;text-align:right;">{r["sent"]}</td>',
            f'<td style="padding:9px 0;text-align:right;color:var(--text-secondary);">'
            f'{r["no_action"]}</td>',
            f'<td style="padding:9px 16px 9px 0;">'
            f'{_bar(r["coverage"], ST_COLOR.get(r["st"], GREY))}</td>',
            f'<td style="padding:9px 0;">{_badge(r["status"], r["st"])}</td>',
        ]
        tr.append(f'<tr style="border-top:0.5px solid var(--border);">'
                  + "".join(cells) + '</tr>')

    return (f'<div style="background:var(--surface-2);border:0.5px solid var(--border);'
            f'border-radius:12px;padding:0.75rem 1.25rem 1rem;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
            f'<thead><tr style="color:var(--text-secondary);text-align:left;">{th}</tr></thead>'
            f'<tbody>{"".join(tr)}</tbody></table>{_legend()}</div>')


# ═══════════════════════════════════════════════════════════════════
# ПРОВЕРКИ
# ═══════════════════════════════════════════════════════════════════

if not table_exists("review_request_log"):
    st.info(t("rev.no_table"))
    st.stop()

health = load_health()
if not health or int(health.get("total_rows") or 0) == 0:
    st.info(t("rev.empty"))
    st.stop()

# ---------- состояние рассылки ----------
last_sent = pd.to_datetime(health.get("last_sent")) if health.get("last_sent") else None
hours_since = None
last_sent_local = None
if last_sent is not None and pd.notna(last_sent):
    # в базе UTC — приводим к киевскому для отображения
    if last_sent.tzinfo is None:
        last_sent = last_sent.tz_localize("UTC")
    last_sent_local = last_sent.tz_convert(TZ)
    hours_since = (datetime.now(last_sent.tzinfo) - last_sent).total_seconds() / 3600

if hours_since is None:
    st.warning(t("rev.health_never"))
elif hours_since > 25:
    st.error(t("rev.health_stopped").format(h=hours_since))
else:
    st.success(t("rev.health_ok").format(
        when=last_sent_local.strftime("%d.%m %H:%M")))

# ---------- как это работает: коротко на видном месте + подробности по клику ----------
_intro_body = t("rev.intro.body").format(
    min=AGE_MIN, max=AGE_MAX,
    maturing=t("rev.st.maturing"),
    catching=t("rev.st.catching"),
    missed=t("rev.st.missed"),
)
st.markdown(f"""
<div style="border:1px solid rgba(128,128,128,0.22); border-left:3px solid {BLUE};
            border-radius:10px; padding:12px 18px; margin:10px 0 14px 0;
            background:rgba(31,119,180,0.045);">
  <div style="font-size:0.72rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
              color:{BLUE}; margin-bottom:4px;">{t("rev.intro.title")}</div>
  <div style="font-size:0.93rem; line-height:1.55;">{_intro_body}</div>
</div>
""", unsafe_allow_html=True)

with st.expander(t("rev.how.title")):
    st.markdown(t("rev.how.body"))

    st.markdown(f"""
<div style="margin-top:6px; border:1px solid rgba(128,128,128,0.22); border-radius:10px;
            padding:12px 16px; background:rgba(128,128,128,0.05);">
  <div style="font-size:0.7rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
              color:{GREY}; margin-bottom:8px;">{t("rev.formula.title")}</div>
  <code style="font-size:0.87rem; display:block; margin-bottom:4px;">
    {t('rev.col.coverage')} = {t('rev.col.sent')} / {t('rev.col.orders')} × 100
  </code>
  <code style="font-size:0.87rem; display:block;">
    {t('rev.col.pending')} = {t('rev.col.orders')} − {t('rev.col.sent')}
  </code>
</div>
""", unsafe_allow_html=True)

# ---------- период ----------
pc1, pc2 = st.columns([2, 3])
with pc1:
    period = st.segmented_control(
        t("rev.period"), options=["7", "14", "30", "60", "90"], default="30")
DAYS = int(period or 30)

# ═══════════════════════════════════════════════════════════════════
# KPI
# ═══════════════════════════════════════════════════════════════════

pool = load_pool()
pool_total = int(pool["orders"].sum()) if not pool.empty else 0
pool_burning = int(pool.loc[pool["age_days"] >= 26, "orders"].sum()) if not pool.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("rev.kpi.today"), f"{int(health.get('today') or 0):,}",
          help=t("rev.kpi.today_help"))
k2.metric(t("rev.kpi.week"), f"{int(health.get('sent7') or 0):,}",
          help=t("rev.kpi.week_help"))
k3.metric(t("rev.kpi.pool"), f"{pool_total:,}", help=t("rev.kpi.pool_help"))
k4.metric(t("rev.kpi.burning"), f"{pool_burning:,}", help=t("rev.kpi.burning_help"))
k5.metric(t("rev.kpi.skipped"), f"{int(health.get('skipped') or 0):,}",
          help=t("rev.kpi.skipped_help"))


st.divider()

tab_cov, tab_dyn, tab_mp, tab_age, tab_asin = st.tabs(
    [t("rev.tab.coverage"), t("rev.tab.dynamics"), t("rev.tab.marketplace"),
     t("rev.tab.age"), t("rev.tab.asin")]
)

cov = load_coverage(DAYS)

# ═══════════════════════════════════════════════════════════════════
# ПОКРЫТИЕ ПО ДАТАМ
# ═══════════════════════════════════════════════════════════════════

with tab_cov:
    if cov.empty:
        st.info(t("common.no_data"))
    else:
        by_day = (cov.groupby("day", as_index=False)
                     .agg(orders=("orders", "sum"), sent=("sent", "sum"),
                          no_action=("no_action", "sum"),
                          skipped=("skipped", "sum"), errors=("errors", "sum")))
        by_day["processed"] = by_day["sent"]
        by_day["coverage"] = np.round(
            safe_div(by_day["processed"], by_day["orders"]) * 100, 1)
        by_day["pending"] = (by_day["orders"] - by_day["processed"]).clip(lower=0)

        today = pd.Timestamp(datetime.now(TZ).date())
        by_day["age"] = (today - pd.to_datetime(by_day["day"])).dt.days

        def status_of(row):
            if row["age"] < AGE_MIN:
                return "maturing"
            if row["coverage"] >= 90:
                return "ok"
            return "catching" if row["age"] <= AGE_MAX else "missed"

        by_day["st"] = by_day.apply(status_of, axis=1)
        ST_LABEL = {
            "ok": t("rev.st.ok"), "catching": t("rev.st.catching"),
            "missed": t("rev.st.missed"), "maturing": t("rev.st.maturing"),
        }
        by_day["status"] = by_day["st"].map(ST_LABEL)

        # ---- сводка по дозревшим датам ----
        matured = by_day[by_day["st"] != "maturing"]
        m_orders = int(matured["orders"].sum())
        m_processed = int(matured["processed"].sum())
        m_sent = int(matured["sent"].sum())
        m_cov = round(m_processed / m_orders * 100, 1) if m_orders else 0.0
        m_missed = int(by_day.loc[by_day["st"] == "missed", "pending"].sum())

        # Сводка считается только по дозревшим дням: пока заказу меньше
        # AGE_MIN дней, запрос отправить нельзя, и «не покрыт» он не по
        # нашей вине. Но если ВСЕ дни окна ещё зреют — а так всегда бывает
        # на окне короче AGE_MIN, — то четыре нуля выглядят как «рассылка
        # стоит», хотя мерить просто нечего. Говорим об этом прямо
        all_maturing = matured.empty
        if all_maturing:
            st.info(t("rev.sum.all_maturing").format(n=AGE_MIN, d=DAYS))

        s1, s2, s3, s4 = st.columns(4)
        s1.metric(t("rev.sum.orders"),
                  "—" if all_maturing else f"{m_orders:,}",
                  help=t("rev.sum.matured_only"))
        s2.metric(t("rev.sum.processed"),
                  "—" if all_maturing else f"{m_processed:,}")
        s3.metric(t("rev.sum.coverage"),
                  "—" if all_maturing else f"{m_cov:.1f}%")
        s4.metric(t("rev.sum.missed"),
                  "—" if all_maturing else f"{m_missed:,}",
                  help=t("rev.sum.missed_help"))

        # ---- воронка: где теряются запросы ----
        f_orders = m_orders
        f_checked = int(matured["sent"].sum() + matured["no_action"].sum()
                        + matured["skipped"].sum())
        f_allowed = int(matured["sent"].sum())
        f_sent = f_allowed

        st.markdown(f"**{t('rev.funnel.title')}**")
        steps = [
            (t("rev.funnel.orders"), f_orders, BLUE),
            (t("rev.funnel.checked"), f_checked, "#3987e5"),
            (t("rev.funnel.allowed"), f_allowed, "#5DCAA5"),
            (t("rev.funnel.sent"), f_sent, GREEN),
        ]
        base = max(f_orders, 1)
        bars = ""
        labels = ""
        for i, (name, val, color) in enumerate(steps):
            h = max(4, round(val / base * 110))
            pct = val / base * 100
            gap = '<div style="width:2px;"></div>' if i else ""
            bars += (gap + f'<div style="flex:1;display:flex;flex-direction:column;'
                     f'justify-content:flex-end;align-items:center;gap:8px;">'
                     f'<span style="font-size:20px;font-weight:500;">{val:,}</span>'
                     f'<div style="width:100%;max-width:110px;height:{h}px;'
                     f'background:{color};border-radius:4px 4px 0 0;"></div></div>')
            labels += (gap + f'<div style="flex:1;text-align:center;">'
                       f'<div style="font-size:13px;color:var(--text-secondary);">{name}</div>'
                       f'<div style="font-size:12px;color:var(--text-muted);">'
                       f'{pct:.0f}%</div></div>')
        st.markdown(
            f'<div style="background:var(--surface-1);border-radius:12px;'
            f'padding:1rem 1.25rem;margin-bottom:1.25rem;">'
            f'<div style="display:flex;align-items:flex-end;height:150px;'
            f'margin-bottom:10px;">{bars}</div>'
            f'<div style="display:flex;border-top:0.5px solid var(--border);'
            f'padding-top:10px;">{labels}</div></div>',
            unsafe_allow_html=True)
        st.caption(t("rev.funnel.note"))

        # ---- график: заказы против обработанных ----
        st.markdown(f"**{t('rev.chart.orders_vs_processed')}**")
        gd = by_day.sort_values("day")
        # сегменты стопки рисуются со сдвигом base — и Plotly показывает
        # в подсказке верхнюю границу стопки вместо самого сегмента.
        # Поэтому значение передаём явно через customdata
        for c in ("orders", "sent", "no_action", "skipped"):
            gd[c] = pd.to_numeric(gd[c], errors="coerce").fillna(0)
        gd["coverage"] = pd.to_numeric(gd["coverage"], errors="coerce").fillna(0)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(
            name=t("rev.col.orders"), x=gd["day"], y=gd["orders"],
            marker_color=BLUE, offsetgroup=0,
            customdata=gd["orders"],
            hovertemplate="%{customdata:.0f}<extra></extra>"),
            secondary_y=False)
        fig.add_trace(go.Bar(
            name=t("rev.col.sent"), x=gd["day"], y=gd["sent"],
            marker_color=GREEN, offsetgroup=1,
            customdata=gd["sent"],
            hovertemplate="%{customdata:.0f}<extra></extra>"),
            secondary_y=False)
        fig.add_trace(go.Bar(
            name=t("rev.col.no_action"), x=gd["day"], y=gd["no_action"],
            marker_color=GREY, offsetgroup=1, base=gd["sent"],
            customdata=gd["no_action"],
            hovertemplate="%{customdata:.0f}<extra></extra>"),
            secondary_y=False)
        fig.add_trace(go.Bar(
            name=t("rev.col.skipped"), x=gd["day"], y=gd["skipped"],
            marker_color=AMBER, offsetgroup=1,
            base=gd["sent"] + gd["no_action"],
            customdata=gd["skipped"],
            hovertemplate="%{customdata:.0f}<extra></extra>"),
            secondary_y=False)
        fig.add_trace(go.Scatter(
            name=t("rev.col.coverage"), x=gd["day"], y=gd["coverage"],
            mode="lines+markers", line=dict(color=ACCENT, width=2),
            customdata=gd["coverage"],
            hovertemplate="%{customdata:.0f}%<extra></extra>"),
            secondary_y=True)
        fig.update_layout(barmode="group", height=360,
                          margin=dict(l=10, r=10, t=10, b=10),
                          hovermode="x unified",
                          legend=dict(orientation="h", y=1.12))
        fig.update_yaxes(title_text=t("rev.col.orders"), secondary_y=False)
        fig.update_yaxes(range=[0, 105], ticksuffix="%", showgrid=False,
                         secondary_y=True)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        st.caption(t("rev.chart.no_action_note"))

        # ---- таблица по датам: итог по дате + разбивка по маркетплейсам ----
        st.markdown(f"**{t('rev.table.by_date')}**")

        by_day_mp = (cov.groupby(["day", "sales_channel"], as_index=False)
                        .agg(orders=("orders", "sum"), sent=("sent", "sum"),
                             no_action=("no_action", "sum"),
                             skipped=("skipped", "sum")))
        by_day_mp["coverage"] = np.round(
            safe_div(by_day_mp["sent"], by_day_mp["orders"]) * 100, 1)
        by_day_mp["age"] = (today - pd.to_datetime(by_day_mp["day"])).dt.days
        by_day_mp["st"] = by_day_mp.apply(
            lambda row: status_of({"age": row["age"], "coverage": row["coverage"]}),
            axis=1)

        # сортировка живёт в адресе страницы — заголовки таблицы кликабельны
        ALLOWED_SORT = {"day", "orders", "sent", "no_action", "coverage"}
        sort_col = st.query_params.get("sort", "day")
        if sort_col not in ALLOWED_SORT:
            sort_col = "day"
        sort_dir = st.query_params.get("dir", "desc")
        if sort_dir not in ("asc", "desc"):
            sort_dir = "desc"
        asc = sort_dir == "asc"

        tc1, tc2 = st.columns([1.1, 2.4])
        with tc1:
            split_mp = st.toggle(t("rev.table.split_by_marketplace"), value=False)
        with tc2:
            mp_options = sorted(by_day_mp["sales_channel"].dropna().unique().tolist())
            mp_filter = st.multiselect(
                t("rev.table.marketplace_filter"), options=mp_options,
                default=mp_options, disabled=not split_mp,
                label_visibility="collapsed" if not split_mp else "visible")

        rows = []
        # даты без покрытия («зреет») всегда внизу — иначе они забьют верх списка
        src = by_day.copy()
        if sort_col == "day":
            src = src.sort_values("day", ascending=asc)
        else:
            src["_null"] = src[sort_col].isna()
            src = src.sort_values(["_null", sort_col], ascending=[True, asc])
        for _, r in src.iterrows():
            day_str = pd.to_datetime(r["day"]).strftime("%d.%m.%Y")
            rows.append({
                "day": day_str, "marketplace": t("rev.table.all_marketplaces"),
                "orders": int(r["orders"]), "sent": int(r["sent"]),
                "no_action": int(r["no_action"]),
                "coverage": None if r["st"] == "maturing" and r["sent"] == 0 else r["coverage"],
                "st": r["st"], "status": r["status"],
            })
            if split_mp:
                sub = by_day_mp[(by_day_mp["day"] == r["day"])
                                & (by_day_mp["sales_channel"].isin(mp_filter))]
                sub_sorted = (sub.sort_values(sort_col, ascending=asc)
                              if sort_col in sub.columns
                              else sub.sort_values("orders", ascending=False))
                for _, m in sub_sorted.iterrows():
                    rows.append({
                        "day": "", "marketplace": m["sales_channel"],
                        "orders": int(m["orders"]), "sent": int(m["sent"]),
                        "no_action": int(m["no_action"]),
                        "coverage": (None if m["st"] == "maturing" and m["sent"] == 0
                                     else m["coverage"]),
                        "st": m["st"], "status": ST_LABEL.get(m["st"], ""),
                    })

        st.markdown(_coverage_table(rows, with_marketplace=True,
                                    sort_col=sort_col, sort_dir=sort_dir),
                    unsafe_allow_html=True)
        st.caption(t("rev.table.sort_hint"))

        export = by_day_mp.copy()
        export["day"] = pd.to_datetime(export["day"]).dt.strftime("%d.%m.%Y")
        export["status"] = export["st"].map(ST_LABEL)
        st.download_button(
            t("rev.download"),
            export[["day", "sales_channel", "orders", "sent", "no_action",
                    "skipped", "coverage", "status"]]
                .to_csv(index=False).encode("utf-8-sig"),
            file_name="review_coverage.csv", mime="text/csv", key="dl_cov")

# ═══════════════════════════════════════════════════════════════════
# ДИНАМИКА ОТЗЫВОВ
# ═══════════════════════════════════════════════════════════════════

with tab_dyn:
    dyn = load_reviews_dynamics(DAYS)
    if dyn.empty:
        st.info(t("rev.dyn.no_data"))
    else:
        stable = dyn[dyn["stable"]].copy()
        n_pairs = stable.groupby(["asin", "marketplace"]).ngroups
        n_dropped = dyn.groupby(["asin", "marketplace"]).ngroups - n_pairs

        if stable.empty:
            st.info(t("rev.dyn.no_stable"))
        else:
            # пропуск скрапера в отдельный день не должен выглядеть падением:
            # переносим последнее известное значение вперёд
            grid = (stable.pivot_table(index="snapshot_date",
                                       columns=["asin", "marketplace"],
                                       values="review_count", aggfunc="last")
                          .sort_index().ffill().bfill())
            daily = pd.DataFrame({
                "snapshot_date": grid.index,
                "review_count": grid.sum(axis=1).values,
            })

            # дни, когда сборщик молчал, должны остаться дырой. Без этого
            # ось «схлопывает» пропуск — 16-е и 22-е становятся соседями,
            # а прирост за все пропущенные дни садится одной точкой и
            # читается как всплеск. Пустой день рвёт линию, это честнее
            span_idx = pd.date_range(daily["snapshot_date"].min(),
                                     daily["snapshot_date"].max(), freq="D")
            gap_days = span_idx.difference(daily["snapshot_date"])
            daily = (daily.set_index("snapshot_date").reindex(span_idx)
                          .rename_axis("snapshot_date").reset_index())
            daily["delta"] = daily["review_count"].diff()

            have = daily.dropna(subset=["review_count"])
            first_val = float(have["review_count"].iloc[0])
            last_val = float(have["review_count"].iloc[-1])
            total_growth = last_val - first_val

            # «Отзывов всего» — величина накопительная, к выбранному периоду
            # отношения не имеет. Берём последний снимок каждой позиции из
            # корзины, а не сумму по последнему дню окна: в окне часть позиций
            # может отсутствовать (сборщик молчал, товар добавлен позже), и
            # тотал проседал бы тем сильнее, чем шире окно
            _basket = load_reviews_basket()
            _live = (_basket[_basket["stable"]] if not _basket.empty
                     else _basket)
            total_now = (float(_live["last_count"].sum()) if not _live.empty
                         else float("nan"))
            as_of = _live["last_date"].max() if not _live.empty else None
            days_span = max((have["snapshot_date"].iloc[-1]
                             - have["snapshot_date"].iloc[0]).days, 1)

            # день первой отправки — граница «до» и «после»
            sent = load_sent_by_day(DAYS)
            launch = None
            if not sent.empty:
                sent["day"] = pd.to_datetime(sent["day"])
                launch = sent["day"].min()

            before_rate = after_rate = None
            if launch is not None:
                b = have[have["snapshot_date"] < launch]
                a = have[have["snapshot_date"] >= launch]
                if len(b) > 1:
                    before_rate = ((float(b["review_count"].iloc[-1])
                                    - float(b["review_count"].iloc[0]))
                                   / max((b["snapshot_date"].iloc[-1]
                                          - b["snapshot_date"].iloc[0]).days, 1))
                if len(a) > 1:
                    after_rate = ((float(a["review_count"].iloc[-1])
                                   - float(a["review_count"].iloc[0]))
                                  / max((a["snapshot_date"].iloc[-1]
                                         - a["snapshot_date"].iloc[0]).days, 1))

            d1, d2, d3, d4 = st.columns(4)
            d1.metric(t("rev.dyn.total"),
                      "—" if pd.isna(total_now) else f"{int(total_now):,}",
                      help=t("rev.dyn.total_help").format(
                          n=len(_live),
                          d=("—" if as_of is None
                             else pd.Timestamp(as_of).strftime("%d.%m.%Y")),
                          w=BASKET_DAYS))
            d2.metric(t("rev.dyn.growth"), f"+{int(total_growth):,}",
                      help=t("rev.dyn.growth_help").format(d=days_span))
            d3.metric(t("rev.dyn.before"),
                      f"{before_rate:.1f}" if before_rate is not None else "—",
                      help=t("rev.dyn.before_help"))
            d4.metric(t("rev.dyn.after"),
                      f"{after_rate:.1f}" if after_rate is not None else "—",
                      delta=(f"×{after_rate / before_rate:.1f}"
                             if before_rate and after_rate and before_rate > 0
                             else None),
                      help=t("rev.dyn.after_help"))

            # ---- график: отправки и прирост отзывов ----
            st.markdown(f"**{t('rev.dyn.chart')}**")
            merged = daily.merge(
                sent.rename(columns={"day": "snapshot_date"}),
                on="snapshot_date", how="left")
            merged["sent"] = merged["sent"].fillna(0)

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                name=t("rev.col.sent"), x=merged["snapshot_date"],
                y=merged["sent"], marker_color=BLUE, opacity=0.55),
                secondary_y=False)
            fig.add_trace(go.Scatter(
                name=t("rev.dyn.delta"), x=merged["snapshot_date"],
                y=merged["delta"], mode="lines+markers",
                line=dict(color=GREEN, width=2),
                connectgaps=False), secondary_y=True)
            if launch is not None:
                lday = merged.loc[merged["snapshot_date"] >= launch,
                                  "snapshot_date"]
                if len(lday):
                    x0 = lday.iloc[0]
                    fig.add_shape(type="line", xref="x", yref="paper",
                                  x0=x0, x1=x0, y0=0, y1=1,
                                  line=dict(color=ACCENT, width=2, dash="dash"),
                                  opacity=0.7)
                    fig.add_annotation(xref="x", yref="paper", x=x0, y=1.04,
                                       text=t("rev.dyn.launch"), showarrow=False,
                                       font=dict(color=ACCENT, size=11),
                                       xanchor="left")
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10),
                              hovermode="x unified",
                              legend=dict(orientation="h", y=1.16),
                              xaxis=dict(type="date", tickformat="%d.%m",
                                         dtick=86400000.0 * max(
                                             1, len(merged) // 15)))
            fig.update_yaxes(title_text=t("rev.col.sent"), secondary_y=False)
            fig.update_yaxes(title_text=t("rev.dyn.delta"),
                             showgrid=False, secondary_y=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
            # минус в ряду возможен: Amazon снимает отзывы. Отдельно
            # фильтровать такие пары нельзя — выбросив пару целиком ради
            # минус двух, мы исказим тотал сильнее, чем на эти два
            if (merged["delta"] < 0).any():
                st.caption(t("rev.dyn.negative_note"))

            first_seen, last_seen = load_reviews_span()
            # п.1: «графика нет за вчера» и «сборщик не отработал за вчера» —
            # разные вещи, и раньше их было не различить
            if last_seen is not None:
                _lag = (pd.Timestamp(datetime.now(TZ).date()) - last_seen).days
                if _lag >= 1:
                    st.caption(t("rev.dyn.data_through").format(
                        d=last_seen.strftime("%d.%m"), n=_lag))
            # п.4: за пределами накопленной истории окна перестают отличаться
            if first_seen is not None:
                _covered = (pd.Timestamp(datetime.now(TZ).date())
                            - first_seen).days
                if DAYS > _covered:
                    st.caption(t("rev.dyn.history_limit").format(
                        d=first_seen.strftime("%d.%m.%Y"), n=_covered))

            raw_last = load_reviews_last_snapshot()
            shown_last = daily.dropna(subset=["review_count"])["snapshot_date"].max()
            if raw_last is not None and raw_last > shown_last:
                st.warning(t("rev.dyn.filtered_note").format(
                    raw=raw_last.strftime("%d.%m"),
                    shown=shown_last.strftime("%d.%m")))
            if len(gap_days):
                st.caption(t("rev.dyn.gap_note").format(
                    n=len(gap_days),
                    days=", ".join(d.strftime("%d.%m")
                                   for d in gap_days[:8])
                          + ("…" if len(gap_days) > 8 else "")))
            st.caption(t("rev.dyn.lag_note"))

            # ---- движение в категории ----
            bsr = load_bsr_daily(DAYS)
            if not bsr.empty and len(bsr) > 1:
                st.divider()
                st.markdown(f"**{t('rev.bsr.title')}**")

                tot = load_bsr_totals(DAYS)
                if tot:
                    b1, b2, b3 = st.columns(3)
                    b1.metric(t("rev.bsr.up"), f"{int(tot.get('up', 0)):,}")
                    b2.metric(t("rev.bsr.down"), f"{int(tot.get('down', 0)):,}")
                    b3.metric(t("rev.bsr.tracked"),
                              f"{int(tot.get('tracked', 0)):,}",
                              help=t("rev.bsr.tracked_help"))

                bsr["snapshot_date"] = pd.to_datetime(bsr["snapshot_date"])
                bsr["label"] = bsr["snapshot_date"].dt.strftime("%d.%m")

                figb = go.Figure()
                figb.add_bar(name=t("rev.bsr.up"), x=bsr["label"],
                             y=bsr["moved_up"], marker_color=GREEN)
                # опустившиеся вниз от нуля — перевес виден с одного взгляда
                figb.add_bar(name=t("rev.bsr.down"), x=bsr["label"],
                             y=-bsr["moved_down"], marker_color=ACCENT,
                             customdata=bsr["moved_down"],
                             hovertemplate="%{customdata}<extra></extra>")
                figb.update_layout(
                    barmode="relative", height=260,
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                    legend=dict(orientation="h", y=1.15, title=None),
                    xaxis=dict(type="category"),
                    yaxis=dict(title=t("rev.bsr.axis")))
                st.plotly_chart(figb, use_container_width=True, config=PLOTLY_CFG)
                st.caption(t("rev.bsr.note").format(
                    n=int(tot.get("tracked", 0)) if tot else 0))
            elif not bsr.empty:
                st.divider()
                st.caption(t("rev.bsr.wait"))

            # ---- топ выросших товаров ----
            first_last = (stable.sort_values("snapshot_date")
                                .groupby(["asin", "marketplace"])
                                .agg(first=("review_count", "first"),
                                     last=("review_count", "last"),
                                     rating=("rating", "last"))
                                .reset_index())
            first_last["growth"] = first_last["last"] - first_last["first"]
            grown = first_last[first_last["growth"] > 0] \
                .sort_values("growth", ascending=False)

            g1, g2 = st.columns(2)
            g1.metric(t("rev.dyn.grown"), f"{len(grown):,}",
                      help=t("rev.dyn.grown_help").format(n=n_pairs))
            g2.metric(t("rev.dyn.excluded"), f"{n_dropped:,}",
                      help=t("rev.dyn.excluded_help"))

            if not grown.empty:
                st.markdown(f"**{t('rev.dyn.top')}**")
                st.dataframe(
                    grown.head(20)[["asin", "marketplace", "first",
                                    "last", "growth", "rating"]],
                    use_container_width=True, height=380, hide_index=True,
                    column_config={
                        "asin": st.column_config.TextColumn("ASIN", width="small"),
                        "marketplace": st.column_config.TextColumn(
                            t("rev.col.marketplace"), width="small"),
                        "first": st.column_config.NumberColumn(
                            t("rev.dyn.was"), width="small"),
                        "last": st.column_config.NumberColumn(
                            t("rev.dyn.now"), width="small"),
                        "growth": st.column_config.NumberColumn(
                            t("rev.dyn.plus"), format="+%d", width="small"),
                        "rating": st.column_config.NumberColumn(
                            t("rev.dyn.rating"), format="%.1f", width="small"),
                    },
                )
            st.caption(t("rev.dyn.note"))


# ═══════════════════════════════════════════════════════════════════
# ПО МАРКЕТПЛЕЙСАМ
# ═══════════════════════════════════════════════════════════════════

with tab_mp:
    if cov.empty:
        st.info(t("common.no_data"))
    else:
        by_mp = (cov.groupby("sales_channel", as_index=False)
                    .agg(orders=("orders", "sum"), sent=("sent", "sum"),
                         no_action=("no_action", "sum"),
                         skipped=("skipped", "sum")))
        by_mp["processed"] = by_mp["sent"]
        by_mp["coverage"] = np.round(
            safe_div(by_mp["processed"], by_mp["orders"]) * 100, 1)
        by_mp["hit_rate"] = np.round(
            safe_div(by_mp["sent"], by_mp["sent"] + by_mp["no_action"]) * 100, 1)
        # сортируем по тому же числу, которое стоит в карточке. Раньше
        # порядок задавали заказы, а показывали отправки — и карточки шли
        # вразнобой: 5 оказывалось перед 6
        by_mp = by_mp.sort_values("sent", ascending=False)

        cc = st.columns(min(len(by_mp), 5) or 1)
        for i, (_, r) in enumerate(by_mp.iterrows()):
            with cc[i % len(cc)]:
                st.metric(channel_code(r["sales_channel"]),
                          f"{int(r['sent']):,}",
                          delta=f"{r['coverage']:.0f}%",
                          help=t("rev.mp.metric_help").format(
                              mp=r["sales_channel"]))

        plot_mp = by_mp.rename(columns={
            "sent": t("rev.col.sent"),
            "no_action": t("rev.col.no_action"),
            "skipped": t("rev.col.skipped"),
        })
        fig = px.bar(plot_mp, x="sales_channel",
                     y=[t("rev.col.sent"), t("rev.col.no_action"), t("rev.col.skipped")],
                     title=t("rev.chart.by_marketplace"),
                     color_discrete_sequence=[GREEN, GREY, AMBER])
        fig.update_layout(height=360, xaxis_title=None,
                          yaxis_title=t("rev.col.orders"),
                          margin=dict(l=10, r=10, t=50, b=10),
                          legend=dict(orientation="h", y=1.12, title_text=""))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.dataframe(
            by_mp[["sales_channel", "orders", "sent", "no_action", "skipped",
                   "coverage", "hit_rate"]],
            use_container_width=True, hide_index=True,
            column_config={
                "sales_channel": st.column_config.TextColumn(t("rev.col.marketplace")),
                "orders": st.column_config.NumberColumn(t("rev.col.orders")),
                "sent": st.column_config.NumberColumn(t("rev.col.sent")),
                "no_action": st.column_config.NumberColumn(t("rev.col.no_action")),
                "skipped": st.column_config.NumberColumn(t("rev.col.skipped")),
                "coverage": st.column_config.ProgressColumn(
                    t("rev.col.coverage"), format="%.0f%%", min_value=0, max_value=100,
                    help=t("rev.col.coverage_help")),
                "hit_rate": st.column_config.NumberColumn(
                    t("rev.col.hit_rate"), format="%.0f%%",
                    help=t("rev.col.hit_rate_help")),
            },
        )

# ═══════════════════════════════════════════════════════════════════
# ВОЗРАСТ ЗАКАЗА
# ═══════════════════════════════════════════════════════════════════

with tab_age:
    age = load_age_stats()
    if age.empty:
        st.info(t("rev.age.no_data"))
    else:
        age["hit_rate"] = np.round(safe_div(age["sent"], age["checked"]) * 100, 1)
        total_checked = int(age["checked"].sum())

        st.markdown(f"**{t('rev.age.title')}**")
        st.caption(t("rev.age.caption"))

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(name=t("rev.age.checked"), x=age["age"],
                             y=age["checked"], marker_color=BLUE), secondary_y=False)
        fig.add_trace(go.Scatter(name=t("rev.col.hit_rate"), x=age["age"],
                                 y=age["hit_rate"], mode="lines+markers",
                                 line=dict(color=ACCENT, width=2)), secondary_y=True)
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                          hovermode="x unified",
                          legend=dict(orientation="h", y=1.12))
        fig.update_xaxes(title_text=t("rev.age.axis"), dtick=2)
        fig.update_yaxes(title_text=t("rev.age.checked"), secondary_y=False)
        fig.update_yaxes(range=[0, 105], ticksuffix="%", showgrid=False,
                         secondary_y=True)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        if total_checked < 200:
            st.warning(t("rev.age.small_sample").format(n=total_checked))
        else:
            st.caption(t("rev.age.enough_sample").format(n=total_checked))

        # ---- во сколько уходят запросы ----
        st.divider()
        st.markdown(f"**{t('rev.hour.title')}**")
        st.caption(t("rev.hour.caption"))
        by_hour = load_by_hour(DAYS)
        if by_hour.empty:
            st.info(t("common.no_data"))
        else:
            by_hour["label"] = by_hour["hour"].astype(int).astype(str) + ":00"
            by_hour = by_hour.sort_values("hour")

            # разбивка по странам: в одном часе может уходить несколько
            # маркетплейсов, и без разделения непонятно, чей это столбец
            figh = px.bar(by_hour, x="label", y="sent", color="marketplace",
                          text="sent",
                          category_orders={"label": by_hour["label"].unique().tolist()})
            figh.update_layout(height=280, xaxis_title=None, barmode="stack",
                               yaxis_title=t("rev.col.sent"),
                               margin=dict(l=10, r=10, t=10, b=10),
                               legend=dict(orientation="h", y=1.15, title=None))
            figh.update_traces(textposition="inside")
            st.plotly_chart(figh, use_container_width=True, config=PLOTLY_CFG)

            hh = by_hour.groupby("hour", as_index=False)["sent"].sum()
            if len(hh) == 1:
                st.caption(t("rev.hour.single").format(h=int(hh["hour"].iloc[0])))
            else:
                # где какой маркетплейс — словами, чтобы не разбирать по цветам
                pairs = (by_hour.groupby("hour")["marketplace"]
                                .apply(lambda x: ", ".join(sorted(set(x))))
                                .to_dict())
                line = " · ".join(f"{h}:00 — {mp}" for h, mp in sorted(pairs.items()))
                st.caption(t("rev.hour.split").format(s=line))

        # ---- сравнение расписаний ----
        slots = load_by_slot(DAYS)
        if not slots.empty and slots["slot"].nunique() > 1:
            st.divider()
            st.markdown(f"**{t('rev.slot.title')}**")
            st.caption(t("rev.slot.caption"))

            SLOT_LABEL = {"evening_es": t("rev.slot.evening"),
                          "morning_default": t("rev.slot.morning")}
            agg = (slots.groupby("slot", as_index=False)[["checked", "sent"]].sum())
            agg["rate"] = np.round(safe_div(agg["sent"], agg["checked"]) * 100, 1)
            agg["label"] = agg["slot"].map(lambda x: SLOT_LABEL.get(x, x))

            scols = st.columns(len(agg))
            for col, (_, r) in zip(scols, agg.iterrows()):
                col.metric(r["label"], f"{r['rate']:.0f}%",
                           delta=t("rev.slot.checked").format(n=int(r["checked"])),
                           delta_color="off",
                           help=t("rev.slot.metric_help"))

            slots["day"] = pd.to_datetime(slots["day"])
            slots["rate"] = np.round(
                safe_div(slots["sent"], slots["checked"]) * 100, 1)
            slots["label"] = slots["slot"].map(lambda x: SLOT_LABEL.get(x, x))
            figs = px.line(slots.sort_values("day"), x="day", y="rate",
                           color="label", markers=True,
                           color_discrete_sequence=[ACCENT, BLUE])
            figs.update_layout(height=260, xaxis_title=None,
                               yaxis_title=t("rev.slot.axis"),
                               margin=dict(l=10, r=10, t=10, b=10),
                               legend=dict(orientation="h", y=1.15, title=None))
            st.plotly_chart(figs, use_container_width=True, config=PLOTLY_CFG)

            total = int(agg["checked"].sum())
            mn = int(agg["checked"].min())
            # смотрим на меньшую группу: 45 против 1086 — это не сравнение
            if mn < 300:
                st.warning(t("rev.slot.small").format(n=total, mn=mn))
            else:
                st.caption(t("rev.slot.enough").format(n=total))
        elif not slots.empty:
            st.divider()
            st.caption(t("rev.slot.wait"))

        st.dataframe(
            age[["age", "checked", "sent", "hit_rate"]],
            use_container_width=True, height=320, hide_index=True,
            column_config={
                "age": st.column_config.NumberColumn(t("rev.age.axis"), width="small"),
                "checked": st.column_config.NumberColumn(t("rev.age.checked"), width="small"),
                "sent": st.column_config.NumberColumn(t("rev.col.sent"), width="small"),
                "hit_rate": st.column_config.ProgressColumn(
                    t("rev.col.hit_rate"), format="%.0f%%", min_value=0, max_value=100),
            },
        )

# ═══════════════════════════════════════════════════════════════════
# ПО ТОВАРАМ
# ═══════════════════════════════════════════════════════════════════

with tab_asin:
    by_asin = load_by_asin(DAYS)
    if by_asin.empty:
        st.info(t("rev.asin.no_data"))
    else:
        by_asin["product_name"] = (by_asin["product_name"]
                                   .fillna("").astype(str)
                                   .replace({"None": "", "nan": ""}))
        by_asin.loc[by_asin["product_name"].str.strip() == "", "product_name"] = "—"
        by_asin["url"] = [
            (f"https://www.{CHANNEL_DOMAIN[ch]}/dp/{a}"
             if ch in CHANNEL_DOMAIN and a else None)
            for ch, a in zip(by_asin["sales_channel"], by_asin["asin"])
        ]

        a1, a2 = st.columns([1, 1])
        with a1:
            top = by_asin.nlargest(15, "sent").sort_values("sent").copy()
            # на оси — название товара: сырой ASIN ни о чём не говорит.
            # Значением категории ASIN остаётся, подписи подменяем через
            # ticktext — иначе два товара с одинаковым названием склеились
            # бы в одну полосу. Нет названия — показываем ASIN, это лучше
            # пустой подписи
            top["label"] = [
                str(a) if pd.isna(n) or str(n).strip() in ("", "—", "None")
                else (str(n)[:38] + "…" if len(str(n)) > 38 else str(n))
                for n, a in zip(top["product_name"], top["asin"])
            ]
            fig = px.bar(top, x="sent", y="asin", orientation="h",
                         title=t("rev.asin.top"), text="sent",
                         hover_data={"asin": True, "product_name": True},
                         color_discrete_sequence=[GREEN])
            fig.update_yaxes(tickmode="array", tickvals=top["asin"],
                             ticktext=top["label"])
            fig.update_layout(height=max(320, 26 * len(top)),
                              yaxis_title=None, xaxis_title=None,
                              margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        with a2:
            st.markdown(f"**{t('rev.asin.table')}**")
            st.dataframe(
                by_asin[["asin", "product_name", "sales_channel",
                         "sent", "no_action", "url"]],
                use_container_width=True, height=460, hide_index=True,
                column_config={
                    "asin": st.column_config.TextColumn("ASIN", width="small"),
                    "product_name": st.column_config.TextColumn(
                        t("rev.col.product"), width="medium"),
                    "sales_channel": st.column_config.TextColumn(
                        t("rev.col.marketplace"), width="small"),
                    "sent": st.column_config.NumberColumn(t("rev.col.sent"), width="small"),
                    "no_action": st.column_config.NumberColumn(
                        t("rev.col.no_action"), width="small"),
                    "url": st.column_config.LinkColumn("", display_text="↗", width="small"),
                },
            )
