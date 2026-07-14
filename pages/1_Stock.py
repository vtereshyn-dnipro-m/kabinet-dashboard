# pages/1_Stock.py — Остатки: аналитический дашборд
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from db.connection import get_connection

# ---------- стили ----------
st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
h1 { margin-bottom: 0.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("Остатки")
st.caption("Консолидация по складам: Amazon FBA (по странам) + собственные/3PL")

# ---------- данные ----------
@st.cache_data(ttl=600)
def load_stock() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT snapshot_date, sku, asin, product_name,
               warehouse_name, location, availability_status, quality_status,
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
# location может быть NULL для не-FBA источников — подстрахуемся
if "location" not in df.columns:
    df["location"] = None
df["location"] = df["location"].fillna("—")

# ---------- фильтры ----------
c1, c2, c3, c4 = st.columns(4)
with c1:
    wh_filter = st.text_input("Склад (часть названия)")
with c2:
    sku_filter = st.text_input("SKU / артикул")
with c3:
    status_filter = st.selectbox(
        "Статус доступности",
        ["Все"] + sorted(df["availability_status"].dropna().unique().tolist()),
    )
with c4:
    country_filter = st.multiselect(
        "Страна (FBA)",
        sorted(df["location"].unique().tolist()),
        placeholder="Все страны",
    )

f = df.copy()
if wh_filter:
    f = f[f["warehouse_name"].str.contains(wh_filter, case=False, na=False)]
if sku_filter:
    f = f[f["sku"].str.contains(sku_filter, case=False, na=False)]
if status_filter != "Все":
    f = f[f["availability_status"] == status_filter]
if country_filter:
    f = f[f["location"].isin(country_filter)]

# ---------- KPI ----------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Всего SKU", f["sku"].nunique())
k2.metric("Стран (FBA)", f["location"].nunique(),
          help="Количество стран, где лежит товар на Amazon FBA")
k3.metric("Суммарный остаток", int(f["quantity"].sum()))
k4.metric("Медиана на SKU",
          int(f.groupby("sku")["quantity"].sum().median()) if len(f) else 0)
low_stock = (f.groupby("sku")["quantity"].sum() <= 3).sum()
k5.metric("SKU с остатком ≤ 3", int(low_stock),
          delta=None, help="Кандидаты на пополнение (сумма по всем странам)")

st.divider()

# ---------- 🔥 Минимальные остатки ----------
burn = (f.groupby(["sku", "asin", "product_name"], as_index=False)["quantity"].sum()
          .sort_values("quantity").head(5))
if not burn.empty and burn["quantity"].min() <= 3:
    st.markdown("#### 🔥 Минимальные остатки — кандидаты на пополнение")
    bcols = st.columns(len(burn))
    for col, (_, row) in zip(bcols, burn.iterrows()):
        # разбивка по странам для этого SKU — где именно лежит остаток
        by_country = (f[f["sku"] == row["sku"]]
                        .groupby("location")["quantity"].sum())
        by_country = by_country[by_country > 0].sort_values(ascending=False)
        country_str = " · ".join(f"{c}: {int(q)}" for c, q in by_country.items())

        with col:
            st.metric(
                label=str(row["sku"])[:18],
                value=f"{int(row['quantity'])} шт",
                help=f"{row['product_name'][:80]}",
            )
            st.caption(f"📍 {country_str}" if country_str else "нет в наличии")
    st.divider()

tab_overview, tab_abc, tab_cat, tab_countries, tab_table = st.tabs(
    ["📊 Обзор", "🅰️ ABC-анализ", "🧰 Категории", "🌍 По странам", "📋 Таблица"]
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
            text="quantity", title="Топ-15 SKU по остатку (сумма по всем странам)",
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
    abc = (f.groupby(["sku", "asin", "product_name"], as_index=False)["quantity"].sum()
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
                              "<br>%{customdata[1]}<br>Остаток: %{y}"
                              "<br><i>Кликни — карточка товара со ссылкой</i><extra></extra>")
    fig.add_scatter(x=abc.index, y=abc["cum_pct"], yaxis="y2",
                    name="Накопленный %", line=dict(color=BLUE, width=2),
                    hoverinfo="skip")
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
    event = st.plotly_chart(fig, use_container_width=True,
                            on_select="rerun", selection_mode="points",
                            key="abc_chart")

    pts = event.selection.points if event and event.selection else []
    if pts:
        idx = pts[0].get("point_index")
        if idx is not None and idx < len(abc):
            row = abc.iloc[idx]
            # разбивка выбранного SKU по странам
            by_country = (f[f["sku"] == row["sku"]]
                            .groupby("location", as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
            cc1, cc2, cc3, cc4 = st.columns([2.5, 1, 1, 1.2])
            cc1.markdown(f"**{row['product_name']}**")
            cc2.metric("Остаток (всего)", f"{int(row['quantity'])} шт")
            cc3.metric("Класс", row["class"])
            cc4.link_button("Открыть на Amazon ↗",
                            f"https://www.amazon.es/dp/{row['asin']}",
                            use_container_width=True)
            if len(by_country) > 1:
                st.caption("По странам: " + " · ".join(
                    f"{r['location']}: {int(r['quantity'])}" for _, r in by_country.iterrows()
                ))
    else:
        st.caption("💡 Кликни по столбику — появится карточка товара со ссылкой на листинг")

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

# ---------- По странам (НОВОЕ) ----------
with tab_countries:
    st.markdown("##### Остаток по странам FBA")
    by_country = (f.groupby("location", as_index=False)
                    .agg(quantity=("quantity", "sum"), skus=("sku", "nunique"))
                    .sort_values("quantity", ascending=False))

    cc = st.columns(min(len(by_country), 6) or 1)
    for i, (_, row) in enumerate(by_country.iterrows()):
        with cc[i % len(cc)]:
            st.metric(row["location"], f"{int(row['quantity'])} шт",
                     help=f"{int(row['skus'])} SKU")

    fig = px.bar(by_country, x="location", y="quantity", text="quantity",
                 title="Остаток по странам", color_discrete_sequence=[BLUE])
    fig.update_layout(height=380, xaxis_title="Страна", yaxis_title="Остаток, шт",
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Матрица SKU × страна (топ-20 по остатку)")
    top_skus_df = (f.groupby(["sku", "product_name"], as_index=False)["quantity"]
                     .sum().nlargest(20, "quantity"))
    top_skus = top_skus_df["sku"].tolist()
    name_map = dict(zip(top_skus_df["sku"], top_skus_df["product_name"]))

    matrix_src = f[f["sku"].isin(top_skus)]
    pivot = (matrix_src.pivot_table(index="sku", columns="location",
                                    values="quantity", aggfunc="sum", fill_value=0)
                        .reindex(top_skus))  # сохраняем порядок по убыванию остатка

    # короткая подпись для оси Y: SKU + начало названия
    y_labels = [f"{sku} · {name_map.get(sku, '')[:28]}" for sku in pivot.index]

    fig = px.imshow(
        pivot.values,
        x=pivot.columns.tolist(),
        y=y_labels,
        color_continuous_scale="Blues",
        aspect="auto",
        labels=dict(x="Страна", y="", color="Остаток"),
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Страна: %{x}<br>Остаток: %{z} шт<extra></extra>"
    )
    fig.update_layout(
        height=44 * len(pivot) + 100,
        margin=dict(l=10, r=10, t=20, b=10),
        coloraxis_showscale=False,
    )
    event = st.plotly_chart(fig, use_container_width=True,
                            on_select="rerun", key="stock_matrix")

    # клик по ячейке -> карточка товара с деталями по всем странам
    pts = event.selection.points if event and event.selection else []
    if pts:
        y_clicked = pts[0].get("y")
        sku_clicked = None
        for sku, lbl in zip(pivot.index, y_labels):
            if lbl == y_clicked:
                sku_clicked = sku
                break
        if sku_clicked:
            row_info = df[df["sku"] == sku_clicked].iloc[0]
            by_country = (f[f["sku"] == sku_clicked]
                            .groupby("location", as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
            total_qty = int(by_country["quantity"].sum())

            cc1, cc2, cc3 = st.columns([2.5, 1, 1.2])
            cc1.markdown(f"**{row_info['product_name']}**  \n`{sku_clicked}`")
            cc2.metric("Остаток (всего)", f"{total_qty} шт")
            cc3.link_button("Открыть на Amazon ↗",
                            f"https://www.amazon.es/dp/{row_info['asin']}",
                            use_container_width=True)

            bc = st.columns(min(len(by_country), 6) or 1)
            for i, (_, r) in enumerate(by_country.iterrows()):
                with bc[i % len(bc)]:
                    st.metric(r["location"], f"{int(r['quantity'])} шт")
    else:
        st.caption("💡 Кликни по ячейке — увидишь товар целиком и остаток по всем странам")

    st.caption("Пусто/светлое = товара нет или мало в этой стране. Топ-20 — для наглядности карты. "
               "Полная таблица со всеми SKU — ниже.")

    st.divider()

    # ---------- полная таблица по ВСЕМ SKU (не только топ-20) ----------
    st.markdown("##### Полная таблица: все SKU × страны")

    full_pivot = (f.pivot_table(index="sku", columns="location",
                                values="quantity", aggfunc="sum", fill_value=0))
    full_pivot["Всего"] = full_pivot.sum(axis=1)
    full_pivot = full_pivot.sort_values("Всего", ascending=False)

    full_name_map = f.drop_duplicates("sku").set_index("sku")["product_name"]

    table_view = full_pivot.reset_index()
    table_view.insert(1, "Товар", table_view["sku"].map(full_name_map))

    country_cols = [c for c in full_pivot.columns if c != "Всего"]

    st.dataframe(
        table_view, use_container_width=True, height=520, hide_index=True,
        column_config={
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "Товар": st.column_config.TextColumn("Товар", width="large"),
            "Всего": st.column_config.NumberColumn("Всего", width="small"),
            **{col: st.column_config.NumberColumn(col, width="small")
               for col in country_cols},
        },
    )

    # ---------- строка ИТОГО ----------
    totals = {c: int(full_pivot[c].sum()) for c in full_pivot.columns}
    tcols = st.columns(len(totals) + 1)
    tcols[0].markdown("**ИТОГО**")
    for i, (country, val) in enumerate(totals.items(), start=1):
        tcols[i].metric(country, f"{val}")

    st.download_button(
        "⬇️ Скачать полную матрицу CSV",
        table_view.to_csv(index=False).encode("utf-8-sig"),
        file_name="stock_by_country_full.csv",
        mime="text/csv",
    )

# ---------- Таблица ----------
with tab_table:
    view_mode = st.radio(
        "Вид таблицы",
        ["По товару (сумма по странам)", "По товару и стране (детально)"],
        horizontal=True,
    )

    if view_mode == "По товару (сумма по странам)":
        tbl = (f.groupby(["sku", "asin", "product_name", "category"], as_index=False)
                 .agg(quantity=("quantity", "sum"),
                      countries=("location", "nunique")))
        tbl["amazon_url"] = "https://www.amazon.es/dp/" + tbl["asin"].astype(str)
        tbl = tbl.sort_values("quantity", ascending=False)
        st.dataframe(
            tbl[["sku", "product_name", "quantity", "countries",
                 "category", "amazon_url"]],
            use_container_width=True, height=560, hide_index=True,
            column_config={
                "quantity": st.column_config.ProgressColumn(
                    "Остаток (всего)", format="%d",
                    min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                ),
                "countries": st.column_config.NumberColumn(
                    "Стран", width="small",
                    help="В скольких странах FBA лежит товар"),
                "product_name": st.column_config.TextColumn("Товар", width="large"),
                "amazon_url": st.column_config.LinkColumn(
                    "Листинг", display_text="Открыть ↗"),
                "category": st.column_config.TextColumn("Категория"),
            },
        )
    else:
        tbl = f.sort_values(["sku", "quantity"], ascending=[True, False]).copy()
        tbl["amazon_url"] = "https://www.amazon.es/dp/" + tbl["asin"].astype(str)
        st.dataframe(
            tbl[["sku", "product_name", "location", "quantity",
                 "availability_status", "category", "amazon_url", "snapshot_date"]],
            use_container_width=True, height=560, hide_index=True,
            column_config={
                "quantity": st.column_config.ProgressColumn(
                    "Остаток", format="%d",
                    min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                ),
                "location": st.column_config.TextColumn("Страна", width="small"),
                "product_name": st.column_config.TextColumn("Товар", width="large"),
                "amazon_url": st.column_config.LinkColumn(
                    "Листинг", display_text="Открыть ↗"),
                "availability_status": st.column_config.TextColumn("Статус"),
                "category": st.column_config.TextColumn("Категория"),
                "snapshot_date": st.column_config.TextColumn("Снапшот", width="small"),
            },
        )

    st.download_button(
        "⬇️ Скачать CSV (детально, по странам)",
        f.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"stock_{f['snapshot_date'].max()}.csv",
        mime="text/csv",
    )
