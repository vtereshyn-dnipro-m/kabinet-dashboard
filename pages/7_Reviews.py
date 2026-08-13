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

# окно отправки: заказы 8–33 дней от даты покупки
AGE_MIN, AGE_MAX = 8, 33

# время в базе хранится в UTC — на странице показываем киевское
TZ = ZoneInfo("Europe/Kyiv")

# домены Amazon по каналу продаж — ссылка на листинг строится по стране
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
                               AND (sent_at AT TIME ZONE 'Europe/Kyiv')::date
                                   = (NOW() AT TIME ZONE 'Europe/Kyiv')::date) AS today,
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


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def _bar(pct, color: str, dash: bool = False) -> str:
    """Полоса покрытия: заполненная часть + подпись процента."""
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return (f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<div style="flex:1;height:6px;background:var(--surface-0);'
                f'border-radius:3px;"></div>'
                f'<span style="font-size:12px;color:var(--text-muted);'
                f'min-width:34px;">—</span></div>')
    w = max(0, min(100, float(pct)))
    return (f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="flex:1;height:6px;background:var(--surface-0);'
            f'border-radius:3px;overflow:hidden;">'
            f'<div style="width:{w:.0f}%;height:100%;background:{color};"></div></div>'
            f'<span style="font-size:12px;color:var(--text-secondary);'
            f'min-width:34px;">{w:.0f}%</span></div>')


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


def _coverage_table(rows: list, with_marketplace: bool) -> str:
    """HTML-таблица покрытия: полоса прогресса + бейдж статуса."""
    head_cols = [(t("rev.col.date"), "76px", "left")]
    if with_marketplace:
        head_cols.append((t("rev.col.marketplace"), "104px", "left"))
    head_cols += [
        (t("rev.col.orders"), "62px", "right"),
        (t("rev.col.sent"), "68px", "right"),
        (t("rev.col.no_action"), "78px", "right"),
        (t("rev.col.coverage"), None, "left"),
        (t("rev.col.status"), "96px", "left"),
    ]
    th = "".join(
        f'<th style="font-weight:400;padding:0 0 8px;text-align:{al};'
        + (f'width:{w};' if w else '') + f'">{name}</th>'
        for name, w, al in head_cols)

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
            f'<td style="padding:9px 12px 9px 0;">'
            f'{_bar(r["coverage"], ST_COLOR.get(r["st"], GREY))}</td>',
            f'<td style="padding:9px 0;">{_badge(r["status"], r["st"])}</td>',
        ]
        tr.append(f'<tr style="border-top:0.5px solid var(--border);">'
                  + "".join(cells) + '</tr>')

    return (f'<div style="background:var(--surface-2);border:0.5px solid var(--border);'
            f'border-radius:12px;padding:0.75rem 1.25rem 1rem;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;'
            f'table-layout:fixed;">'
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

    def _legend_item(color: str, label: str, desc: str) -> str:
        return f"""<div style="display:flex; gap:10px; align-items:flex-start;">
  <span style="width:10px; height:10px; border-radius:3px; background:{color};
               margin-top:5px; flex-shrink:0;"></span>
  <div>
    <div style="font-weight:600; font-size:0.88rem;">{label}</div>
    <div style="font-size:0.8rem; color:{GREY}; line-height:1.4;">{desc}</div>
  </div>
</div>"""

    legend_html = f"""
<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));
            gap:14px 22px; margin:14px 0 4px 0;">
  {_legend_item(GREEN, t('rev.st.ok'), t('rev.st.ok_desc'))}
  {_legend_item(AMBER, t('rev.st.catching'), t('rev.st.catching_desc'))}
  {_legend_item(ACCENT, t('rev.st.missed'),
                t('rev.st.missed_desc').format(min=AGE_MIN, max=AGE_MAX))}
  {_legend_item(GREY, t('rev.st.maturing'),
                t('rev.st.maturing_desc').format(min=AGE_MIN))}
</div>
"""
    st.markdown(legend_html, unsafe_allow_html=True)

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
k1.metric(t("rev.kpi.today"), f"{int(health.get('today') or 0):,}")
k2.metric(t("rev.kpi.week"), f"{int(health.get('sent7') or 0):,}",
          help=t("rev.kpi.week_help"))
k3.metric(t("rev.kpi.pool"), f"{pool_total:,}", help=t("rev.kpi.pool_help"))
k4.metric(t("rev.kpi.burning"), f"{pool_burning:,}", help=t("rev.kpi.burning_help"))
k5.metric(t("rev.kpi.skipped"), f"{int(health.get('skipped') or 0):,}",
          help=t("rev.kpi.skipped_help"))

st.divider()

tab_cov, tab_mp, tab_age, tab_asin = st.tabs(
    [t("rev.tab.coverage"), t("rev.tab.marketplace"),
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

        s1, s2, s3, s4 = st.columns(4)
        s1.metric(t("rev.sum.orders"), f"{m_orders:,}", help=t("rev.sum.matured_only"))
        s2.metric(t("rev.sum.processed"), f"{m_processed:,}")
        s3.metric(t("rev.sum.coverage"), f"{m_cov:.1f}%")
        s4.metric(t("rev.sum.missed"), f"{m_missed:,}", help=t("rev.sum.missed_help"))

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
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(name=t("rev.col.orders"), x=gd["day"], y=gd["orders"],
                             marker_color=BLUE, offsetgroup=0), secondary_y=False)
        fig.add_trace(go.Bar(name=t("rev.col.sent"), x=gd["day"], y=gd["sent"],
                             marker_color=GREEN, offsetgroup=1), secondary_y=False)
        fig.add_trace(go.Bar(name=t("rev.col.no_action"), x=gd["day"], y=gd["no_action"],
                             marker_color=GREY, offsetgroup=1, base=gd["sent"]),
                      secondary_y=False)
        fig.add_trace(go.Bar(name=t("rev.col.skipped"), x=gd["day"], y=gd["skipped"],
                             marker_color=AMBER, offsetgroup=1,
                             base=gd["sent"] + gd["no_action"]), secondary_y=False)
        fig.add_trace(go.Scatter(name=t("rev.col.coverage"), x=gd["day"],
                                 y=gd["coverage"], mode="lines+markers",
                                 line=dict(color=ACCENT, width=2)), secondary_y=True)
        fig.update_layout(barmode="group", height=360,
                          margin=dict(l=10, r=10, t=10, b=10),
                          hovermode="x unified",
                          legend=dict(orientation="h", y=1.12))
        fig.update_yaxes(title_text=t("rev.col.orders"), secondary_y=False)
        fig.update_yaxes(range=[0, 105], ticksuffix="%", showgrid=False,
                         secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
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

        tc1, tc2 = st.columns([1, 2])
        with tc1:
            split_mp = st.toggle(t("rev.table.split_by_marketplace"), value=False)
        with tc2:
            mp_options = sorted(by_day_mp["sales_channel"].dropna().unique().tolist())
            mp_filter = st.multiselect(
                t("rev.table.marketplace_filter"), options=mp_options,
                default=mp_options, disabled=not split_mp,
                label_visibility="collapsed" if not split_mp else "visible")

        rows = []
        src = by_day.sort_values("day", ascending=False)
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
                for _, m in sub.sort_values("orders", ascending=False).iterrows():
                    rows.append({
                        "day": "", "marketplace": m["sales_channel"],
                        "orders": int(m["orders"]), "sent": int(m["sent"]),
                        "no_action": int(m["no_action"]),
                        "coverage": (None if m["st"] == "maturing" and m["sent"] == 0
                                     else m["coverage"]),
                        "st": m["st"], "status": ST_LABEL.get(m["st"], ""),
                    })

        st.markdown(_coverage_table(rows, with_marketplace=True),
                    unsafe_allow_html=True)

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
        by_mp = by_mp.sort_values("orders", ascending=False)

        cc = st.columns(min(len(by_mp), 5) or 1)
        for i, (_, r) in enumerate(by_mp.iterrows()):
            with cc[i % len(cc)]:
                st.metric(r["sales_channel"], f"{int(r['sent']):,}",
                          delta=f"{r['coverage']:.0f}%",
                          help=t("rev.mp.metric_help"))

        fig = px.bar(by_mp, x="sales_channel", y=["sent", "no_action", "skipped"],
                     title=t("rev.chart.by_marketplace"),
                     color_discrete_sequence=[GREEN, GREY, AMBER])
        fig.update_layout(height=360, xaxis_title=None,
                          yaxis_title=t("rev.col.orders"),
                          margin=dict(l=10, r=10, t=50, b=10),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)

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
                    t("rev.col.coverage"), format="%.0f%%", min_value=0, max_value=100),
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
        st.plotly_chart(fig, use_container_width=True)

        if total_checked < 200:
            st.warning(t("rev.age.small_sample").format(n=total_checked))
        else:
            st.caption(t("rev.age.enough_sample").format(n=total_checked))

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
        by_asin["url"] = [
            (f"https://www.{CHANNEL_DOMAIN[ch]}/dp/{a}"
             if ch in CHANNEL_DOMAIN and a else None)
            for ch, a in zip(by_asin["sales_channel"], by_asin["asin"])
        ]

        a1, a2 = st.columns([1, 1])
        with a1:
            top = by_asin.nlargest(15, "sent").sort_values("sent")
            fig = px.bar(top, x="sent", y="asin", orientation="h",
                         title=t("rev.asin.top"), text="sent",
                         color_discrete_sequence=[GREEN])
            fig.update_layout(height=max(320, 26 * len(top)),
                              yaxis_title=None, xaxis_title=None,
                              margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
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
