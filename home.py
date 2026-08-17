# home.py — Обзор: сводка для руководителя
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-size: 1.6rem; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; }
h1 { margin-bottom: 0.1rem; font-size: 2rem; }
[data-testid="stCaptionContainer"] { margin-top: -0.3rem; }
hr { margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# логотип выводится в сайдбаре через st.logo — второй раз не нужен
st.title(t("home.title"))
st.caption(t("home.subtitle"))

ACCENT = "#e8484d"
BLUE = "#1f77b4"
AMBER = "#f2b134"
GREEN = "#2e9e5b"
GREY = "#9aa4b2"
PLOTLY_CFG = {"displayModeBar": False}


# ═══════════════════════════════════════════════════════════════════
# ДАННЫЕ — каждый блок независим: нет источника, нет блока
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def load_money(days: int = 30) -> pd.DataFrame:
    if not table_exists("economics_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT sales_date, marketplace,
                   SUM(units_ordered)                     AS units,
                   SUM(ordered_product_sales)             AS revenue,
                   SUM(net_proceeds_total)                AS net,
                   SUM(COALESCE(cogs, 0) * units_ordered) AS cogs
            FROM kabinet_data.economics_summary
            WHERE sales_date >= CURRENT_DATE - INTERVAL '{days * 2} days'
            GROUP BY 1, 2
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_coverage() -> pd.DataFrame:
    if not table_exists("coverage_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT sku, marketplace, coverage_status,
                   realistic_coverage_weeks, first_deficit_week, calc_date
            FROM kabinet_data.coverage_summary
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_summary)
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT incident_type, severity, status, source, created_at,
                   DATE_PART('day', NOW() - created_at)::int AS days_open
            FROM kabinet_data.incidents
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_transfers() -> pd.DataFrame:
    if not table_exists("transfer_recommendations"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT sku, from_location, to_location, transfer_qty, status
            FROM kabinet_data.transfer_recommendations
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.transfer_recommendations)
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_reviews(days: int = 30) -> dict:
    """Отправленные запросы и прирост отзывов за период."""
    out = {}
    conn = get_connection()
    try:
        if table_exists("review_request_log"):
            df = pd.read_sql(f"""
                SELECT COUNT(*) FILTER (WHERE status='sent'
                        AND sent_at >= NOW() - INTERVAL '{days} days') AS sent7,
                       MAX(sent_at) FILTER (WHERE status='sent')       AS last_sent
                FROM kabinet_data.review_request_log
            """, conn)
            if not df.empty:
                out["sent7"] = int(df["sent7"].iloc[0] or 0)
                out["last_sent"] = df["last_sent"].iloc[0]
        if table_exists("asin_reviews_daily"):
            # сравниваем только те пары товар×площадка, что есть на обе даты:
            # охват скрапера растёт день ото дня, и общая сумма выросла бы
            # даже без единого нового отзыва
            df = pd.read_sql(f"""
                WITH per_day AS (
                    SELECT snapshot_date, COUNT(*) AS n
                    FROM kabinet_data.asin_reviews_daily
                    WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
                      AND review_count IS NOT NULL
                    GROUP BY 1
                ),
                bounds AS (
                    -- первые дни сбора скрапер охватывал единицы товаров:
                    -- берём начало периода там, где охват стал полным
                    SELECT MIN(snapshot_date) AS d0, MAX(snapshot_date) AS d1
                    FROM per_day
                    WHERE n >= (SELECT MAX(n) * 0.5 FROM per_day)
                ),
                pairs AS (
                    SELECT a.asin, a.marketplace,
                           MAX(CASE WHEN a.snapshot_date = b.d0
                                    THEN a.review_count END) AS first_cnt,
                           MAX(CASE WHEN a.snapshot_date = b.d1
                                    THEN a.review_count END) AS last_cnt
                    FROM kabinet_data.asin_reviews_daily a
                    CROSS JOIN bounds b
                    WHERE a.review_count IS NOT NULL
                      AND a.snapshot_date IN (b.d0, b.d1)
                    GROUP BY a.asin, a.marketplace
                )
                SELECT SUM(last_cnt - first_cnt) AS growth,
                       SUM(last_cnt)             AS total,
                       COUNT(*)                  AS pairs
                FROM pairs
                WHERE first_cnt IS NOT NULL AND last_cnt IS NOT NULL
                  AND last_cnt >= first_cnt
            """, conn)
            if not df.empty and pd.notna(df["growth"].iloc[0]):
                out["reviews_growth"] = int(df["growth"].iloc[0])
                out["reviews_total"] = int(df["total"].iloc[0] or 0)
                out["reviews_pairs"] = int(df["pairs"].iloc[0] or 0)
    except Exception:
        pass
    finally:
        conn.close()
    return out


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def fmt_money(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €"


# ═══════════════════════════════════════════════════════════════════
# ЗАГРУЗКА
# ═══════════════════════════════════════════════════════════════════

# период держим в адресе — иначе он сбрасывается при переходе на другую
# страницу и обратно
_qp = st.query_params.get("d", "30")
_default = _qp if _qp in ("7", "30", "90") else "30"

pc1, _ = st.columns([1, 3])
with pc1:
    period = st.segmented_control(
        t("home.period"), options=["7", "30", "90"], default=_default,
        key="home_period")
DAYS = int(period or 30)
if str(DAYS) != _qp:
    st.query_params["d"] = str(DAYS)

try:
    money = load_money(DAYS)
    cov = load_coverage()
    inc = load_incidents()
    transfers = load_transfers()
    reviews = load_reviews(DAYS)
except Exception as e:
    st.error(f"{t('home.db_error')}: {e}")
    st.stop()

today = pd.Timestamp(datetime.now().date())


# ═══════════════════════════════════════════════════════════════════
# ПРОДАЖИ
# ═══════════════════════════════════════════════════════════════════

st.markdown(f"##### {t('home.sec.sales').format(d=DAYS)}")

if money.empty:
    st.caption(t("home.sales.no_data"))
else:
    money["sales_date"] = pd.to_datetime(money["sales_date"])
    cur = money[money["sales_date"] >= today - pd.Timedelta(days=DAYS)]
    prev = money[(money["sales_date"] < today - pd.Timedelta(days=DAYS))
                 & (money["sales_date"] >= today - pd.Timedelta(days=DAYS * 2))]

    rev_cur = float(cur["revenue"].sum())
    rev_prev = float(prev["revenue"].sum())
    cm_cur = float(cur["net"].sum() - cur["cogs"].sum())
    cm_pct = round(cm_cur / rev_cur * 100, 1) if rev_cur else 0.0
    units_cur = int(cur["units"].sum())
    delta_pct = (round((rev_cur - rev_prev) / rev_prev * 100, 1)
                 if rev_prev > 0 else None)
    # период неполный или предыдущий пустой — сравнение обманет
    if delta_pct is not None and abs(delta_pct) > 300:
        delta_pct = None

    s1, s2, s3, s4 = st.columns(4)
    s1.metric(t("home.kpi.revenue"), fmt_money(rev_cur),
              delta=(f"{delta_pct:+.1f}%" if delta_pct is not None else None),
              help=t("home.kpi.revenue_help").format(d=DAYS))
    s2.metric(t("home.kpi.margin"), f"{cm_cur:,.0f} € · {cm_pct:.0f}%",
              help=t("home.kpi.margin_help"))
    s3.metric(t("home.kpi.units"), f"{units_cur:,}")
    s4.metric(t("home.kpi.markets"), f"{cur['marketplace'].nunique()}")

    gl, gr = st.columns([1.6, 1])

    with gl:
        daily = (cur.groupby("sales_date", as_index=False)["revenue"].sum()
                    .sort_values("sales_date"))
        fig = px.area(daily, x="sales_date", y="revenue",
                      color_discrete_sequence=[BLUE])
        fig.update_layout(height=190, margin=dict(l=0, r=0, t=6, b=0),
                          xaxis_title=None, yaxis_title=None,
                          yaxis=dict(showgrid=False))
        fig.update_traces(line=dict(width=1.5),
                          fillcolor="rgba(31,119,180,0.15)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

    with gr:
        # Leroy Merlin — отдельная площадка, а не ещё одна страна Amazon:
        # свои комиссии, своя логистика, свой контракт
        by_mp = (cur.groupby("marketplace", as_index=False)["revenue"].sum()
                    .sort_values("revenue", ascending=False))
        by_mp["platform"] = np.where(by_mp["marketplace"] == "LM",
                                     t("home.platform.lm"),
                                     t("home.platform.amazon"))
        # сколько стран стоит за каждой площадкой — чтобы «Leroy Merlin»
        # не выглядел как ещё одна страна рядом с Amazon
        countries = (by_mp.groupby("platform")["marketplace"]
                          .nunique().to_dict())
        by_pl = by_mp.groupby("platform", as_index=False)["revenue"].sum()

        for _, r in by_pl.iterrows():
            share = r["revenue"] / rev_cur * 100 if rev_cur else 0
            color = GREEN if r["platform"] == t("home.platform.lm") else BLUE
            n_c = countries.get(r["platform"], 0)
            sub = (t("home.sales.n_countries").format(n=n_c)
                   if r["platform"] == t("home.platform.amazon")
                   else t("home.sales.lm_where"))
            st.markdown(
                f"<div style='margin-bottom:8px'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:0.85rem'><span>{r['platform']} "
                f"<span style='color:var(--text-muted);font-size:0.78rem'>"
                f"{sub}</span></span>"
                f"<b>{r['revenue']:,.0f} €</b></div>"
                f"<div style='height:6px;border-radius:3px;"
                f"background:rgba(128,128,128,0.18)'>"
                f"<div style='height:6px;border-radius:3px;width:{share:.0f}%;"
                f"background:{color}'></div></div></div>",
                unsafe_allow_html=True)

        # у Amazon страна в коде маркетплейса, у Leroy Merlin — нет:
        # подписываем обе площадки одинаково, иначе LM читается как страна
        amz = by_mp[by_mp["marketplace"] != "LM"]
        top_c = amz.head(4)
        rest = amz.iloc[4:]
        parts = [f"{r['marketplace']} {r['revenue']:,.0f} €"
                 for _, r in top_c.iterrows()]
        if len(rest):
            parts.append(t("home.sales.others").format(
                n=len(rest), v=rest["revenue"].sum()))
        st.caption(t("home.sales.by_country") + " " + " · ".join(parts))

        lm_row = by_mp[by_mp["marketplace"] == "LM"]
        if len(lm_row):
            st.caption(t("home.sales.lm_country").format(
                v=float(lm_row["revenue"].iloc[0])))

    st.caption(t("home.sales.no_plan"))
    st.page_link("pages/5_Money.py", label=t("home.link.money"),
                 icon=":material/euro:")

st.divider()


# ═══════════════════════════════════════════════════════════════════
# ЗАПАСЫ И ПОКРЫТИЕ
# ═══════════════════════════════════════════════════════════════════

st.markdown(f"##### {t('home.sec.stock')}")
st.caption(t("home.sec.stock_note"))

cl, cr = st.columns([1.4, 1])

with cl:
    if cov.empty:
        st.caption(t("home.cov.no_data"))
    else:
        cov["realistic_coverage_weeks"] = pd.to_numeric(
            cov["realistic_coverage_weeks"], errors="coerce")
        n_crit = int((cov["coverage_status"] == "critical").sum())
        n_warn = int((cov["coverage_status"] == "warning").sum())
        n_ok = int((cov["coverage_status"] == "ok").sum())
        total_pairs = len(cov)
        secured = round(n_ok / total_pairs * 100) if total_pairs else 0

        v1, v2, v3 = st.columns(3)
        v1.metric(t("home.kpi.secured"), f"{secured}%",
                  help=t("home.kpi.secured_help"))
        v2.metric(t("home.kpi.deficit_soon"), f"{n_crit:,}",
                  help=t("home.kpi.deficit_soon_help"))
        v3.metric(t("home.kpi.deficit_later"), f"{n_warn:,}",
                  help=t("home.kpi.deficit_later_help"))

        bars = pd.DataFrame({
            "bucket": [t("home.cov.b_crit"), t("home.cov.b_warn"),
                       t("home.cov.b_ok")],
            "n": [n_crit, n_warn, n_ok],
        })
        fig = px.bar(bars, x="n", y="bucket", orientation="h", text="n",
                     color="bucket",
                     color_discrete_map={t("home.cov.b_crit"): ACCENT,
                                         t("home.cov.b_warn"): AMBER,
                                         t("home.cov.b_ok"): GREEN})
        fig.update_layout(height=150, showlegend=False,
                          xaxis_title=None, yaxis_title=None,
                          margin=dict(l=0, r=10, t=6, b=0))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.page_link("pages/1_Stock.py", label=t("home.link.coverage"),
                     icon=":material/inventory_2:")

with cr:
    st.markdown(f"**{t('home.sec.reorder')}**")
    if transfers.empty:
        st.caption(t("home.reorder.no_data"))
    else:
        pending = transfers[transfers["status"].isin(["new", "pending"])] \
            if "status" in transfers.columns else transfers
        r1, r2 = st.columns(2)
        r1.metric(t("home.kpi.transfers"), f"{len(pending):,}",
                  help=t("home.kpi.transfers_help"))
        r2.metric(t("home.kpi.transfer_qty"),
                  f"{int(pending['transfer_qty'].sum()):,}")
        st.page_link("pages/4_Reorder.py", label=t("home.link.reorder"),
                     icon=":material/shopping_cart:")

st.divider()


# ═══════════════════════════════════════════════════════════════════
# ИНЦИДЕНТЫ И ОТЗЫВЫ
# ═══════════════════════════════════════════════════════════════════

il, ir = st.columns([1.4, 1])

with il:
    st.markdown(f"##### {t('home.sec.incidents')}")
    if inc.empty:
        st.caption(t("home.inc.no_data"))
    else:
        open_inc = inc[inc["status"].isin(["open", "acknowledged"])]
        n_crit_inc = int((open_inc["severity"].isin(["critical", "high"])).sum())
        oldest = int(open_inc["days_open"].max()) if len(open_inc) else 0

        # снабжение и продажи — два разных потока, смотрят разные люди
        SALES_SRC = open_inc["source"].fillna("").str.contains(
            "leroy|lm|amazon_sales", case=False, na=False)
        n_supply = int((~SALES_SRC).sum())
        n_sales = int(SALES_SRC.sum())

        n1, n2, n3 = st.columns(3)
        n1.metric(t("home.kpi.inc_supply"), f"{n_supply:,}",
                  help=t("home.kpi.inc_supply_help"))
        n2.metric(t("home.kpi.inc_sales"), f"{n_sales:,}",
                  help=t("home.kpi.inc_sales_help"))
        n3.metric(t("home.kpi.inc_oldest"), f"{oldest}",
                  help=t("home.kpi.inc_oldest_help"))

        if len(open_inc):
            TYPE_LABEL = {
                "low_stock": t("home.inc.low_stock"),
                "out_of_stock": t("home.inc.out_of_stock"),
                "stale_data": t("home.inc.stale_data"),
                "negative_stock": t("home.inc.negative_stock"),
                "lm_order_not_accepted": t("home.inc.lm_not_accepted"),
                "lm_offer_out_of_stock": t("home.inc.lm_offer_zero"),
                "lm_health_degraded": t("home.inc.lm_degraded"),
            }
            open_inc = open_inc.copy()
            open_inc["type_label"] = open_inc["incident_type"].map(
                lambda v: TYPE_LABEL.get(v, v))
            by_type = (open_inc.groupby("type_label", as_index=False)
                               .size().rename(columns={"size": "n"})
                               .sort_values("n", ascending=True).tail(5))
            fig = px.bar(by_type, x="n", y="type_label", orientation="h",
                         text="n", color_discrete_sequence=[ACCENT])
            fig.update_layout(height=150, xaxis_title=None, yaxis_title=None,
                              margin=dict(l=0, r=10, t=6, b=0))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        else:
            st.success(t("home.inc.all_clear"))

        st.page_link("pages/2_Incidents.py", label=t("home.link.incidents"),
                     icon=":material/warning:")

with ir:
    st.markdown(f"##### {t('home.sec.reviews')}")
    if not reviews:
        st.caption(t("home.rev.no_data"))
    else:
        q1, q2 = st.columns(2)
        q1.metric(t("home.kpi.requests").format(d=DAYS),
                  f"{reviews.get('sent7', 0):,}",
                  help=t("home.kpi.requests_help").format(d=DAYS))
        growth = reviews.get("reviews_growth")
        q2.metric(t("home.kpi.new_reviews"),
                  f"+{growth:,}" if growth is not None else "—",
                  help=t("home.kpi.new_reviews_help").format(
                      d=DAYS, n=reviews.get("reviews_pairs", 0)))
        if reviews.get("last_sent") is not None:
            ls = pd.to_datetime(reviews["last_sent"])
            hours = (datetime.now(ls.tzinfo) - ls).total_seconds() / 3600
            if hours > 25:
                st.warning(t("home.rev.stopped").format(h=hours))
        st.page_link("pages/7_Reviews.py", label=t("home.link.reviews"),
                     icon=":material/rate_review:")

st.divider()

with st.expander(t("home.how_title")):
    st.markdown(t("home.how_body"))
with st.expander(t("home.roadmap_title")):
    st.markdown(t("home.roadmap_table"))
