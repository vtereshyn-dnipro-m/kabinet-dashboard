# pages/2_Incidents.py — Инциденты: единый журнал проблем
import pandas as pd
import streamlit as st
import plotly.express as px

from db.connection import get_connection

st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #f8f9fb;
    border: 1px solid #e6e8ee;
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)

st.title("Инциденты")
st.caption(
    "Единый журнал проблем со всех разделов системы: что требует действия прямо сейчас. "
    "Источники: остатки (активно) · поставки и продажи (скоро)"
)

with st.expander("ℹ️ Как это работает"):
    st.markdown("""
    Инциденты создаются **автоматически** при каждом обновлении данных:

    | Тип | Правило | Источник | Статус |
    |---|---|---|---|
    | 🔴 out_of_stock | остаток = 0 | Остатки | ✅ активно |
    | 🟡 low_stock | остаток ≤ 3 шт | Остатки | ✅ активно |
    | 🟠 stuck_shipment | поставка без движения | Поставки | 🔜 скоро |
    | 🟣 sales_anomaly | резкий рост/падение продаж | Продажи | 🔜 скоро |

    Когда проблема исчезает (например, сток пополнен) — инцидент закрывается сам.
    """)

@st.cache_data(ttl=300)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT id, created_at, incident_type, sku, warehouse_name,
               severity, message, status
        FROM kabinet_data.incidents
        ORDER BY
            CASE status WHEN 'open' THEN 0 ELSE 1 END,
            CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            created_at DESC
    """, conn)
    conn.close()
    return df

df = load_incidents()

if df.empty:
    st.info("Инцидентов пока нет. Либо всё хорошо, либо генератор ещё не запускался 🙂")
    st.stop()

# ---------- фильтры ----------
c1, c2, c3 = st.columns(3)
with c1:
    sev = st.multiselect("Уровень серьёзности",
                         sorted(df["severity"].unique()),
                         default=sorted(df["severity"].unique()))
with c2:
    statuses = sorted(df["status"].unique())
    default_status = ["open"] if "open" in statuses else statuses
    stat = st.multiselect("Статус", statuses, default=default_status)
with c3:
    itype = st.multiselect("Тип", sorted(df["incident_type"].unique()),
                           default=sorted(df["incident_type"].unique()))

f = df[df["severity"].isin(sev) & df["status"].isin(stat) & df["incident_type"].isin(itype)]

# ---------- KPI ----------
open_df = df[df["status"] == "open"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Открытых", len(open_df))
k2.metric("🔴 Critical", int((open_df["severity"] == "critical").sum()))
k3.metric("🟡 Warning", int((open_df["severity"] == "warning").sum()))
k4.metric("Закрыто (всего)", int((df["status"] == "resolved").sum()))

st.divider()

# ---------- разбивка ----------
left, right = st.columns([2, 3])
with left:
    by_type = open_df.groupby("incident_type").size().reset_index(name="count")
    if not by_type.empty:
        fig = px.pie(by_type, names="incident_type", values="count",
                     hole=0.55, title="Открытые по типу",
                     color="incident_type",
                     color_discrete_map={"out_of_stock": "#e24b4a",
                                         "low_stock": "#f2b134",
                                         "stuck_shipment": "#ef9f27",
                                         "sales_anomaly": "#7f77dd"})
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

with right:
    dyn = (df.assign(day=pd.to_datetime(df["created_at"]).dt.date)
             .groupby(["day", "severity"]).size().reset_index(name="count"))
    if dyn["day"].nunique() > 1:
        fig = px.bar(dyn, x="day", y="count", color="severity",
                     title="Новые инциденты по дням",
                     color_discrete_map={"critical": "#e24b4a", "warning": "#f2b134"})
        fig.update_layout(height=280, xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("📈 График динамики появится, когда накопится история за несколько дней")

# ---------- таблица ----------
SEV_ICON = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
show = f.copy()
show["severity"] = show["severity"].map(lambda s: f"{SEV_ICON.get(s, '')} {s}")
show["created_at"] = pd.to_datetime(show["created_at"]).dt.strftime("%d.%m.%Y %H:%M")

st.dataframe(
    show[["created_at", "severity", "incident_type", "sku",
          "warehouse_name", "message", "status"]],
    use_container_width=True, height=480, hide_index=True,
    column_config={
        "created_at": st.column_config.TextColumn("Создан", width="small"),
        "severity": st.column_config.TextColumn("Уровень", width="small"),
        "incident_type": st.column_config.TextColumn("Тип", width="small"),
        "message": st.column_config.TextColumn("Описание", width="large"),
        "status": st.column_config.TextColumn("Статус", width="small"),
    },
)

st.download_button(
    "⬇️ Скачать CSV",
    f.to_csv(index=False).encode("utf-8-sig"),
    file_name="incidents.csv",
    mime="text/csv",
)
