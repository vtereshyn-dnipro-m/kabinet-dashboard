# pages/1_Stock.py — Остатки: аналитический дашборд
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from db.connection import get_connection  # поправь импорт под свой db/connection.py

st.set_page_config(page_title="Остатки — Кабинет управления", layout="wide")

# ---------- стили ----------
st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #f8f9fb;
    border: 1px solid #e6e8ee;
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
h1 { margin-bottom: 0.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("Остатки")
st.caption("Консолидация по складам: Amazon FBA + собственные/3PL")

# ---------- данные ----------
@st.cache_data(ttl=600)
def load_stock() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT snapshot_date, sku, asin, product_name,
               warehouse_name, availability_status, quality_status,
               quantity, source, sync_status
        FROM kabinet_data.stock_local
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
    """, conn)
    conn.close()
    return df

CATEGORY_MAP = {
    "amoladora": "Amoladoras (болгарки)",
    "martillo": "Martillos (перфораторы)",
    "taladro": "Taladros (дрели/шуруповёрты)",
    "destornillador": "Destornilladores (отвёртки)",
    "motosierra": "Motosierras (пилы)",
    "sierra": "Sierras (пилы)",
    "soldador": "Soldadores (сварка)",
    "compresor": "Compresores",
    "bateria": "Baterías / зарядки",
    "cargador": "Baterías / зарядки",
}

def detect_category(name: str) -> str:
    n = (name or "").lower()
    for key, cat in CATEGORY_MAP.items():
        if key in n:
            return cat
    return "Прочее"

df = load_stock()
if df.empty:
    st.warning("Нет данных в kabinet_data.stock_local")
    st.stop()

df["category"] = df["product_name"].apply(detect_category)
df["power_w"] = df["product_name"].str.extract(r"(\d{3,4})\s*W", flags=re.I)[0].astype(float)

# ---------- фильтры ----------
c1, c2, c3 = st.columns(3)
with c1:
    wh_filter = st.text_input("Склад (часть названия)")
with c2:
    sku_filter = st.text_input("SKU / артикул")
with c3:
    status_filter = st.selectbox(
        "Статус доступности",
        ["Все"] + sorted(df["availability_status"].dropna().unique().tolist()),
    )

f = df.copy()
if wh_filter:
    f = f[f["warehouse_name"].str.contains(wh_filter, case=False, na=False)]
if sku_filter:
    f = f[f["sku"].str.contains(sku_filter, case=False, na=False)]
if status_filter != "Все":
    f = f[f["availability_status"] == status_filter]

# ---------- KPI ----------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Всего SKU", f["sku"].nunique())
k2.metric("Складов", f["warehouse_name"].nunique())
k3.metric("Суммарный остаток", int(f["quantity"].sum()))
k4.metric("Медиана на SKU", int(f["quantity"].median()) if len(f) else 0)
low_stock = (f.groupby("sku")["quantity"].sum() <= 3).sum()
k5.metric("SKU с остатком ≤ 3", int(low_stock),
          delta=None, help="Кандидаты на пополнение")

st.divider()

tab_overview, tab_abc, tab_cat, tab_table = st.tabs(
    ["📊 Обзор", "🅰️ ABC-анализ", "🧰 Категории", "📋 Таблица"]
)

BLUE = "#1f77b4"
ACCENT = "#e8484d"  # фирменный красный Dnipro-M

# ---------- Обзор ----------
with tab_overview:
    left, right = st.columns([3, 2])

    with left:
        top = (f.groupby(["sku", "product_name"], as_index=False)["quantity"]
                 .sum().nlargest(15, "quantity"))
        top["label"] = top["product_name"].str.slice(0, 45) + "…"
        fig = px.bar(
            top.sort_values("quantity"),
            x="quantity", y="label", orientation="h",
            text="quantity", title="Топ-15 SKU по остатку",
            color_discrete_sequence=[BLUE],
            hover_data={"sku": True, "label": False},
        )
        fig.update_layout(height=520, yaxis_title=None, xaxis_title="шт",
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        by_status = f.groupby("availability_status", as_index=False)["quantity"].sum()
        fig = px.pie(by_status, names="availability_status", values="quantity",
                     hole=0.55, title="Остаток по статусу доступности",
                     color_discrete_sequence=[BLUE, ACCENT, "#9aa4b2", "#f2b134"])
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        hist = px.histogram(
            f.groupby("sku", as_index=False)["quantity"].sum(),
            x="quantity", nbins=20,
            title="Распределение остатка по SKU",
            color_discrete_sequence=[BLUE],
        )
        hist.update_layout(height=250, xaxis_title="шт на SKU",
                           yaxis_title="SKU", margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(hist, use_container_width=True)

# ---------- ABC ----------
with tab_abc:
    abc = (f.groupby(["sku", "product_name"], as_index=False)["quantity"].sum()
             .sort_values("quantity", ascending=False)
             .reset_index(drop=True))
    total = abc["quantity"].sum()
    abc["cum_pct"] = abc["quantity"].cumsum() / total * 100
    abc["class"] = np.where(abc["cum_pct"] <= 80, "A",
                    np.where(abc["cum_pct"] <= 95, "B", "C"))

    a1, a2, a3 = st.columns(3)
    for col, cls in zip((a1, a2, a3), ("A", "B", "C")):
        sub = abc[abc["class"] == cls]
        col.metric(f"Класс {cls}",
                   f"{len(sub)} SKU",
                   f"{sub['quantity'].sum() / total * 100:.0f}% остатка")

    fig = go.Figure()
    colors = abc["class"].map({"A": ACCENT, "B": "#f2b134", "C": "#9aa4b2"})
    fig.add_bar(x=abc.index, y=abc["quantity"], marker_color=colors,
                name="Остаток, шт",
                customdata=abc[["sku", "product_name", "class"]],
                hovertemplate="<b>%{customdata[0]}</b> (класс %{customdata[2]})"
                              "<br>%{customdata[1]}<br>Остаток: %{y}<extra></extra>")
    fig.add_scatter(x=abc.index, y=abc["cum_pct"], yaxis="y2",
                    name="Накопленный %", line=dict(color=BLUE, width=2))
    fig.add_hline(y=80, yref="y2", line_dash="dot", line_color="#666",
                  annotation_text="80%")
    fig.update_layout(
        title="Парето: вклад SKU в суммарный остаток",
        height=480,
        yaxis=dict(title="шт"),
        yaxis2=dict(title="накопленный %", overlaying="y", side="right",
                    range=[0, 105]),
        xaxis=dict(title="SKU (по убыванию остатка)", showticklabels=False),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=80, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("A — SKU, дающие 80% остатка; B — следующие 15%; C — хвост. "
               "Когда подключим продажи, пересчитаем ABC по velocity — это будет честнее.")

# ---------- Категории ----------
with tab_cat:
    by_cat = (f.groupby("category", as_index=False)
                .agg(quantity=("quantity", "sum"), skus=("sku", "nunique")))
    fig = px.treemap(by_cat, path=["category"], values="quantity",
                     title="Остаток по категориям инструмента",
                     color="quantity", color_continuous_scale="Blues",
                     custom_data=["skus"])
    fig.update_traces(hovertemplate="<b>%{label}</b><br>Остаток: %{value} шт"
                                    "<br>SKU: %{customdata[0]}<extra></extra>")
    fig.update_layout(height=450, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    pw = f.dropna(subset=["power_w"])
    if not pw.empty:
        fig = px.scatter(pw, x="power_w", y="quantity", color="category",
                         hover_data=["sku", "product_name"],
                         title="Мощность (W) vs остаток — где сидит сток")
        fig.update_layout(height=400, xaxis_title="Мощность, W",
                          yaxis_title="Остаток, шт",
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ---------- Таблица ----------
with tab_table:
    st.dataframe(
        f.sort_values("quantity", ascending=False),
        use_container_width=True, height=560,
        column_config={
            "quantity": st.column_config.ProgressColumn(
                "quantity", format="%d",
                min_value=0, max_value=int(f["quantity"].max()),
            ),
        },
    )
    st.download_button(
        "⬇️ Скачать CSV",
        f.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"stock_{f['snapshot_date'].max()}.csv",
        mime="text/csv",
    ) 
