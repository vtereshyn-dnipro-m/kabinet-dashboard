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
    padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-size: 1.7rem; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; }
h1 { margin-bottom: 0.1rem; font-size: 2rem; }
[data-testid="stCaptionContainer"] { margin-top: -0.3rem; }
hr { margin: 0.6rem 0 !important; }
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


@st.cache_data(ttl=600)
def table_exists(name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'kabinet_data' AND table_name = %s
        """, (name,))
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_coverage() -> pd.DataFrame:
    """Свод покрытия на последнюю дату расчёта."""
    if not table_exists("coverage_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT s.*, l.product_name AS fallback_name
            FROM kabinet_data.coverage_summary s
            LEFT JOIN (
                SELECT SUBSTRING(sku FROM '([0-9]{5,})') AS base_sku,
                       MAX(product_name) AS product_name
                FROM kabinet_data.stock_local
                WHERE product_name IS NOT NULL
                GROUP BY 1
            ) l ON l.base_sku = s.sku
            WHERE s.calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_summary)
        """, conn)
        # имя приходит из расчёта, но у части позиций его нет —
        # подстраховываемся остатками, иначе в списке выбора будут прочерки
        if "product_name" not in df.columns:
            df["product_name"] = None
        df["product_name"] = (df["product_name"]
                              .fillna(df.get("fallback_name"))
                              .fillna("—").replace({"None": "—", "": "—"}))
        return df.drop(columns=["fallback_name"], errors="ignore")
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_projection(sku: str, marketplace: str) -> pd.DataFrame:
    """Понедельная проекция по одному товару."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT week_start, week_num, stock_begin, incoming,
                   forecast, stock_end, unmet_demand, is_covered
            FROM kabinet_data.coverage_projection
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_projection)
              AND sku = %(sku)s AND marketplace = %(mp)s
            ORDER BY week_num
        """, conn, params={"sku": sku, "mp": marketplace})
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


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
_status_norm = df["availability_status"].astype(str).str.strip().str.lower()
reserve_df = df[_status_norm == RESERVE_STATUS].copy()
df = df[_status_norm != RESERVE_STATUS].copy()

# страховка: если физических строк не осталось (например, в снапшот попали
# только квоты каналов) — показываем то, что есть, но честно предупреждаем
if df.empty and not reserve_df.empty:
    st.info(t("stock.only_channels"))
    df = reserve_df.copy()
    reserve_df = reserve_df.iloc[0:0]

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

# Обзор, ABC, По странам и Таблица скрыты до доработки: показывать
# полупустые вкладки хуже, чем не показывать их вовсе
SHOW_DRAFT_TABS = False

if SHOW_DRAFT_TABS:
    (tab_cov, tab_cat, tab_overview,
     tab_abc, tab_countries, tab_table) = st.tabs(
        [t("stock.tab.coverage"), t("stock.tab.categories"),
         t("stock.tab.overview"), t("stock.tab.abc"),
         t("stock.tab.countries"), t("stock.tab.table")])
else:
    tab_cov, tab_cat = st.tabs(
        [t("stock.tab.coverage"), t("stock.tab.categories")])
    tab_overview = tab_abc = tab_countries = tab_table = None

BLUE = "#1f77b4"
ACCENT = "#e8484d"  # фирменный красный Dnipro-M

if SHOW_DRAFT_TABS:
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

# ---------- Покрытие: на сколько недель хватит ----------
with tab_cov:
    cov = load_coverage()
    if cov.empty:
        st.info(t("stock.cov.no_data"))
    else:
        for c in ("available_now", "coverage_weeks", "fbm_fallback_qty",
                  "total_coverage_weeks", "realistic_coverage_weeks",
                  "pool_exhaustion_weeks", "competing_marketplaces",
                  "pool_total_weekly_demand", "gaps_count", "gaps_total_qty",
                  "overstock_qty", "overstock_weeks", "odoo_incoming_qty",
                  "weeks_until_first_gap"):
            if c in cov.columns:
                cov[c] = pd.to_numeric(cov[c], errors="coerce")
        cov["coverage_status"] = cov["coverage_status"].fillna("ok")

        calc_d = pd.to_datetime(cov["calc_date"].iloc[0]).strftime("%d.%m.%Y")
        hc1, hc2 = st.columns([3, 1])
        hc1.markdown(f"##### {t('stock.cov.header').format(d=calc_d)}")
        with hc2.popover(t("stock.cov.how"), use_container_width=True):
            st.markdown(t("stock.cov.intro"))
            st.markdown("---")
            st.markdown(t("stock.cov.horizon_note"))

        CST = {"critical": t("stock.cov.st_critical"),
               "warning": t("stock.cov.st_warning"),
               "ok": t("stock.cov.st_ok")}

        cf1, cf2 = st.columns([1.3, 2])
        with cf1:
            cov_mps = sorted(cov["marketplace"].dropna().unique().tolist())
            cov_mp = st.multiselect(t("stock.cov.filter_mp"), cov_mps,
                                    default=cov_mps, key="cov_mp")
        with cf2:
            cov_st = st.multiselect(
                t("stock.cov.filter_status"), list(CST.values()),
                default=[CST["critical"], CST["warning"]], key="cov_st")

        cv = cov[cov["marketplace"].isin(cov_mp)].copy()

        n_crit = int((cv["coverage_status"] == "critical").sum())
        n_warn = int((cv["coverage_status"] == "warning").sum())
        n_switch = int(cv["channel_switch_week"].notna().sum())
        n_pool = int((cv["pool_exhaustion_weeks"]
                      < cv["total_coverage_weeks"]).sum())
        n_over = int((cv["overstock_qty"].fillna(0) > 0).sum())
        n_multi = int((cv["gaps_count"].fillna(0) > 1).sum())

        # карточки работают как фильтр: нажал — таблица отфильтровалась
        if "cov_quick" not in st.session_state:
            st.session_state.cov_quick = None

        def _toggle(key: str):
            st.session_state.cov_quick = (
                None if st.session_state.cov_quick == key else key)

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric(t("stock.cov.kpi_critical"), f"{n_crit:,}",
                      help=t("stock.cov.kpi_critical_help"))
            st.button(t("stock.cov.show"), key="btn_crit",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "critical"
                            else "secondary"),
                      on_click=_toggle, args=("critical",))
        with m2:
            st.metric(t("stock.cov.kpi_warning"), f"{n_warn:,}",
                      help=t("stock.cov.kpi_warning_help"))
            st.button(t("stock.cov.show"), key="btn_warn",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "warning"
                            else "secondary"),
                      on_click=_toggle, args=("warning",))
        with m3:
            st.metric(t("stock.cov.kpi_switch"), f"{n_switch:,}",
                      help=t("stock.cov.kpi_switch_help"))
            st.button(t("stock.cov.show"), key="btn_switch",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "switch"
                            else "secondary"),
                      on_click=_toggle, args=("switch",))
        with m4:
            st.metric(t("stock.cov.kpi_pool"), f"{n_pool:,}",
                      help=t("stock.cov.kpi_pool_help"))
            st.button(t("stock.cov.show"), key="btn_pool",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "pool"
                            else "secondary"),
                      on_click=_toggle, args=("pool",))
        with m5:
            st.metric(t("stock.cov.kpi_overstock"), f"{n_over:,}",
                      help=t("stock.cov.kpi_overstock_help"))
            st.button(t("stock.cov.show"), key="btn_over",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "over"
                            else "secondary"),
                      on_click=_toggle, args=("over",))

        quick = st.session_state.cov_quick
        if quick == "critical":
            cv = cv[cv["coverage_status"] == "critical"]
        elif quick == "warning":
            cv = cv[cv["coverage_status"] == "warning"]
        elif quick == "switch":
            cv = cv[cv["channel_switch_week"].notna()]
        elif quick == "pool":
            cv = cv[cv["pool_exhaustion_weeks"] < cv["total_coverage_weeks"]]
        elif quick == "over":
            cv = cv[cv["overstock_qty"].fillna(0) > 0]
        elif cov_st:
            keys = [k for k, v in CST.items() if v in cov_st]
            cv = cv[cv["coverage_status"].isin(keys)]

        st.markdown("")
        if cv.empty:
            st.info(t("common.no_data"))
        else:
            cview = cv.sort_values(["realistic_coverage_weeks", "sku"]).copy()
            cview["status_label"] = cview["coverage_status"].map(CST)
            cview["first_deficit_week"] = pd.to_datetime(
                cview["first_deficit_week"], errors="coerce").dt.strftime("%d.%m.%Y")
            cview["shared_note"] = np.where(
                (cview["pool_exhaustion_weeks"] < cview["total_coverage_weeks"])
                & (cview["competing_marketplaces"] > 1),
                cview["competing_marketplaces"].fillna(0).astype(int).astype(str)
                + " " + t("stock.cov.col_shared_suffix"),
                "—")

            st.dataframe(
                cview[["sku", "product_name", "marketplace", "available_now",
                       "weeks_until_first_gap", "coverage_weeks",
                       "fbm_fallback_qty", "total_coverage_weeks",
                       "shared_note", "realistic_coverage_weeks",
                       "first_deficit_week", "gaps_count", "gaps_total_qty",
                       "odoo_incoming_qty", "overstock_qty", "status_label"]],
                use_container_width=True, height=460, hide_index=True,
                column_config={
                    "sku": st.column_config.TextColumn("SKU", width="small"),
                    "product_name": st.column_config.TextColumn(
                        t("stock.ctr.col_product"), width="medium"),
                    "marketplace": st.column_config.TextColumn(
                        t("stock.cov.col_mp"), width="small"),
                    "available_now": st.column_config.NumberColumn(
                        t("stock.cov.col_stock"), width="small"),
                    "weeks_until_first_gap": st.column_config.NumberColumn(
                        t("stock.cov.col_until_gap"), width="small",
                        help=t("stock.cov.col_until_gap_help")),
                    "coverage_weeks": st.column_config.NumberColumn(
                        t("stock.cov.col_weeks_fba"), width="small",
                        help=t("stock.cov.col_weeks_fba_help")),
                    "fbm_fallback_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_madrid"), width="small",
                        help=t("stock.cov.col_madrid_help")),
                    "total_coverage_weeks": st.column_config.NumberColumn(
                        t("stock.cov.col_weeks_total"), width="small",
                        help=t("stock.cov.col_weeks_total_help")),
                    "shared_note": st.column_config.TextColumn(
                        t("stock.cov.col_shared"), width="small",
                        help=t("stock.cov.col_shared_help")),
                    "realistic_coverage_weeks": st.column_config.ProgressColumn(
                        t("stock.cov.col_weeks_real"), format="%d",
                        min_value=0, max_value=26,
                        help=t("stock.cov.col_weeks_real_help")),
                    "first_deficit_week": st.column_config.TextColumn(
                        t("stock.cov.col_first_deficit"), width="small"),
                    "gaps_count": st.column_config.NumberColumn(
                        t("stock.cov.col_gaps"), width="small",
                        help=t("stock.cov.col_gaps_help")),
                    "gaps_total_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_gaps_qty"), format="%.0f", width="small",
                        help=t("stock.cov.col_gaps_qty_help")),
                    "odoo_incoming_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_odoo"), format="%.0f", width="small",
                        help=t("stock.cov.col_odoo_help")),
                    "overstock_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_overstock"), format="%.0f", width="small",
                        help=t("stock.cov.col_overstock_help")),
                    "status_label": st.column_config.TextColumn(
                        t("stock.cov.col_status"), width="small"),
                },
            )
            st.caption(t("stock.cov.note"))

            # ---- проекция по неделям для выбранного товара ----
            st.divider()
            st.markdown(f"##### {t('stock.cov.weekly_title')}")
            opts = (cv.sort_values(["realistic_coverage_weeks", "sku"])
                      .assign(label=lambda d: d["sku"] + " · " + d["marketplace"]
                              + " · " + d["product_name"].str.slice(0, 40)))
            pick = st.selectbox(t("stock.cov.pick"), opts["label"].tolist(),
                                key="cov_pick")
            prow = opts[opts["label"] == pick].iloc[0]

            pw_ = prow.get("pool_exhaustion_weeks")
            tw_ = prow.get("total_coverage_weeks")
            shared = (pd.notna(pw_) and pd.notna(tw_) and pw_ < tw_
                      and int(prow.get("competing_marketplaces") or 0) > 1)
            if shared:
                st.warning(t("stock.cov.pool_warn").format(
                    n=int(prow["competing_marketplaces"]),
                    qty=int(prow["fbm_fallback_qty"] or 0),
                    demand=float(prow["pool_total_weekly_demand"] or 0),
                    pool_weeks=int(pw_), promised=int(tw_)))

            # разрывы: где именно товар кончается и на сколько
            gaps = prow.get("gaps_detail")
            if isinstance(gaps, str):
                import json
                try:
                    gaps = json.loads(gaps)
                except Exception:
                    gaps = None
            if gaps:
                gl_, gr_ = st.columns([1, 1])
                gl_.metric(t("stock.cov.gaps_found"), f"{len(gaps)}")
                gr_.metric(t("stock.cov.gaps_qty"),
                           f"{float(prow.get('gaps_total_qty') or 0):,.0f}",
                           help=t("stock.cov.gaps_qty_help"))
                gdf = pd.DataFrame(gaps)
                gdf["start"] = pd.to_datetime(gdf["start"]).dt.strftime("%d.%m.%Y")
                gdf["end"] = pd.to_datetime(gdf["end"]).dt.strftime("%d.%m.%Y")
                st.dataframe(
                    gdf[["start", "end", "qty"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "start": st.column_config.TextColumn(
                            t("stock.cov.gap_from"), width="small"),
                        "end": st.column_config.TextColumn(
                            t("stock.cov.gap_to"), width="small"),
                        "qty": st.column_config.NumberColumn(
                            t("stock.cov.gap_qty"), format="%.0f"),
                    },
                )

            odoo_q = float(prow.get("odoo_incoming_qty") or 0)
            if odoo_q > 0:
                st.caption(t("stock.cov.odoo_note").format(qty=int(odoo_q)))

            over_q = float(prow.get("overstock_qty") or 0)
            if over_q > 0:
                st.info(t("stock.cov.overstock_note").format(
                    qty=int(over_q),
                    weeks=int(float(prow.get("overstock_weeks") or 0))))

            proj = load_projection(prow["sku"], prow["marketplace"])
            if proj.empty:
                st.info(t("stock.cov.no_projection"))
            else:
                proj["week_start"] = pd.to_datetime(proj["week_start"])
                proj["label"] = (proj["week_num"].astype(str) + ". "
                                 + proj["week_start"].dt.strftime("%d.%m"))

                pfig = go.Figure()
                pfig.add_bar(name=t("stock.cov.p_begin"), x=proj["label"],
                             y=proj["stock_begin"], marker_color=BLUE, opacity=0.55)
                pfig.add_bar(name=t("stock.cov.p_incoming"), x=proj["label"],
                             y=proj["incoming"], marker_color="#2e9e5b")
                pfig.add_scatter(name=t("stock.cov.p_forecast"), x=proj["label"],
                                 y=proj["forecast"], mode="lines+markers",
                                 line=dict(color=ACCENT, width=2))
                pfig.add_bar(name=t("stock.cov.p_unmet"), x=proj["label"],
                             y=proj["unmet_demand"], marker_color=ACCENT, opacity=0.4)

                if shared:
                    i = int(pw_)
                    if 0 <= i < len(proj):
                        pfig.add_shape(type="line", xref="x", yref="paper",
                                       x0=i, x1=i, y0=0, y1=1,
                                       line=dict(color=ACCENT, width=2, dash="dash"),
                                       opacity=0.8)
                        pfig.add_annotation(xref="x", yref="paper", x=i, y=1.02,
                                            text=t("stock.cov.p_pool_line"),
                                            showarrow=False, xanchor="left",
                                            font=dict(color=ACCENT, size=11))

                pfig.update_layout(
                    barmode="group", height=340,
                    margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                    legend=dict(orientation="h", y=1.16),
                    xaxis=dict(type="category", categoryorder="array",
                               categoryarray=proj["label"].tolist()))
                st.plotly_chart(pfig, use_container_width=True,
                                config={"displayModeBar": False})

                ptbl = proj.copy()
                ptbl["week_start"] = ptbl["week_start"].dt.strftime("%d.%m.%Y")
                ptbl["covered"] = np.where(ptbl["is_covered"],
                                           t("stock.cov.p_covered"),
                                           t("stock.cov.p_deficit"))
                st.dataframe(
                    ptbl[["week_num", "week_start", "stock_begin", "incoming",
                          "forecast", "stock_end", "unmet_demand", "covered"]],
                    use_container_width=True, height=360, hide_index=True,
                    column_config={
                        "week_num": st.column_config.NumberColumn(
                            t("stock.cov.p_week"), width="small"),
                        "week_start": st.column_config.TextColumn(
                            t("stock.cov.p_from"), width="small"),
                        "stock_begin": st.column_config.NumberColumn(
                            t("stock.cov.p_begin"), format="%.0f"),
                        "incoming": st.column_config.NumberColumn(
                            t("stock.cov.p_incoming"), format="%.0f"),
                        "forecast": st.column_config.NumberColumn(
                            t("stock.cov.p_forecast"), format="%.1f"),
                        "stock_end": st.column_config.NumberColumn(
                            t("stock.cov.p_end"), format="%.0f"),
                        "unmet_demand": st.column_config.NumberColumn(
                            t("stock.cov.p_unmet"), format="%.1f"),
                        "covered": st.column_config.TextColumn(
                            t("stock.cov.p_result"), width="small"),
                    },
                )
                st.caption(t("stock.cov.weekly_note"))

            cd1, cd2 = st.columns([1, 1])
            with cd1:
                st.download_button(
                    t("stock.cov.download"),
                    cview.to_csv(index=False).encode("utf-8-sig"),
                    file_name="coverage.csv", mime="text/csv",
                    use_container_width=True)
            with cd2:
                st.page_link("pages/4_Reorder.py", label=t("stock.cov.go_reorder"),
                             icon=":material/shopping_cart:",
                             use_container_width=True)


if SHOW_DRAFT_TABS:
    # ---------- ABC ----------
    with tab_abc:
        # группируем только по SKU: если добавить asin в ключ, строки с пустым
        # asin молча выпадут — pandas отбрасывает записи с NaN в группировке
        abc = (f.groupby("sku_display", as_index=False)
                 .agg(quantity=("quantity", "sum"),
                      asin=("asin", "first"),
                      product_name=("product_name", "first"))
                 .sort_values("quantity", ascending=False)
                 .reset_index(drop=True))

        if abc.empty or abc["quantity"].sum() <= 0:
            st.info(t("stock.abc.no_data"))
            st.stop()

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
                if pd.notna(row["asin"]) and str(row["asin"]) not in ("None", ""):
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

if SHOW_DRAFT_TABS:
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

if SHOW_DRAFT_TABS:
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
            tbl = (f.groupby("sku_display", as_index=False)
                     .agg(quantity=("quantity", "sum"),
                          countries=("location", "nunique"),
                          asin=("asin", "first"),
                          product_name=("product_name", "first"),
                          category=("category", "first")))
            tbl["amazon_url"] = np.where(
                tbl["asin"].notna() & (tbl["asin"].astype(str) != "None"),
                "https://www.amazon.es/dp/" + tbl["asin"].astype(str), None)
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
