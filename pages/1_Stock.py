# pages/1_Stock.py — Остатки: аналитический дашборд
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from db.connection import get_connection
from i18n import init_lang, t

init_lang()

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

st.title(t("stock.title"))
st.caption(t("stock.caption"))


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


def get_category_map():
    return {
        "amoladora": t("stock.cat.amoladora"),
        "martillo": t("stock.cat.martillo"),
        "taladro": t("stock.cat.taladro"),
        "destornillador": t("stock.cat.destornillador"),
        "motosierra": t("stock.cat.motosierra"),
        "sierra": t("stock.cat.sierra"),
        "soldador": t("stock.cat.soldador"),
        "compresor": t("stock.cat.compresor"),
        "bateria": t("stock.cat.bateria"),
        "cargador": t("stock.cat.bateria"),
    }


def detect_category(name: str) -> str:
    n = (name or "").lower()
    for key, cat in get_category_map().items():
        if key in n:
            return cat
    return t("stock.other")


# ---------- очистка SKU и фильтр дефектов/возвратов ----------
def clean_sku(sku: str) -> str:
    """Убирает -FBA суффикс для отображения."""
    return str(sku or "").replace("-FBA", "").strip()


def is_defect_sku(sku: str) -> bool:
    """Дефектные/возвратные SKU (Amazon removal/grade): amzn.gr.16873000-1-eyYX..."""
    return str(sku or "").lower().startswith("amzn.gr.")


df = load_stock()

if df.empty:
    st.warning(t("stock.no_data_warning"))
    st.stop()

df["category"] = df["product_name"].apply(detect_category)
df["power_w"] = df["product_name"].str.extract(r"(\d{3,4})\s*W", flags=re.I)[0].astype(float)

if "location" not in df.columns:
    df["location"] = None
df["location"] = df["location"].fillna("—")

# очищенный SKU для отображения + отделение дефектов
df["sku_display"] = df["sku"].apply(clean_sku)
df["is_defect"] = df["sku"].apply(is_defect_sku)

defects_df = df[df["is_defect"]].copy()      # дефекты/возвраты — отдельно
df = df[~df["is_defect"]].copy()             # основной сток — без дефектов

# ---------- физический остаток vs квота канала ----------
# availability_status='reserve' — это НЕ отдельный физический товар, а квота,
# выделенная на канал продаж из уже учтённого складского остатка
# (например, офферы Leroy Merlin — часть мадридского стока).
# Смешивать их с физическим остатком нельзя: получится двойной счёт.
RESERVE_STATUS = "reserve"
reserve_df = df[df["availability_status"] == RESERVE_STATUS].copy()
df = df[df["availability_status"] != RESERVE_STATUS].copy()

if df.empty:
    st.warning(t("stock.no_data_warning"))
    st.stop()

# ---------- фильтры ----------
c1, c2, c3, c4 = st.columns(4)
with c1:
    wh_filter = st.text_input(t("stock.filter.warehouse"))
with c2:
    sku_filter = st.text_input(t("stock.filter.sku"))
with c3:
    status_filter = st.selectbox(
        t("stock.filter.avail_status"),
        [t("stock.filter.all")] + sorted(df["availability_status"].dropna().unique().tolist()),
    )
with c4:
    country_filter = st.multiselect(
        t("stock.filter.country"),
        sorted(df["location"].unique().tolist()),
        placeholder=t("stock.filter.country_placeholder"),
    )

f = df.copy()
if wh_filter:
    f = f[f["warehouse_name"].str.contains(wh_filter, case=False, na=False)]
if sku_filter:
    f = f[f["sku_display"].str.contains(sku_filter, case=False, na=False)
          | f["sku"].str.contains(sku_filter, case=False, na=False)]
if status_filter != t("stock.filter.all"):
    f = f[f["availability_status"] == status_filter]
if country_filter:
    f = f[f["location"].isin(country_filter)]

# ---------- KPI ----------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("stock.kpi.total_sku"), f["sku"].nunique())
k2.metric(t("stock.kpi.countries"), f["location"].nunique(),
          help=t("stock.kpi.countries_help"))
k3.metric(t("stock.kpi.total_qty"), int(f["quantity"].sum()),
          help=t("stock.kpi.total_qty_help"))
k4.metric(t("stock.kpi.median"),
          int(f.groupby("sku")["quantity"].sum().median()) if len(f) else 0)
low_stock = (f.groupby("sku")["quantity"].sum() <= 3).sum()
k5.metric(t("stock.kpi.low_stock"), int(low_stock),
          delta=None, help=t("stock.kpi.low_stock_help"))

# ---------- квоты, выделенные на каналы продаж ----------
if not reserve_df.empty:
    with st.expander(t("stock.channels.title").format(
            n=int(reserve_df["quantity"].sum()))):
        st.caption(t("stock.channels.caption"))
        ch = (reserve_df.groupby("warehouse_name", as_index=False)
                        .agg(quantity=("quantity", "sum"), skus=("sku", "nunique")))
        ch_cols = st.columns(min(len(ch), 4) or 1)
        unit_ = t("stock.ov.unit_short")
        for i, (_, row) in enumerate(ch.iterrows()):
            with ch_cols[i % len(ch_cols)]:
                st.metric(row["warehouse_name"], f"{int(row['quantity'])} {unit_}",
                          help=t("stock.ctr.metric_help").format(n=int(row["skus"])))

        ch_tbl = (reserve_df.groupby(["warehouse_name", "sku_display", "product_name"],
                                     as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
        st.dataframe(
            ch_tbl, use_container_width=True, height=320, hide_index=True,
            column_config={
                "warehouse_name": st.column_config.TextColumn(
                    t("stock.channels.col_channel"), width="medium"),
                "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "quantity": st.column_config.NumberColumn(
                    t("stock.channels.col_qty"), width="small"),
            },
        )
        st.download_button(
            t("stock.channels.download"),
            ch_tbl.to_csv(index=False).encode("utf-8-sig"),
            file_name="stock_channel_quotas.csv", mime="text/csv",
        )

st.divider()

# ---------- 🔥 Минимальные остатки ----------
burn = (f.groupby(["sku_display", "asin", "product_name"], as_index=False)["quantity"].sum()
          .sort_values("quantity").head(5))

if not burn.empty and burn["quantity"].min() <= 3:
    st.markdown(f"#### {t('stock.burn_title')}")
    bcols = st.columns(len(burn))
    unit = t("stock.ov.unit_short")
    for col, (_, row) in zip(bcols, burn.iterrows()):
        by_country = (f[f["sku_display"] == row["sku_display"]]
                        .groupby("location")["quantity"].sum())
        by_country = by_country[by_country > 0].sort_values(ascending=False)
        country_str = " · ".join(f"{c}: {int(q)}" for c, q in by_country.items())
        with col:
            st.metric(
                label=str(row["sku_display"])[:18],
                value=f"{int(row['quantity'])} {unit}",
                help=f"{row['product_name'][:80]}",
            )
            st.caption(f"📍 {country_str}" if country_str else t("stock.burn_none"))
    st.divider()

tab_overview, tab_abc, tab_cat, tab_countries, tab_table = st.tabs(
    [t("stock.tab.overview"), t("stock.tab.abc"), t("stock.tab.categories"),
     t("stock.tab.countries"), t("stock.tab.table")]
)

BLUE = "#1f77b4"
ACCENT = "#e8484d"  # фирменный красный Dnipro-M

# ---------- Обзор ----------
with tab_overview:
    left, right = st.columns([3, 2])

    with left:
        top = (f.groupby(["sku_display", "product_name"], as_index=False)["quantity"]
                 .sum().nlargest(15, "quantity"))
        top["label"] = top["product_name"].str.slice(0, 45) + "…"
        fig = px.bar(
            top.sort_values("quantity"),
            x="quantity", y="label", orientation="h",
            text="quantity", title=t("stock.ov.top15_title"),
            color_discrete_sequence=[BLUE],
            hover_data={"sku_display": True, "label": False},
        )
        fig.update_layout(height=520, yaxis_title=None, xaxis_title=t("stock.ov.unit_short"),
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        by_status = f.groupby("availability_status", as_index=False)["quantity"].sum()
        fig = px.pie(by_status, names="availability_status", values="quantity",
                     hole=0.55, title=t("stock.ov.by_status_title"),
                     color_discrete_sequence=[BLUE, ACCENT, "#9aa4b2", "#f2b134"])
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        hist = px.histogram(
            f.groupby("sku", as_index=False)["quantity"].sum(),
            x="quantity", nbins=20,
            title=t("stock.ov.dist_title"),
            color_discrete_sequence=[BLUE],
        )
        hist.update_layout(height=250, xaxis_title=t("stock.ov.dist_xaxis"),
                           yaxis_title=t("stock.cat.sku_word"), margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(hist, use_container_width=True)

# ---------- ABC ----------
with tab_abc:
    abc = (f.groupby(["sku_display", "asin", "product_name"], as_index=False)["quantity"].sum()
             .sort_values("quantity", ascending=False)
             .reset_index(drop=True))
    total = abc["quantity"].sum()
    abc["cum_pct"] = abc["quantity"].cumsum() / total * 100
    abc["class"] = np.where(abc["cum_pct"] <= 80, "A",
                    np.where(abc["cum_pct"] <= 95, "B", "C"))

    a1, a2, a3 = st.columns(3)
    for col, cls in zip((a1, a2, a3), ("A", "B", "C")):
        sub = abc[abc["class"] == cls]
        col.metric(t("stock.abc.class_label").format(cls=cls),
                   t("stock.abc.sku_count").format(n=len(sub)),
                   t("stock.abc.pct_of_stock").format(pct=sub['quantity'].sum() / total * 100))

    fig = go.Figure()
    colors = abc["class"].map({"A": ACCENT, "B": "#f2b134", "C": "#9aa4b2"})
    fig.add_bar(x=abc.index, y=abc["quantity"], marker_color=colors,
                name=t("stock.abc.qty_legend"),
                customdata=abc[["sku_display", "product_name", "class"]],
                hovertemplate="<b>%{customdata[0]}</b> (" + t("stock.abc.class_word") + " %{customdata[2]})"
                              "<br>%{customdata[1]}<br>" + t("stock.abc.stock_word") + ": %{y}"
                              "<br><i>" + t("stock.abc.hover_click_hint") + "</i><extra></extra>")
    fig.add_scatter(x=abc.index, y=abc["cum_pct"], yaxis="y2",
                    name=t("stock.abc.cum_pct_legend"), line=dict(color=BLUE, width=2),
                    hoverinfo="skip")
    fig.add_hline(y=80, yref="y2", line_dash="dot", line_color="#666",
                  annotation_text="80%")
    fig.update_layout(
        title=t("stock.abc.pareto_title"),
        height=480,
        yaxis=dict(title=t("stock.ov.unit_short")),
        yaxis2=dict(title=t("stock.abc.yaxis_pct"), overlaying="y", side="right",
                    range=[0, 105]),
        xaxis=dict(title=t("stock.abc.xaxis"), showticklabels=False),
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
            by_country = (f[f["sku_display"] == row["sku_display"]]
                            .groupby("location", as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
            cc1, cc2, cc3, cc4 = st.columns([2.5, 1, 1, 1.2])
            cc1.markdown(f"**{row['product_name']}**")
            cc2.metric(t("stock.abc.total_stock"), f"{int(row['quantity'])} {t('stock.ov.unit_short')}")
            cc3.metric(t("stock.abc.class_word"), row["class"])
            cc4.link_button(t("stock.abc.open_amazon"),
                            f"https://www.amazon.es/dp/{row['asin']}",
                            use_container_width=True)
            if len(by_country) > 1:
                st.caption(f"{t('stock.abc.by_country_prefix')} " + " · ".join(
                    f"{r['location']}: {int(r['quantity'])}" for _, r in by_country.iterrows()
                ))
    else:
        st.caption(t("stock.abc.click_hint"))

    st.caption(t("stock.abc.footer_note"))

# ---------- Категории ----------
with tab_cat:
    by_cat = (f.groupby("category", as_index=False)
                .agg(quantity=("quantity", "sum"), skus=("sku", "nunique")))
    fig = px.treemap(by_cat, path=["category"], values="quantity",
                     title=t("stock.cat.treemap_title"),
                     color="quantity", color_continuous_scale="Blues",
                     custom_data=["skus"])
    fig.update_traces(hovertemplate="<b>%{label}</b><br>" + t("stock.abc.stock_word") + ": %{value} " + t("stock.ov.unit_short")
                                    + "<br>" + t("stock.cat.sku_word") + ": %{customdata[0]}<extra></extra>")
    fig.update_layout(height=450, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    pw = f.dropna(subset=["power_w"])
    if not pw.empty:
        fig = px.scatter(pw, x="power_w", y="quantity", color="category",
                         hover_data=["sku_display", "product_name"],
                         title=t("stock.cat.power_scatter_title"))
        fig.update_layout(height=400, xaxis_title=t("stock.cat.power_xaxis"),
                          yaxis_title=t("stock.cat.qty_yaxis"),
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ---------- По странам ----------
with tab_countries:
    st.markdown(f"##### {t('stock.ctr.by_country_title')}")
    by_country = (f.groupby("location", as_index=False)
                    .agg(quantity=("quantity", "sum"), skus=("sku", "nunique"))
                    .sort_values("quantity", ascending=False))

    cc = st.columns(min(len(by_country), 6) or 1)
    unit = t("stock.ov.unit_short")
    for i, (_, row) in enumerate(by_country.iterrows()):
        with cc[i % len(cc)]:
            st.metric(row["location"], f"{int(row['quantity'])} {unit}",
                     help=t("stock.ctr.metric_help").format(n=int(row['skus'])))

    fig = px.bar(by_country, x="location", y="quantity", text="quantity",
                 title=t("stock.ctr.bar_title"), color_discrete_sequence=[BLUE])
    fig.update_layout(height=380, xaxis_title=t("stock.ctr.country_axis"), yaxis_title=t("stock.cat.qty_yaxis"),
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"##### {t('stock.ctr.matrix_title')}")
    top_skus_df = (f.groupby(["sku_display", "product_name"], as_index=False)["quantity"]
                     .sum().nlargest(20, "quantity"))
    top_skus = top_skus_df["sku_display"].tolist()
    name_map = dict(zip(top_skus_df["sku_display"], top_skus_df["product_name"]))
    matrix_src = f[f["sku_display"].isin(top_skus)]
    pivot = (matrix_src.pivot_table(index="sku_display", columns="location",
                                    values="quantity", aggfunc="sum", fill_value=0)
                        .reindex(top_skus))

    y_labels = [f"{sku} · {name_map.get(sku, '')[:28]}" for sku in pivot.index]

    fig = px.imshow(
        pivot.values,
        x=pivot.columns.tolist(),
        y=y_labels,
        color_continuous_scale="Blues",
        aspect="auto",
        labels=dict(x=t("stock.ctr.country_axis"), y="", color=t("stock.abc.stock_word")),
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>" + t("stock.ctr.country_axis") + ": %{x}<br>" + t("stock.abc.stock_word") + ": %{z} " + t("stock.ov.unit_short") + "<extra></extra>"
    )
    fig.update_layout(
        height=44 * len(pivot) + 100,
        margin=dict(l=10, r=10, t=20, b=10),
        coloraxis_showscale=False,
    )
    event = st.plotly_chart(fig, use_container_width=True,
                            on_select="rerun", key="stock_matrix")

    pts = event.selection.points if event and event.selection else []
    if pts:
        y_clicked = pts[0].get("y")
        sku_clicked = None
        for sku, lbl in zip(pivot.index, y_labels):
            if lbl == y_clicked:
                sku_clicked = sku
                break
        if sku_clicked:
            row_info = f[f["sku_display"] == sku_clicked].iloc[0]
            by_country = (f[f["sku_display"] == sku_clicked]
                            .groupby("location", as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
            total_qty = int(by_country["quantity"].sum())

            cc1, cc2, cc3 = st.columns([2.5, 1, 1.2])
            cc1.markdown(f"**{row_info['product_name']}**  \n`{sku_clicked}`")
            cc2.metric(t("stock.abc.total_stock"), f"{total_qty} {unit}")
            cc3.link_button(t("stock.abc.open_amazon"),
                            f"https://www.amazon.es/dp/{row_info['asin']}",
                            use_container_width=True)

            bc = st.columns(min(len(by_country), 6) or 1)
            for i, (_, r) in enumerate(by_country.iterrows()):
                with bc[i % len(bc)]:
                    st.metric(r["location"], f"{int(r['quantity'])} {unit}")
    else:
        st.caption(t("stock.ctr.click_hint"))

    st.caption(t("stock.ctr.map_note"))

    st.divider()

    # ---------- полная таблица по ВСЕМ SKU ----------
    st.markdown(f"##### {t('stock.ctr.full_table_title')}")

    full_pivot = (f.pivot_table(index="sku_display", columns="location",
                                values="quantity", aggfunc="sum", fill_value=0))
    total_col = t("stock.ctr.col_total")
    full_pivot[total_col] = full_pivot.sum(axis=1)
    full_pivot = full_pivot.sort_values(total_col, ascending=False)

    full_name_map = f.drop_duplicates("sku_display").set_index("sku_display")["product_name"]
    full_asin_map = f.drop_duplicates("sku_display").set_index("sku_display")["asin"]

    table_view = full_pivot.reset_index()
    table_view.insert(1, t("stock.ctr.col_product"), table_view["sku_display"].map(full_name_map))
    table_view.insert(2, "asin_url",
                      "https://www.amazon.es/dp/" + table_view["sku_display"].map(full_asin_map).astype(str))

    country_cols = [c for c in full_pivot.columns if c != total_col]
    st.dataframe(
        table_view, use_container_width=True, height=520, hide_index=True,
        column_config={
            "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
            t("stock.ctr.col_product"): st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
            "asin_url": st.column_config.LinkColumn(
                "ASIN", display_text=t("stock.tbl.col_listing_text"), width="small"),
            total_col: st.column_config.NumberColumn(total_col, width="small"),
            **{col: st.column_config.NumberColumn(col, width="small")
               for col in country_cols},
        },
    )

    # ---------- строка ИТОГО ----------
    totals = {c: int(full_pivot[c].sum()) for c in full_pivot.columns}
    tcols = st.columns(len(totals) + 1)
    tcols[0].markdown(f"**{t('stock.ctr.total_row')}**")
    for i, (country, val) in enumerate(totals.items(), start=1):
        tcols[i].metric(country, f"{val}")

    st.download_button(
        t("stock.ctr.download_matrix"),
        table_view.to_csv(index=False).encode("utf-8-sig"),
        file_name="stock_by_country_full.csv",
        mime="text/csv",
    )

    # ---------- дефекты / возвраты ----------
    if not defects_df.empty:
        st.divider()
        st.markdown(f"##### {t('stock.ctr.defects_title')}")
        st.caption(t("stock.ctr.defects_caption"))
        dfx = (defects_df.groupby(["sku", "product_name"], as_index=False)
                         .agg(quantity=("quantity", "sum"),
                              countries=("location", "nunique")))
        dfx = dfx.sort_values("quantity", ascending=False)
        st.dataframe(
            dfx, use_container_width=True, height=280, hide_index=True,
            column_config={
                "sku": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="medium"),
                "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "quantity": st.column_config.NumberColumn(t("stock.abc.stock_word"), width="small"),
                "countries": st.column_config.NumberColumn(t("stock.tbl.col_countries"), width="small"),
            },
        )
        st.download_button(
            t("stock.ctr.defects_download"),
            defects_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="stock_defects.csv", mime="text/csv",
        )

# ---------- Таблица ----------
with tab_table:
    view_by_product = t("stock.tbl.view_by_product")
    view_by_product_country = t("stock.tbl.view_by_product_country")
    view_mode = st.radio(
        t("stock.tbl.view_mode"),
        [view_by_product, view_by_product_country],
        horizontal=True,
    )

    if view_mode == view_by_product:
        tbl = (f.groupby(["sku_display", "asin", "product_name", "category"], as_index=False)
                 .agg(quantity=("quantity", "sum"),
                      countries=("location", "nunique")))
        tbl["amazon_url"] = "https://www.amazon.es/dp/" + tbl["asin"].astype(str)
        tbl = tbl.sort_values("quantity", ascending=False)
        st.dataframe(
            tbl[["sku_display", "product_name", "quantity", "countries",
                 "category", "amazon_url"]],
            use_container_width=True, height=560, hide_index=True,
            column_config={
                "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                "quantity": st.column_config.ProgressColumn(
                    t("stock.tbl.col_total_stock"), format="%d",
                    min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                ),
                "countries": st.column_config.NumberColumn(
                    t("stock.tbl.col_countries"), width="small",
                    help=t("stock.tbl.col_countries_help")),
                "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "amazon_url": st.column_config.LinkColumn(
                    t("stock.tbl.col_listing"), display_text=t("stock.tbl.col_listing_text")),
                "category": st.column_config.TextColumn(t("stock.tbl.col_category")),
            },
        )
    else:
        tbl = f.sort_values(["sku_display", "quantity"], ascending=[True, False]).copy()
        tbl["amazon_url"] = "https://www.amazon.es/dp/" + tbl["asin"].astype(str)
        st.dataframe(
            tbl[["sku_display", "product_name", "location", "quantity",
                 "availability_status", "category", "amazon_url", "snapshot_date"]],
            use_container_width=True, height=560, hide_index=True,
            column_config={
                "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                "quantity": st.column_config.ProgressColumn(
                    t("stock.tbl.col_stock"), format="%d",
                    min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                ),
                "location": st.column_config.TextColumn(t("stock.tbl.col_country"), width="small"),
                "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "amazon_url": st.column_config.LinkColumn(
                    t("stock.tbl.col_listing"), display_text=t("stock.tbl.col_listing_text")),
                "availability_status": st.column_config.TextColumn(t("stock.tbl.col_status")),
                "category": st.column_config.TextColumn(t("stock.tbl.col_category")),
                "snapshot_date": st.column_config.TextColumn(t("stock.tbl.col_snapshot"), width="small"),
            },
        )

    st.download_button(
        t("stock.tbl.download_detail"),
        f.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"stock_{f['snapshot_date'].max()}.csv",
        mime="text/csv",
    ) 
