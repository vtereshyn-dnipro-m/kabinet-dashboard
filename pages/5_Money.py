# pages/5_Money.py — Деньги: полная P&L (Contribution Margin)
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
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

st.title(t("money.title"))
st.caption(t("money.caption"))

def clean_sku(sku: str) -> str:
    s = str(sku or "").strip()
    s = re.sub(r"^amzn\.gr\.", "", s)
    s = s.replace("-FBA", "").replace("-FBM", "")
    s = re.sub(r"-[A-Za-z0-9]{8,}$", "", s)
    s = re.sub(r"-[A-Za-z]$", "", s)
    return s.strip(" -")

WINDOW = 30  # окно P&L, дней

@st.cache_data(ttl=600)
def load_pnl():
    conn = get_connection()
    df = pd.read_sql(f"""
        SELECT e.norm_sku, e.product_name, e.marketplace, e.sales_date,
               e.units_ordered      AS units,
               e.ordered_product_sales AS gross_revenue,
               e.net_product_sales  AS revenue,
               e.total_fees         AS fees,
               e.net_proceeds_total AS net_proceeds,
               COALESCE(e.cogs, 0)  AS cogs_unit,
               COALESCE(a.total_spend, 0) AS ads
        FROM kabinet_data.economics_summary e
        LEFT JOIN kabinet_data.ads_spend a
          ON a.date = e.sales_date
         AND a.marketplace = e.marketplace
         AND a.norm_sku = e.norm_sku
        WHERE e.sales_date >= (SELECT MAX(sales_date) - INTERVAL '{WINDOW} days'
                               FROM kabinet_data.economics_summary)
    """, conn)
    conn.close()
    return df

df = load_pnl()
if df.empty:
    st.info(t("money.empty"))
    st.stop()

df["sku_display"] = df["norm_sku"].apply(clean_sku)
for c in ["units", "gross_revenue", "revenue", "fees", "net_proceeds", "cogs_unit", "ads"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
df["cogs_total"] = df["cogs_unit"] * df["units"]

# ---------- фильтры ----------
c1, c2 = st.columns([1, 2])
with c1:
    mp_filter = st.multiselect(
        t("money.filter.country"),
        sorted(df["marketplace"].dropna().unique().tolist()),
        placeholder=t("money.filter.country_ph"),
    )
with c2:
    search = st.text_input(t("money.filter.search"), placeholder=t("money.filter.search_ph"))

f = df.copy()
if mp_filter:
    f = f[f["marketplace"].isin(mp_filter)]
if search:
    f = f[f["sku_display"].str.contains(search, case=False, na=False)]

# ---------- KPI: полная воронка P&L ----------
tot_rev = f["revenue"].sum()
tot_net = f["net_proceeds"].sum()
tot_cogs = f["cogs_total"].sum()
tot_ads = f["ads"].sum()
cm = tot_net - tot_cogs - tot_ads
cm_pct = (cm / tot_rev * 100) if tot_rev > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("money.kpi.revenue").format(d=WINDOW), f"{tot_rev:,.0f} €")
k2.metric(t("money.kpi.net"), f"{tot_net:,.0f} €", help=t("money.kpi.net_help"))
k3.metric(t("money.kpi.cogs"), f"−{tot_cogs:,.0f} €", help=t("money.kpi.cogs_help"))
k4.metric(t("money.kpi.ads"), f"−{tot_ads:,.0f} €", help=t("money.kpi.ads_help"))
k5.metric(t("money.kpi.cm"), f"{cm:,.0f} €", delta=f"{cm_pct:.1f}%",
          help=t("money.kpi.cm_help"))

st.divider()

tab_pnl, tab_country, tab_fees = st.tabs(
    [t("money.tab.pnl"), t("money.tab.by_country"), t("money.tab.fees")]
)
BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"

def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)

# ---------- P&L по товарам ----------
with tab_pnl:
    by_sku = (f.groupby(["sku_display", "norm_sku"], as_index=False)
                .agg(product_name=("product_name", "first"),
                     units=("units", "sum"), revenue=("revenue", "sum"),
                     fees=("fees", "sum"), net_proceeds=("net_proceeds", "sum"),
                     cogs=("cogs_total", "sum"), ads=("ads", "sum")))
    by_sku["cm"] = by_sku["net_proceeds"] - by_sku["cogs"] - by_sku["ads"]
    by_sku["cm_pct"] = np.round(safe_div(by_sku["cm"], by_sku["revenue"]) * 100, 1)
    by_sku["acos_pct"] = np.round(safe_div(by_sku["ads"], by_sku["revenue"]) * 100, 1)

    def flag(row):
        if row["cm"] < 0:
            return "🔴"
        if row["cm_pct"] < 5:
            return "🟠"
        if row["cm_pct"] < 15:
            return "🟡"
        return "🟢"
    by_sku["⚑"] = by_sku.apply(flag, axis=1)
    by_sku = by_sku.sort_values("cm", ascending=False)

    # алерты: убыточные и почти нулевые
    losers = by_sku[by_sku["cm"] < 0]
    thin = by_sku[(by_sku["cm"] >= 0) & (by_sku["cm_pct"] < 5) & (by_sku["revenue"] > 500)]
    if not losers.empty or not thin.empty:
        alert_parts = []
        if not losers.empty:
            alert_parts.append(t("money.alert.losers").format(
                n=len(losers), skus=", ".join(losers["sku_display"].head(5))))
        if not thin.empty:
            alert_parts.append(t("money.alert.thin").format(
                n=len(thin), skus=", ".join(thin["sku_display"].head(5))))
        st.warning("  \n".join(alert_parts))

    cprof1, cprof2 = st.columns(2)
    with cprof1:
        st.markdown(f"**{t('money.top_cm')}**")
        top = by_sku.nlargest(10, "cm")
        fig = px.bar(top.sort_values("cm"), x="cm", y="sku_display",
                     orientation="h", text="cm", color_discrete_sequence=[GREEN])
        fig.update_traces(texttemplate="%{text:.0f}€")
        fig.update_layout(height=340, yaxis_title=None, xaxis_title="€",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cprof2:
        st.markdown(f"**{t('money.worst_cm')}**")
        worst = by_sku[by_sku["units"] > 0].nsmallest(10, "cm")
        fig = px.bar(worst.sort_values("cm", ascending=False),
                     x="cm", y="sku_display", orientation="h",
                     text="cm", color_discrete_sequence=[ACCENT])
        fig.update_traces(texttemplate="%{text:.0f}€")
        fig.update_layout(height=340, yaxis_title=None, xaxis_title="€",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"**{t('money.pnl_table')}**")
    st.dataframe(
        by_sku[["⚑", "sku_display", "product_name", "units", "revenue",
                "net_proceeds", "cogs", "ads", "cm", "cm_pct", "acos_pct"]],
        use_container_width=True, height=480, hide_index=True,
        column_config={
            "⚑": st.column_config.TextColumn("", width="small"),
            "sku_display": st.column_config.TextColumn("SKU", width="small"),
            "product_name": st.column_config.TextColumn(t("money.col.product"), width="medium"),
            "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €",
                help=t("money.col.net_help")),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €",
                help=t("money.col.cogs_help")),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €",
                help=t("money.col.cm_help")),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
            "acos_pct": st.column_config.NumberColumn("ACOS", format="%.1f%%",
                help=t("money.col.acos_help")),
        },
    )
    st.caption(t("money.pnl_note"))
    st.download_button(
        t("money.download"),
        by_sku.to_csv(index=False).encode("utf-8-sig"),
        file_name="pnl_by_sku.csv", mime="text/csv",
    )

# ---------- по странам ----------
with tab_country:
    by_c = (f.groupby("marketplace", as_index=False)
              .agg(units=("units", "sum"), revenue=("revenue", "sum"),
                   net_proceeds=("net_proceeds", "sum"),
                   cogs=("cogs_total", "sum"), ads=("ads", "sum")))
    by_c["cm"] = by_c["net_proceeds"] - by_c["cogs"] - by_c["ads"]
    by_c["cm_pct"] = np.round(safe_div(by_c["cm"], by_c["revenue"]) * 100, 1)
    by_c = by_c.sort_values("cm", ascending=False)

    cc = st.columns(min(len(by_c), 5) or 1)
    for i, (_, r) in enumerate(by_c.iterrows()):
        with cc[i % len(cc)]:
            st.metric(r["marketplace"], f"{r['cm']:,.0f} €",
                     delta=f"{r['cm_pct']:.0f}%",
                     help=t("money.country_metric_help"))

    melt = by_c.melt(id_vars="marketplace",
                     value_vars=["cm", "cogs", "ads"],
                     var_name="part", value_name="eur")
    part_names = {"cm": t("money.col.cm"), "cogs": "COGS", "ads": t("money.col.ads")}
    melt["part"] = melt["part"].map(part_names)
    fig = px.bar(melt, x="marketplace", y="eur", color="part",
                 title=t("money.country_chart"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT])
    fig.update_layout(height=380, xaxis_title=None, yaxis_title="€",
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_c[["marketplace", "units", "revenue", "net_proceeds", "cogs", "ads", "cm", "cm_pct"]],
        use_container_width=True, hide_index=True,
        column_config={
            "marketplace": st.column_config.TextColumn(t("money.col.country")),
            "units": st.column_config.NumberColumn(t("money.col.units")),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €"),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €"),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €"),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
        },
    )

# ---------- комиссии/структура ----------
with tab_fees:
    st.markdown(f"**{t('money.struct_title')}**")
    total_rev = f["revenue"].sum()
    parts = pd.DataFrame({
        "part": [t("money.col.cm"), "COGS", t("money.col.ads"),
                 t("money.struct.fees")],
        "value": [max(cm, 0), tot_cogs, tot_ads, f["fees"].sum()],
    })
    fig = px.pie(parts, names="part", values="value", hole=0.5,
                 title=t("money.struct_pie_title"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT, "#f2b134"])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    fee_share = (f.groupby("marketplace", as_index=False)
                   .agg(revenue=("revenue", "sum"), fees=("fees", "sum")))
    fee_share["fees_pct"] = np.round(safe_div(fee_share["fees"], fee_share["revenue"]) * 100, 1)
    fig = px.bar(fee_share.sort_values("fees_pct", ascending=False),
                 x="marketplace", y="fees_pct", text="fees_pct",
                 title=t("money.fees_by_country"), color_discrete_sequence=["#f2b134"])
    fig.update_traces(texttemplate="%{text:.0f}%")
    fig.update_layout(height=340, xaxis_title=None, yaxis_title=t("money.fees_axis"),
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(t("money.pnl_note"))
