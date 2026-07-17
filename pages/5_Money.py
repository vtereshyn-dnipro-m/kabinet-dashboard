# pages/5_Money.py — Деньги: юнит-экономика и прибыльность
import re
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

@st.cache_data(ttl=600)
def load_econ():
    conn = get_connection()
    # реальная структура: daily-строки (sales_date × marketplace × norm_sku)
    df = pd.read_sql("""
        SELECT norm_sku, product_name, marketplace, sales_date,
               units_ordered, net_product_sales, total_fees, net_proceeds_total
        FROM kabinet_data.economics_summary
        WHERE sales_date >= (SELECT MAX(sales_date) - INTERVAL '45 days'
                             FROM kabinet_data.economics_summary)
    """, conn)
    conn.close()
    return df

df = load_econ()
if df.empty:
    st.info(t("money.empty"))
    st.stop()

# базовые поля -> удобные имена
df = df.rename(columns={
    "net_product_sales": "revenue",
    "total_fees": "fees",
    "net_proceeds_total": "net_proceeds",
    "units_ordered": "units",
})
df["sku_display"] = df["norm_sku"].apply(clean_sku)
for c in ["units", "revenue", "fees", "net_proceeds"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

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

# ---------- KPI ----------
k1, k2, k3, k4 = st.columns(4)
tot_rev = f["revenue"].sum()
tot_net = f["net_proceeds"].sum()
tot_fees = f["fees"].sum()
avg_margin = (tot_net / tot_rev * 100) if tot_rev > 0 else 0
k1.metric(t("money.kpi.revenue").format(d=45), f"{tot_rev:,.0f} €")
k2.metric(t("money.kpi.net"), f"{tot_net:,.0f} €", help=t("money.kpi.net_help"))
k3.metric(t("money.kpi.margin"), f"{avg_margin:.1f}%")
k4.metric(t("money.kpi.fees"), f"{tot_fees:,.0f} €", help=t("money.kpi.fees_help"))

st.divider()

tab_sku, tab_country, tab_fees = st.tabs(
    [t("money.tab.by_sku"), t("money.tab.by_country"), t("money.tab.fees")]
)
BLUE = "#1f77b4"
ACCENT = "#e8484d"

# ---------- по SKU ----------
with tab_sku:
    by_sku = (f.groupby(["sku_display", "norm_sku"], as_index=False)
                .agg(units=("units", "sum"), revenue=("revenue", "sum"),
                     fees=("fees", "sum"), net_proceeds=("net_proceeds", "sum"),
                     product_name=("product_name", "first")))
    by_sku["profit_per_unit"] = (by_sku["net_proceeds"] /
                                 by_sku["units"].replace(0, pd.NA)).round(2)
    by_sku["margin_pct"] = (by_sku["net_proceeds"] /
                            by_sku["revenue"].replace(0, pd.NA) * 100).round(1)
    by_sku = by_sku.sort_values("net_proceeds", ascending=False)

    cprof1, cprof2 = st.columns(2)
    with cprof1:
        st.markdown(f"**{t('money.top_profit')}**")
        top = by_sku.nlargest(10, "net_proceeds")
        fig = px.bar(top.sort_values("net_proceeds"), x="net_proceeds", y="sku_display",
                     orientation="h", text="net_proceeds", color_discrete_sequence=[BLUE])
        fig.update_traces(texttemplate="%{text:.0f}€")
        fig.update_layout(height=340, yaxis_title=None, xaxis_title="€",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cprof2:
        st.markdown(f"**{t('money.low_margin')}**")
        low = by_sku[by_sku["units"] > 0].nsmallest(10, "margin_pct")
        fig = px.bar(low.sort_values("margin_pct", ascending=False),
                     x="margin_pct", y="sku_display", orientation="h",
                     text="margin_pct", color_discrete_sequence=[ACCENT])
        fig.update_traces(texttemplate="%{text:.0f}%")
        fig.update_layout(height=340, yaxis_title=None, xaxis_title="%",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"**{t('money.table_title')}**")
    st.dataframe(
        by_sku[["sku_display", "product_name", "units", "revenue", "fees",
                "net_proceeds", "profit_per_unit", "margin_pct"]],
        use_container_width=True, height=460, hide_index=True,
        column_config={
            "sku_display": st.column_config.TextColumn("SKU", width="small"),
            "product_name": st.column_config.TextColumn(t("money.col.product"), width="large"),
            "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "fees": st.column_config.NumberColumn(t("money.col.fees"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €"),
            "profit_per_unit": st.column_config.NumberColumn(t("money.col.ppu"), format="%.2f €"),
            "margin_pct": st.column_config.NumberColumn(t("money.col.margin"), format="%.1f%%"),
        },
    )
    st.download_button(
        t("money.download"),
        by_sku.to_csv(index=False).encode("utf-8-sig"),
        file_name="economics_by_sku.csv", mime="text/csv",
    )

# ---------- по странам ----------
with tab_country:
    by_c = (f.groupby("marketplace", as_index=False)
              .agg(units=("units", "sum"), revenue=("revenue", "sum"),
                   fees=("fees", "sum"), net_proceeds=("net_proceeds", "sum")))
    by_c["margin_pct"] = (by_c["net_proceeds"] /
                          by_c["revenue"].replace(0, pd.NA) * 100).round(1)
    by_c = by_c.sort_values("net_proceeds", ascending=False)

    cc = st.columns(min(len(by_c), 5) or 1)
    for i, (_, r) in enumerate(by_c.iterrows()):
        with cc[i % len(cc)]:
            st.metric(r["marketplace"], f"{r['net_proceeds']:,.0f} €",
                     help=f"{t('money.col.margin')}: {r['margin_pct']:.0f}%")

    fig = px.bar(by_c, x="marketplace", y=["net_proceeds", "fees"],
                 barmode="group", title=t("money.country_chart"),
                 color_discrete_sequence=[BLUE, ACCENT])
    fig.update_layout(height=380, xaxis_title=None, yaxis_title="€",
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_c[["marketplace", "units", "revenue", "fees", "net_proceeds", "margin_pct"]],
        use_container_width=True, hide_index=True,
        column_config={
            "marketplace": st.column_config.TextColumn(t("money.col.country")),
            "units": st.column_config.NumberColumn(t("money.col.units")),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "fees": st.column_config.NumberColumn(t("money.col.fees"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €"),
            "margin_pct": st.column_config.NumberColumn(t("money.col.margin"), format="%.1f%%"),
        },
    )

# ---------- комиссии ----------
with tab_fees:
    st.markdown(f"**{t('money.fees_title')}**")
    fee_share = (f.groupby("marketplace", as_index=False)
                   .agg(revenue=("revenue", "sum"), fees=("fees", "sum")))
    fee_share["fees_pct"] = (fee_share["fees"] /
                             fee_share["revenue"].replace(0, pd.NA) * 100).round(1)
    fig = px.bar(fee_share.sort_values("fees_pct", ascending=False),
                 x="marketplace", y="fees_pct", text="fees_pct",
                 title=t("money.fees_by_country"), color_discrete_sequence=[ACCENT])
    fig.update_traces(texttemplate="%{text:.0f}%")
    fig.update_layout(height=360, xaxis_title=None, yaxis_title=t("money.fees_axis"),
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    total_rev = f["revenue"].sum()
    total_fees = f["fees"].sum()
    total_net = f["net_proceeds"].sum()
    other = max(0, total_rev - total_fees - total_net)
    struct = pd.DataFrame({
        "part": [t("money.struct.net"), t("money.struct.fees"), t("money.struct.other")],
        "value": [total_net, total_fees, other],
    })
    fig = px.pie(struct, names="part", values="value", hole=0.5,
                 title=t("money.struct_title"),
                 color_discrete_sequence=[BLUE, ACCENT, "#9aa4b2"])
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(t("money.fees_note"))
