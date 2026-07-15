# pages/4_Reorder.py — Автозаказ: рекомендации по пополнению
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

st.title(t("ro.title"))
st.caption(t("ro.caption"))

@st.cache_data(ttl=300)
def load_reorder():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT sku, product_name, current_stock, daily_velocity,
               days_of_cover, reorder_point, suggested_qty, urgency
        FROM kabinet_data.reorder_recommendations
        WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.reorder_recommendations)
    """, conn)
    conn.close()
    return df

df = load_reorder()

if df.empty:
    st.info(t("ro.empty"))
    st.stop()

URG_ORDER = {"critical": 0, "warning": 1, "ok": 2}
URG_ICON = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}

def urg_label(u: str) -> str:
    return t(f"ro.urg.{u}")

df["urg_rank"] = df["urgency"].map(URG_ORDER)

# ---------- KPI ----------
c1, c2, c3, c4 = st.columns(4)
crit = df[df["urgency"] == "critical"]
warn = df[df["urgency"] == "warning"]
c1.metric(t("ro.kpi.critical"), len(crit),
          help=t("ro.kpi.critical_help"))
c2.metric(t("ro.kpi.warning"), len(warn))
c3.metric(t("ro.kpi.total_qty"),
          int(df.loc[df["urgency"] != "ok", "suggested_qty"].sum()))
c4.metric(t("ro.kpi.sku_controlled"), len(df))

st.divider()

# ---------- срочные — крупно ----------
if not crit.empty:
    st.markdown(f"#### {t('ro.priority_title')}")
    top = crit.sort_values("days_of_cover").head(6)
    cols = st.columns(min(len(top), 3))
    for i, (_, r) in enumerate(top.iterrows()):
        with cols[i % 3]:
            st.metric(
                label=f"{str(r['sku'])[:16]}",
                value=t("ro.priority.value").format(n=int(r['suggested_qty'])),
                delta=t("ro.priority.delta").format(n=r['days_of_cover']),
                delta_color="inverse",
                help=t("ro.priority.help").format(name=r['product_name'][:70], v=r['daily_velocity']),
            )
    st.divider()

# ---------- фильтр ----------
f1, f2 = st.columns([1, 2])
with f1:
    urg_filter = st.multiselect(
        t("ro.filter.urgency"),
        ["critical", "warning", "ok"],
        default=["critical", "warning"],
        format_func=lambda x: f"{URG_ICON[x]} {urg_label(x)}",
    )
with f2:
    search = st.text_input(t("ro.filter.search"), placeholder=t("ro.filter.search_placeholder"))

f = df[df["urgency"].isin(urg_filter)]
if search:
    mask = (f["sku"].str.contains(search, case=False, na=False)
            | f["product_name"].str.contains(search, case=False, na=False))
    f = f[mask]

# ---------- таблица рекомендаций ----------
col_urgency = t("ro.tbl.col_urgency")
col_velocity = t("ro.tbl.col_velocity")
col_days_left = t("ro.tbl.col_days_left")

show = f.sort_values(["urg_rank", "days_of_cover"]).copy()
show[col_urgency] = show["urgency"].map(lambda u: f"{URG_ICON.get(u, '')} {urg_label(u)}")
show[col_velocity] = show["daily_velocity"].round(1)
show[col_days_left] = show["days_of_cover"].round(0)

st.dataframe(
    show[[col_urgency, "sku", "product_name", "current_stock",
          col_velocity, col_days_left, "suggested_qty"]],
    use_container_width=True, height=460, hide_index=True,
    column_config={
        "sku": st.column_config.TextColumn(t("ro.tbl.col_sku"), width="small"),
        "product_name": st.column_config.TextColumn(t("ro.tbl.col_product"), width="large"),
        "current_stock": st.column_config.NumberColumn(t("ro.tbl.col_stock"), width="small"),
        col_days_left: st.column_config.NumberColumn(col_days_left, width="small",
                                                      help=t("ro.tbl.col_days_left_help")),
        "suggested_qty": st.column_config.NumberColumn(t("ro.tbl.col_suggested"), width="small",
                                                       help=t("ro.tbl.col_suggested_help")),
    },
)

# ---------- выгрузка заказа ----------
order = f[f["urgency"] != "ok"][["sku", "product_name", "current_stock",
                                  "daily_velocity", "days_of_cover", "suggested_qty"]]
st.download_button(
    t("ro.download_btn").format(n=len(order), qty=int(order['suggested_qty'].sum())),
    order.to_csv(index=False).encode("utf-8-sig"),
    file_name="reorder.csv",
    mime="text/csv",
    disabled=order.empty,
)

# ---------- как считается ----------
with st.expander(t("ro.how_title")):
    st.markdown(t("ro.how_body"))
