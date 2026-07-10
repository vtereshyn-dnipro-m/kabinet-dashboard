# home.py — Обзор: executive-сводка
import pandas as pd
import streamlit as st
import plotly.express as px

from db.connection import get_connection

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
    _logo = "logo_dark.png" if st.context.theme.type == "dark" else "logo_light.png"
except Exception:
    _logo = "logo_light.png"
st.image(_logo, width=140)
st.title("Кабинет Demand & Supply")
st.caption("Система сама находит проблемы и приносит их вам")

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
    st.error(f"❌ Нет подключения к базе: {e}")

if db_ok:
    open_inc = inc[inc["status"].isin(["open", "acknowledged"])]
    critical = int((open_inc["severity"] == "critical").sum())
    low_stock_cnt = int((stock["qty"] <= 3).sum())
    health = max(0, 100 - round(100 * low_stock_cnt / max(len(stock), 1)))

    # ---------- KPI ----------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💚 Здоровье каталога", f"{health}%",
              help="Доля SKU с достаточным запасом (остаток > 3). "
                   f"Данные на {snap}")
    c2.metric("SKU под контролем", len(stock))
    c3.metric("Суммарный остаток", int(stock["qty"].sum()))
    c4.metric("Открытых инцидентов", len(open_inc),
              delta=f"{critical} critical" if critical else None,
              delta_color="inverse" if critical else "off")
    c5.metric("Решено автоматически",
              int((inc["status"] == "resolved").sum()),
              help="Система сама закрыла после пополнения стока")

    st.divider()

    # ---------- визуальная сводка ----------
    left, mid, right = st.columns([1.2, 1, 1.2])

    with left:
        st.markdown("##### 🔥 Требуют внимания первыми")
        burn = stock.nsmallest(5, "qty")
        for _, row in burn.iterrows():
            pct = min(row["qty"] / 10 * 100, 100)
            st.markdown(
                f"<div style='margin-bottom:10px'>"
                f"<div style='display:flex;justify-content:space-between;font-size:0.85rem'>"
                f"<span>{row['product_name'][:38]}…</span>"
                f"<b style='color:{ACCENT}'>{int(row['qty'])} шт</b></div>"
                f"<div style='height:6px;border-radius:3px;background:rgba(128,128,128,0.2)'>"
                f"<div style='height:6px;border-radius:3px;width:{pct}%;background:{ACCENT}'></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
        st.page_link("pages/2_Incidents.py", label="Весь журнал →", icon="🚨")

    with mid:
        st.markdown("##### Распределение запаса")
        dist = pd.DataFrame({
            "bucket": ["критично (≤3)", "мало (4–10)", "норма (>10)"],
            "skus": [
                int((stock["qty"] <= 3).sum()),
                int(((stock["qty"] > 3) & (stock["qty"] <= 10)).sum()),
                int((stock["qty"] > 10).sum()),
            ],
        })
        fig = px.pie(dist, names="bucket", values="skus", hole=0.6,
                     color="bucket",
                     color_discrete_map={"критично (≤3)": ACCENT,
                                         "мало (4–10)": AMBER,
                                         "норма (>10)": BLUE})
        fig.update_layout(height=260, showlegend=True,
                          legend=dict(orientation="h", y=-0.15),
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("##### Топ запаса (куда вложены деньги)")
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
        st.page_link("pages/1_Stock.py", label="Полная аналитика →", icon="📦")

    st.divider()

# ---------- как это работает / roadmap ----------
with st.expander("⚙️ Как устроена система"):
    st.markdown("""
    ```
    Databricks (данные)  →  Loader (правила)  →  Lakebase (состояние)  →  этот дашборд
    ```

    Каждый день система автоматически: обновляет остатки → проверяет правила
    (остаток = 0, остаток ≤ 3) → открывает инциденты по новым проблемам →
    закрывает инциденты по решённым. Человек нужен там, где нужно решение,
    а не там, где нужно смотреть в таблицы.
    """)

with st.expander("🗺️ Что дальше (roadmap)"):
    st.markdown("""
    | Этап | Что даёт | Статус |
    |---|---|---|
    | Правила по остаткам | инциденты low stock / out of stock | ✅ в проде |
    | История снапшотов | тренды остатков, динамика инцидентов | 🔄 копится |
    | Данные продаж | умные пороги (days of cover), прогноз спроса | 🔜 следующий шаг |
    | Поставки в пути | инциденты «зависшая поставка», точный дозаказ | 🔜 |
    | Новые каналы | Shopify, Leroy Merlin (Mirakl) в тот же контур | 🔜 |
    | ИИ-агент | триаж инцидентов, черновики заказов, алерты в Telegram | 🔜 |
    """)

# ---------- служебное ----------
with st.expander("🔧 Диагностика", expanded=False):
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
        st.success("✅ Lakebase доступен")
        st.code(
            f"{version}\n"
            f"stock_local: {snap_rows} строк, последний снапшот {snap_date}\n"
            f"incidents: последняя запись {last_inc}",
            language="text",
        )
    except Exception as e:
        st.error(f"❌ Ошибка подключения: {e}")
