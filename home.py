# home.py — Обзор: executive-сводка
import pandas as pd
import streamlit as st
import plotly.express as px
from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)

try:
    _dark = st.context.theme.type == "dark"
except Exception:
    _dark = True  # по умолчанию тёмная — основная тема команды

st.image("logo_dark.png" if _dark else "logo_light.png", width=140)
st.title(t("home.title"))
st.caption(t("home.subtitle"))

ACCENT = "#e8484d"
BLUE = "#1f77b4"
AMBER = "#f2b134"


# ---------- данные ----------
@st.cache_data(ttl=300)
def load_overview():
    conn = get_connection()
    stock = pd.read_sql("""
        SELECT sku, product_name, SUM(quantity) AS qty
        FROM kabinet_data.stock_local
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
        GROUP BY sku, product_name
    """, conn)
    snap = pd.read_sql(
        "SELECT MAX(snapshot_date) AS d FROM kabinet_data.stock_local", conn
    )["d"].iloc[0]
    inc = pd.read_sql("""
        SELECT severity, status, incident_type
        FROM kabinet_data.incidents
    """, conn)
    conn.close()
    return stock, snap, inc


db_ok = True
try:
    stock, snap, inc = load_overview()
except Exception as e:
    db_ok = False
    st.error(f"❌ {t('home.db_error')}: {e}")

if db_ok:
    open_inc = inc[inc["status"].isin(["open", "acknowledged"])]
    critical = int((open_inc["severity"] == "critical").sum())
    low_stock_cnt = int((stock["qty"] <= 3).sum())
    health = max(0, 100 - round(100 * low_stock_cnt / max(len(stock), 1)))

    # ---------- KPI ----------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("home.metric.health"), f"{health}%",
              help=t("home.metric.health_help").format(snap=snap))
    c2.metric(t("home.metric.sku_controlled"), len(stock))
    c3.metric(t("home.metric.total_stock"), int(stock["qty"].sum()))
    c4.metric(t("home.metric.open_incidents"), len(open_inc),
              delta=f"{critical} {t('home.critical_suffix')}" if critical else None,
              delta_color="inverse" if critical else "off")
    c5.metric(t("home.metric.resolved_auto"),
              int((inc["status"] == "resolved").sum()),
              help=t("home.metric.resolved_auto_help"))

    st.divider()

    # ---------- визуальная сводка ----------
    left, mid, right = st.columns([1.2, 1, 1.2])

    with left:
        st.markdown(f"##### {t('home.attention_title')}")
        burn = stock.nsmallest(5, "qty")
        unit = t("home.unit_pcs")
        for _, row in burn.iterrows():
            pct = min(row["qty"] / 10 * 100, 100)
            st.markdown(
                f"<div style='margin-bottom:10px'>"
                f"<div style='display:flex;justify-content:space-between;font-size:0.85rem'>"
                f"<span>{row['product_name'][:38]}…</span>"
                f"<b style='color:{ACCENT}'>{int(row['qty'])} {unit}</b></div>"
                f"<div style='height:6px;border-radius:3px;background:rgba(128,128,128,0.2)'>"
                f"<div style='height:6px;border-radius:3px;width:{pct}%;background:{ACCENT}'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
        st.page_link("pages/2_Incidents.py", label=t("home.link.full_journal"), icon="🚨")

    with mid:
        st.markdown(f"##### {t('home.dist_title')}")
        crit_label = t("home.dist.critical")
        low_label = t("home.dist.low")
        norm_label = t("home.dist.normal")
        dist = pd.DataFrame({
            "bucket": [crit_label, low_label, norm_label],
            "skus": [
                int((stock["qty"] <= 3).sum()),
                int(((stock["qty"] > 3) & (stock["qty"] <= 10)).sum()),
                int((stock["qty"] > 10).sum()),
            ],
        })
        fig = px.pie(dist, names="bucket", values="skus", hole=0.6,
                     color="bucket",
                     color_discrete_map={crit_label: ACCENT,
                                         low_label: AMBER,
                                         norm_label: BLUE})
        fig.update_layout(height=260, showlegend=True,
                          legend=dict(orientation="h", y=-0.15),
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown(f"##### {t('home.top_title')}")
        top = stock.nlargest(5, "qty").sort_values("qty")
        fig = px.bar(top, x="qty", y="product_name", orientation="h",
                     text="qty", color_discrete_sequence=[BLUE])
        fig.update_traces(textposition="outside")
        fig.update_layout(height=260, yaxis_title=None, xaxis_title=None,
                          yaxis=dict(tickfont=dict(size=10)),
                          margin=dict(l=0, r=10, t=10, b=0))
        fig.update_yaxes(ticktext=[n[:28] + "…" for n in top["product_name"]],
                         tickvals=top["product_name"])
        st.plotly_chart(fig, use_container_width=True)
        st.page_link("pages/1_Stock.py", label=t("home.link.full_analytics"), icon="📦")

    st.divider()

# ---------- как это работает / roadmap ----------
with st.expander(t("home.how_title")):
    st.markdown(t("home.how_body"))

with st.expander(t("home.roadmap_title")):
    st.markdown(t("home.roadmap_table"))

# ---------- служебное ----------
with st.expander(t("home.diag_title"), expanded=False):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.execute("SELECT MAX(snapshot_date), COUNT(*) FROM kabinet_data.stock_local;")
        snap_date, snap_rows = cur.fetchone()
        cur.execute("SELECT MAX(created_at) FROM kabinet_data.incidents;")
        last_inc = cur.fetchone()[0]
        cur.close()
        conn.close()
        st.success(t("home.diag_ok"))
        st.code(
            f"{version}\n"
            f"{t('home.diag_stock_line').format(rows=snap_rows, date=snap_date)}\n"
            f"{t('home.diag_incidents_line').format(date=last_inc)}",
            language="text",
        )
    except Exception as e:
        st.error(f"{t('home.diag_error')}: {e}")
