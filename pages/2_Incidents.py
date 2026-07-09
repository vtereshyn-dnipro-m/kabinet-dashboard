# pages/2_Incidents.py — Инциденты: единый журнал проблем
import pandas as pd
import streamlit as st
import plotly.express as px

from db.connection import get_connection

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

SEV_ORDER = ["critical", "high", "warning", "low", "info"]  # от худшего к лучшему
SEV_ICON = {"critical": "🔴", "high": "🟠", "warning": "🟡", "low": "🟡", "info": "🔵"}
SEV_COLOR = {"critical": "#e24b4a", "high": "#ef9f27", "warning": "#f2b134",
             "low": "#f2b134", "info": "#5b9bd5"}

def sev_rank(s: str) -> int:
    return SEV_ORDER.index(s) if s in SEV_ORDER else len(SEV_ORDER)

@st.cache_data(ttl=300)
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
    st.info("Инцидентов пока нет. Либо всё хорошо, либо генератор ещё не запускался 🙂")
    st.stop()

df["severity"] = df["severity"].fillna("info").str.lower()
df["created_at"] = pd.to_datetime(df["created_at"])
df["age_days"] = (pd.Timestamp.now(tz=df["created_at"].dt.tz) - df["created_at"]).dt.days
df = df.sort_values(
    by=["status", "severity", "created_at"],
    key=lambda col: col.map(sev_rank) if col.name == "severity"
    else (col != "open").astype(int) if col.name == "status" else col,
    ascending=[True, True, False],
)

# ---------- фильтры ----------
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    sev = st.multiselect("Уровень серьёзности",
                         sorted(df["severity"].unique(), key=sev_rank),
                         default=sorted(df["severity"].unique(), key=sev_rank))
with c2:
    statuses = sorted(df["status"].unique())
    default_status = ["open"] if "open" in statuses else statuses
    stat = st.multiselect("Статус", statuses, default=default_status)
with c3:
    itype = st.multiselect("Тип", sorted(df["incident_type"].unique()),
                           default=sorted(df["incident_type"].unique()))
with c4:
    search = st.text_input("Поиск (SKU / текст)", placeholder="например 22635000")

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
    "critical": "Продажи уже остановлены: остаток = 0. Реагировать немедленно.",
    "high": "Высокий риск, требует реакции в ближайшие дни.",
    "warning": "Запас на исходе: остаток ≤ 3 шт. Спланировать пополнение.",
    "low": "Запас на исходе: остаток ≤ 3 шт. Спланировать пополнение.",
    "info": "Информационное уведомление, действия по ситуации.",
}

cols = st.columns(4)
cols[0].metric(
    "Открытых", len(open_df),
    help="Инциденты со статусом open — требуют действия. "
         "Закрываются автоматически, когда проблема исчезает из данных.",
)
for i, s in enumerate(top_sevs, start=1):
    cols[i].metric(f"{SEV_ICON.get(s, '⚪')} {s.capitalize()}", int(sev_counts[s]),
                   help=SEV_HELP.get(s, ""))
for i in range(1 + len(top_sevs), 3):
    cols[i].metric("—", 0, help="Инцидентов других уровней сейчас нет.")
cols[3].metric(
    "Закрыто (всего)", int((df["status"] == "resolved").sum()),
    help="Автозакрытые: сток пополнился — система сама перевела инцидент в resolved. "
         "Показатель того, что проблемы реально решаются.",
)

st.divider()

# ---------- графики ----------
left, mid, right = st.columns(3)

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
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

with mid:
    # Возраст открытых инцидентов: сколько дней висят без реакции
    age = open_df.copy()
    age["bucket"] = pd.cut(age["age_days"], bins=[-1, 0, 2, 6, 13, 9999],
                           labels=["сегодня", "1–2 дня", "3–6 дней",
                                   "1–2 недели", "> 2 недель"])
    by_age = age.groupby("bucket", observed=True).size().reset_index(name="count")
    fig = px.bar(by_age, x="bucket", y="count", text="count",
                 title="Возраст открытых (дней без реакции)",
                 color_discrete_sequence=["#1f77b4"])
    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

with right:
    dyn = (df.assign(day=df["created_at"].dt.date)
             .groupby(["day", "severity"]).size().reset_index(name="count"))
    if dyn["day"].nunique() > 1:
        fig = px.bar(dyn, x="day", y="count", color="severity",
                     title="Новые инциденты по дням",
                     color_discrete_map=SEV_COLOR)
        fig.update_layout(height=300, xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("**Динамика по дням**")
        st.caption("📈 Появится, когда накопится история за несколько дней. "
                   "Включи расписание лоадера — и через неделю здесь будет тренд.")

# ---------- таблица ----------
show = f.copy()
show["severity"] = show["severity"].map(lambda s: f"{SEV_ICON.get(s, '⚪')} {s}")
show["created_at"] = show["created_at"].dt.strftime("%d.%m.%Y %H:%M")

st.dataframe(
    show[["created_at", "severity", "incident_type", "sku",
          "warehouse_name", "current_qty", "message", "age_days", "status"]],
    use_container_width=True, height=480, hide_index=True,
    column_config={
        "created_at": st.column_config.TextColumn("Создан", width="small"),
        "severity": st.column_config.TextColumn("Уровень", width="small"),
        "incident_type": st.column_config.TextColumn("Тип", width="small"),
        "current_qty": st.column_config.NumberColumn("Остаток", width="small",
                                                     help="Актуальный остаток по последнему снапшоту"),
        "message": st.column_config.TextColumn("Описание", width="large"),
        "age_days": st.column_config.NumberColumn("Дней", width="small",
                                                  help="Сколько дней инцидент открыт"),
        "status": st.column_config.TextColumn("Статус", width="small"),
    },
)

st.download_button(
    "⬇️ Скачать CSV",
    f.to_csv(index=False).encode("utf-8-sig"),
    file_name="incidents.csv",
    mime="text/csv",
)
