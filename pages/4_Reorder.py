# pages/4_Reorder.py — Автозаказ: рекомендации по пополнению
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

st.title("Автозаказ")
st.caption("Что и сколько заказать: скорость продаж × остаток × срок поставки. "
           "Система считает точку заказа сама.")

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
    st.info("Рекомендации ещё не рассчитаны. Запусти ячейку автозаказа в пайплайне.")
    st.stop()

URG_ORDER = {"critical": 0, "warning": 1, "ok": 2}
URG_ICON = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}
URG_LABEL = {"critical": "Заказать срочно", "warning": "Пора заказывать", "ok": "В норме"}

df["urg_rank"] = df["urgency"].map(URG_ORDER)

# ---------- KPI ----------
c1, c2, c3, c4 = st.columns(4)
crit = df[df["urgency"] == "critical"]
warn = df[df["urgency"] == "warning"]
c1.metric("🔴 Заказать срочно", len(crit),
          help="Кончатся раньше, чем приедет поставка")
c2.metric("🟡 Пора заказывать", len(warn))
c3.metric("Всего к заказу, шт",
          int(df.loc[df["urgency"] != "ok", "suggested_qty"].sum()))
c4.metric("SKU под контролем", len(df))

st.divider()

# ---------- срочные — крупно ----------
if not crit.empty:
    st.markdown("#### 🔴 Требуют заказа в первую очередь")
    top = crit.sort_values("days_of_cover").head(6)
    cols = st.columns(min(len(top), 3))
    for i, (_, r) in enumerate(top.iterrows()):
        with cols[i % 3]:
            st.metric(
                label=f"{str(r['sku'])[:16]}",
                value=f"заказать {int(r['suggested_qty'])}",
                delta=f"хватит на {r['days_of_cover']:.0f} дн",
                delta_color="inverse",
                help=f"{r['product_name'][:70]} · продаётся {r['daily_velocity']:.1f}/день",
            )
    st.divider()

# ---------- фильтр ----------
f1, f2 = st.columns([1, 2])
with f1:
    urg_filter = st.multiselect(
        "Срочность",
        ["critical", "warning", "ok"],
        default=["critical", "warning"],
        format_func=lambda x: f"{URG_ICON[x]} {URG_LABEL[x]}",
    )
with f2:
    search = st.text_input("Поиск по SKU / названию", placeholder="напр. Amoladora")

f = df[df["urgency"].isin(urg_filter)]
if search:
    mask = (f["sku"].str.contains(search, case=False, na=False)
            | f["product_name"].str.contains(search, case=False, na=False))
    f = f[mask]

# ---------- таблица рекомендаций ----------
show = f.sort_values(["urg_rank", "days_of_cover"]).copy()
show["Срочность"] = show["urgency"].map(lambda u: f"{URG_ICON.get(u, '')} {URG_LABEL.get(u, u)}")
show["Продаётся/день"] = show["daily_velocity"].round(1)
show["Хватит, дней"] = show["days_of_cover"].round(0)

st.dataframe(
    show[["Срочность", "sku", "product_name", "current_stock",
          "Продаётся/день", "Хватит, дней", "suggested_qty"]],
    use_container_width=True, height=460, hide_index=True,
    column_config={
        "sku": st.column_config.TextColumn("SKU", width="small"),
        "product_name": st.column_config.TextColumn("Товар", width="large"),
        "current_stock": st.column_config.NumberColumn("Остаток", width="small"),
        "Хватит, дней": st.column_config.NumberColumn("Хватит, дней", width="small",
                                                      help="На сколько дней хватит при текущей скорости продаж"),
        "suggested_qty": st.column_config.NumberColumn("Заказать, шт", width="small",
                                                       help="Рекомендуемое количество к заказу"),
    },
)

# ---------- выгрузка заказа ----------
order = f[f["urgency"] != "ok"][["sku", "product_name", "current_stock",
                                  "daily_velocity", "days_of_cover", "suggested_qty"]]
st.download_button(
    f"⬇️ Скачать заказ ({len(order)} SKU, {int(order['suggested_qty'].sum())} шт)",
    order.to_csv(index=False).encode("utf-8-sig"),
    file_name="reorder.csv",
    mime="text/csv",
    disabled=order.empty,
)

# ---------- как считается ----------
with st.expander("ℹ️ Как считается автозаказ"):
    st.markdown("""
    - **Скорость продаж** — среднее за последние 30 дней (из истории заказов)
    - **Хватит дней** = остаток / скорость продаж
    - **🔴 Заказать срочно** — хватит меньше, чем срок поставки (не успеваем)
    - **🟡 Пора заказывать** — остаток ниже точки заказа (срок поставки + страховой запас)
    - **Заказать, шт** — сколько нужно, чтобы покрыть спрос на 60 дней вперёд

    Параметры (срок поставки, страховой запас) пока общие — скоро вынесем в настройки,
    и посчитаем реальный срок поставки по каждому складу из истории поставок.
    """)
