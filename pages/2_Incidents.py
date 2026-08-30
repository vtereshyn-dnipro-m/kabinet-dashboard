# pages/2_Incidents.py — Инциденты: единый журнал проблем
import pandas as pd
import streamlit as st
import plotly.express as px

from db.connection import get_connection
from i18n import init_lang, t
import catalog

init_lang()

# ---------- стили (темонезависимые) ----------
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

st.title(t("inc.title"))
st.caption(t("inc.caption"))

with st.expander(t("inc.how_title")):
    st.markdown(t("inc.how_body"))

SEV_ORDER = ["critical", "high", "warning", "low", "info"]  # от худшего к лучшему
SEV_ICON = {"critical": "🔴", "high": "🟠", "warning": "🟡", "low": "🟡", "info": "🔵"}
SEV_COLOR = {"critical": "#e24b4a", "high": "#ef9f27", "warning": "#f2b134",
             "low": "#f2b134", "info": "#5b9bd5"}

def sev_rank(s: str) -> int:
    return SEV_ORDER.index(s) if s in SEV_ORDER else len(SEV_ORDER)

def sev_label(s: str) -> str:
    return t(f"inc.sev.{s}") if f"inc.sev.{s}" in t.__globals__.get("TRANSLATIONS", {}) else s.capitalize()

# ttl=60: инциденты — сигнал «прямо сейчас», и страница открыта ради
# реакции на них. Остальные загрузчики на своих 300 с
@st.cache_data(ttl=60)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT i.id, i.created_at, i.incident_type, i.sku, i.warehouse_name,
               i.severity, i.message, i.status,
               s.qty AS current_qty
        FROM kabinet_data.incidents i
        LEFT JOIN (
            SELECT sku, warehouse_name, SUM(quantity) AS qty
            FROM kabinet_data.stock_local
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
            GROUP BY sku, warehouse_name
        ) s ON s.sku = i.sku AND s.warehouse_name = i.warehouse_name
    """, conn)
    conn.close()
    return df

df = load_incidents()

if df.empty:
    st.info(t("inc.empty"))
    st.stop()

STATUS_ORDER = {"open": 0, "acknowledged": 1, "resolved": 2}

df["severity"] = df["severity"].fillna("info").str.lower()
df["created_at"] = pd.to_datetime(df["created_at"])
df["age_days"] = (pd.Timestamp.now(tz=df["created_at"].dt.tz) - df["created_at"]).dt.days
df = df.sort_values(
    by=["status", "severity", "created_at"],
    key=lambda col: col.map(sev_rank) if col.name == "severity"
    else col.map(lambda s: STATUS_ORDER.get(s, 9)) if col.name == "status" else col,
    ascending=[True, True, False],
)

# ---------- фильтры ----------
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    sev = st.multiselect(t("inc.filter.severity"),
                         sorted(df["severity"].unique(), key=sev_rank),
                         default=sorted(df["severity"].unique(), key=sev_rank),
                         format_func=sev_label)
with c2:
    statuses = sorted(df["status"].unique(), key=lambda s: STATUS_ORDER.get(s, 9))
    default_status = [s for s in ("open", "acknowledged") if s in statuses] or statuses
    stat = st.multiselect(t("inc.filter.status"), statuses, default=default_status)
with c3:
    itype = st.multiselect(t("inc.filter.type"), sorted(df["incident_type"].unique()),
                           default=sorted(df["incident_type"].unique()))
with c4:
    search = st.text_input(t("inc.filter.search"), placeholder=t("inc.filter.search_placeholder"))

f = df[df["severity"].isin(sev) & df["status"].isin(stat) & df["incident_type"].isin(itype)]
if search:
    mask = (f["sku"].str.contains(search, case=False, na=False)
            | f["message"].str.contains(search, case=False, na=False))
    f = f[mask]

# ---------- KPI (динамические severity) ----------
open_df = df[df["status"] == "open"]
sev_counts = open_df["severity"].value_counts()
top_sevs = sorted(sev_counts.index.tolist(), key=sev_rank)[:2]

SEV_HELP = {
    "critical": t("inc.sev_help.critical"),
    "high": t("inc.sev_help.high"),
    "warning": t("inc.sev_help.warning"),
    "low": t("inc.sev_help.low"),
    "info": t("inc.sev_help.info"),
}

cols = st.columns(4)
cols[0].metric(
    t("inc.kpi.open"), len(open_df),
    help=t("inc.kpi.open_help"),
)
for i, s in enumerate(top_sevs, start=1):
    cols[i].metric(f"{SEV_ICON.get(s, '⚪')} {sev_label(s)}", int(sev_counts[s]),
                   help=SEV_HELP.get(s, ""))
for i in range(1 + len(top_sevs), 3):
    cols[i].metric("—", 0, help=t("inc.kpi.none_help"))
cols[3].metric(
    t("inc.kpi.resolved"), int((df["status"] == "resolved").sum()),
    help=t("inc.kpi.resolved_help"),
)

st.divider()

# ---------- 🔥 Топ горящих ----------
burning = (df[df["status"].isin(["open", "acknowledged"])]
           .dropna(subset=["current_qty"])
           .sort_values(["current_qty", "age_days"], ascending=[True, False])
           .head(5))
if not burning.empty:
    st.markdown(f"#### {t('inc.burning_title')}")
    bcols = st.columns(len(burning))
    unit = t("stock.ov.unit_short")
    for col, (_, row) in zip(bcols, burning.iterrows()):
        product = str(row["message"]).split(":")[0][:40]
        col.metric(
            label=f"{SEV_ICON.get(row['severity'], '⚪')} {row['sku'][:18]}",
            value=f"{int(row['current_qty'])} {unit}",
            delta=t("inc.age_delta_open").format(n=int(row["age_days"])) if row["age_days"] else t("inc.age_new"),
            delta_color="inverse" if row["age_days"] else "off",
            help=f"{product} · {row['warehouse_name']} · {t('inc.status_word')}: {row['status']}",
        )
    st.divider()

# ---------- графики ----------
left, mid, right = st.columns(3)

with left:
    by_type = open_df.groupby("incident_type").size().reset_index(name="count")
    if not by_type.empty:
        fig = px.pie(by_type, names="incident_type", values="count",
                     hole=0.55, title=t("inc.chart.by_type_title"),
                     color="incident_type",
                     color_discrete_map={"out_of_stock": "#e24b4a",
                                         "low_stock": "#f2b134",
                                         "stuck_shipment": "#ef9f27",
                                         "sales_anomaly": "#7f77dd"})
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

with mid:
    # Возраст открытых инцидентов: сколько дней висят без реакции
    age = open_df.copy()
    age["bucket"] = pd.cut(age["age_days"], bins=[-1, 0, 2, 6, 13, 9999],
                           labels=[t("inc.age.today"), t("inc.age.1_2d"), t("inc.age.3_6d"),
                                   t("inc.age.1_2w"), t("inc.age.gt2w")])
    by_age = age.groupby("bucket", observed=True).size().reset_index(name="count")
    fig = px.bar(by_age, x="bucket", y="count", text="count",
                 title=t("inc.chart.age_title"),
                 color_discrete_sequence=["#1f77b4"])
    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

with right:
    dyn = (df.assign(day=df["created_at"].dt.date)
             .groupby(["day", "severity"]).size().reset_index(name="count"))
    if dyn["day"].nunique() > 1:
        fig = px.bar(dyn, x="day", y="count", color="severity",
                     title=t("inc.chart.daily_title"),
                     color_discrete_map=SEV_COLOR)
        fig.update_layout(height=300, xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(f"**{t('inc.chart.dynamics_title')}**")
        st.caption(t("inc.chart.dynamics_caption"))

# ---------- таблица с выбором ----------
def update_status(ids: list, new_status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE kabinet_data.incidents SET status = %s WHERE id = ANY(%s)",
        (new_status, list(map(int, ids))),
    )
    conn.commit()
    cur.close()
    conn.close()

show = f.reset_index(drop=True).copy()
show["severity_icon"] = show["severity"].map(lambda s: f"{SEV_ICON.get(s, '⚪')} {sev_label(s)}")
show["created_str"] = show["created_at"].dt.strftime("%d.%m.%Y %H:%M")
# ASIN в инцидентах не хранится — добираем по артикулу, чтобы из строки
# инцидента можно было сразу открыть карточку и посмотреть, что там
show["asin_url"] = catalog.url_series(skus=show["sku"])
show["photo"] = catalog.image_series(skus=show["sku"])

event = st.dataframe(
    show[["photo", "created_str", "severity_icon", "incident_type", "sku",
          "asin_url", "warehouse_name", "current_qty", "message", "age_days",
          "status"]],
    use_container_width=True, height=480, hide_index=True,
    on_select="rerun", selection_mode="multi-row",
    column_config={
        "photo": catalog.image_column(),
        "created_str": st.column_config.TextColumn(t("inc.tbl.col_created"), width="small"),
        "severity_icon": st.column_config.TextColumn(t("inc.tbl.col_level"), width="small"),
        "incident_type": st.column_config.TextColumn(t("inc.tbl.col_type"), width="small"),
        "asin_url": catalog.asin_column(),
        "current_qty": st.column_config.NumberColumn(t("inc.tbl.col_qty"), width="small",
                                                     help=t("inc.tbl.col_qty_help")),
        "message": st.column_config.TextColumn(t("inc.tbl.col_desc"), width="large"),
        "age_days": st.column_config.NumberColumn(t("inc.tbl.col_age"), width="small",
                                                  help=t("inc.tbl.col_age_help")),
        "status": st.column_config.TextColumn(t("inc.tbl.col_status"), width="small"),
    },
)

selected_rows = event.selection.rows if event and event.selection else []
b1, b2, b3 = st.columns([1.2, 1.2, 3])
with b1:
    if st.button(t("inc.btn.acknowledge").format(n=len(selected_rows)),
                 disabled=not selected_rows, use_container_width=True):
        ids = show.loc[selected_rows, "id"].tolist()
        update_status(ids, "acknowledged")
        st.cache_data.clear()
        st.rerun()
with b2:
    if st.button(t("inc.btn.resolve").format(n=len(selected_rows)),
                 disabled=not selected_rows, use_container_width=True):
        ids = show.loc[selected_rows, "id"].tolist()
        update_status(ids, "resolved")
        st.cache_data.clear()
        st.rerun()
with b3:
    st.caption(t("inc.hint.select_rows"))

st.download_button(
    t("inc.btn.download"),
    f.to_csv(index=False).encode("utf-8-sig"),
    file_name="incidents.csv",
    mime="text/csv",
)
