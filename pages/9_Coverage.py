# pages/9_Coverage.py — Покрытие: сколько недель хватит товара и где будет дефицит
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.8rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("cov.title"))
st.caption(t("cov.caption"))

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"
AMBER = "#f2b134"
GREY = "#9aa4b2"
PLOTLY_CFG = {"displayModeBar": False}

ST_COLOR = {"critical": ACCENT, "warning": AMBER, "ok": GREEN}


# ═══════════════════════════════════════════════════════════════════
# ДАННЫЕ
# ═══════════════════════════════════════════════════════════════════

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
def load_summary() -> pd.DataFrame:
    """Свод покрытия на последнюю дату расчёта."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT s.*,
                   COALESCE(l.product_name, '—') AS product_name
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
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_calc_date():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(calc_date) FROM kabinet_data.coverage_summary")
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def weeks_label(w) -> str:
    if w is None or pd.isna(w):
        return "—"
    w = int(w)
    return "26+" if w >= 26 else str(w)


# ═══════════════════════════════════════════════════════════════════
# ПРОВЕРКИ
# ═══════════════════════════════════════════════════════════════════

if not table_exists("coverage_summary"):
    st.info(t("cov.no_table"))
    st.stop()

df = load_summary()
if df.empty:
    st.info(t("cov.empty"))
    st.stop()

calc_date = load_calc_date()
if calc_date:
    st.caption(t("cov.as_of").format(
        d=pd.to_datetime(calc_date).strftime("%d.%m.%Y")))

for c in ("available_now", "coverage_weeks", "fbm_fallback_qty",
          "total_coverage_weeks", "realistic_coverage_weeks",
          "pool_exhaustion_weeks", "competing_marketplaces",
          "pool_total_weekly_demand", "gap_weeks", "gap_qty"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

df["coverage_status"] = df["coverage_status"].fillna("ok")

# ---------- как читать ----------
st.markdown(f"""
<div style="border:1px solid rgba(128,128,128,0.22); border-left:3px solid {BLUE};
            border-radius:10px; padding:12px 18px; margin:10px 0 16px 0;
            background:rgba(31,119,180,0.045);">
  <div style="font-size:0.72rem; font-weight:700; letter-spacing:.06em;
              text-transform:uppercase; color:{BLUE}; margin-bottom:4px;">
    {t("cov.intro.title")}</div>
  <div style="font-size:0.93rem; line-height:1.55;">{t("cov.intro.body")}</div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# ФИЛЬТРЫ
# ═══════════════════════════════════════════════════════════════════

f1, f2, f3 = st.columns([1.2, 1.4, 2])
with f1:
    mps = sorted(df["marketplace"].dropna().unique().tolist())
    mp_filter = st.multiselect(t("cov.filter.marketplace"), mps, default=mps)
with f2:
    ST_LABEL = {"critical": t("cov.st.critical"),
                "warning": t("cov.st.warning"), "ok": t("cov.st.ok")}
    st_options = list(ST_LABEL.values())
    st_filter = st.multiselect(t("cov.filter.status"), st_options,
                               default=[ST_LABEL["critical"], ST_LABEL["warning"]])
with f3:
    search = st.text_input(t("cov.filter.search"), placeholder=t("cov.filter.search_ph"))

f = df[df["marketplace"].isin(mp_filter)].copy()
if st_filter:
    keys = [k for k, v in ST_LABEL.items() if v in st_filter]
    f = f[f["coverage_status"].isin(keys)]
if search:
    m = (f["sku"].str.contains(search, case=False, na=False)
         | f["product_name"].str.contains(search, case=False, na=False))
    f = f[m]

# ═══════════════════════════════════════════════════════════════════
# KPI
# ═══════════════════════════════════════════════════════════════════

base = df[df["marketplace"].isin(mp_filter)]
n_crit = int((base["coverage_status"] == "critical").sum())
n_warn = int((base["coverage_status"] == "warning").sum())
n_13 = int((base["realistic_coverage_weeks"] < 13).sum())
n_switch = int(base["channel_switch_week"].notna().sum())
n_pool = int((base["pool_exhaustion_weeks"] < base["total_coverage_weeks"]).sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("cov.kpi.critical"), f"{n_crit:,}", help=t("cov.kpi.critical_help"))
k2.metric(t("cov.kpi.warning"), f"{n_warn:,}", help=t("cov.kpi.warning_help"))
k3.metric(t("cov.kpi.deficit_13"), f"{n_13:,}", help=t("cov.kpi.deficit_13_help"))
k4.metric(t("cov.kpi.switch"), f"{n_switch:,}", help=t("cov.kpi.switch_help"))
k5.metric(t("cov.kpi.pool_risk"), f"{n_pool:,}", help=t("cov.kpi.pool_risk_help"))

st.divider()

tab_list, tab_detail, tab_dist = st.tabs(
    [t("cov.tab.list"), t("cov.tab.detail"), t("cov.tab.distribution")]
)


# ═══════════════════════════════════════════════════════════════════
# СПИСОК ТОВАРОВ
# ═══════════════════════════════════════════════════════════════════

with tab_list:
    if f.empty:
        st.info(t("common.no_data"))
    else:
        view = f.sort_values(["realistic_coverage_weeks", "sku"]).copy()
        view["status_label"] = view["coverage_status"].map(ST_LABEL)
        view["first_deficit_week"] = pd.to_datetime(
            view["first_deficit_week"], errors="coerce").dt.strftime("%d.%m.%Y")
        view["channel_switch_week"] = pd.to_datetime(
            view["channel_switch_week"], errors="coerce").dt.strftime("%d.%m.%Y")
        view["pool_warn"] = (view["pool_exhaustion_weeks"]
                             < view["total_coverage_weeks"])
        # вместо второй колонки с неделями — понятная пометка «делят N стран»
        view["shared_note"] = np.where(
            view["pool_warn"] & (view["competing_marketplaces"] > 1),
            view["competing_marketplaces"].fillna(0).astype(int).astype(str)
            + " " + t("cov.col.shared_suffix"),
            "—")

        st.dataframe(
            view[["sku", "product_name", "marketplace", "available_now",
                  "coverage_weeks", "fbm_fallback_qty", "total_coverage_weeks",
                  "shared_note", "realistic_coverage_weeks",
                  "first_deficit_week", "status_label"]],
            use_container_width=True, height=560, hide_index=True,
            column_config={
                "sku": st.column_config.TextColumn("SKU", width="small"),
                "product_name": st.column_config.TextColumn(
                    t("cov.col.product"), width="medium"),
                "marketplace": st.column_config.TextColumn(
                    t("cov.col.marketplace"), width="small"),
                "available_now": st.column_config.NumberColumn(
                    t("cov.col.stock"), width="small",
                    help=t("cov.col.stock_help")),
                "coverage_weeks": st.column_config.NumberColumn(
                    t("cov.col.weeks_fba"), width="small",
                    help=t("cov.col.weeks_fba_help")),
                "fbm_fallback_qty": st.column_config.NumberColumn(
                    t("cov.col.madrid"), width="small",
                    help=t("cov.col.madrid_help")),
                "total_coverage_weeks": st.column_config.NumberColumn(
                    t("cov.col.weeks_total"), width="small",
                    help=t("cov.col.weeks_total_help")),
                "shared_note": st.column_config.TextColumn(
                    t("cov.col.shared"), width="small",
                    help=t("cov.col.shared_help")),
                "realistic_coverage_weeks": st.column_config.ProgressColumn(
                    t("cov.col.weeks_real"), format="%d",
                    min_value=0, max_value=26,
                    help=t("cov.col.weeks_real_help")),
                "first_deficit_week": st.column_config.TextColumn(
                    t("cov.col.first_deficit"), width="small"),
                "status_label": st.column_config.TextColumn(
                    t("cov.col.status"), width="small"),
            },
        )

        n_optimistic = int(view["pool_warn"].sum())
        if n_optimistic:
            st.warning(t("cov.list.pool_warn").format(n=n_optimistic))
        st.caption(t("cov.list.note"))

        b1, b2 = st.columns([1, 1])
        with b1:
            st.download_button(
                t("cov.download"),
                view.to_csv(index=False).encode("utf-8-sig"),
                file_name="coverage.csv", mime="text/csv",
                use_container_width=True)
        with b2:
            st.page_link("pages/4_Reorder.py", label=t("cov.go_reorder"),
                         icon=":material/shopping_cart:",
                         use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# ПОНЕДЕЛЬНАЯ ПРОЕКЦИЯ ПО ТОВАРУ
# ═══════════════════════════════════════════════════════════════════

with tab_detail:
    if f.empty:
        st.info(t("common.no_data"))
    else:
        opts = (f.sort_values(["realistic_coverage_weeks", "sku"])
                 .assign(label=lambda d: d["sku"] + " · " + d["marketplace"]
                         + " · " + d["product_name"].str.slice(0, 44)))
        pick = st.selectbox(t("cov.detail.pick"), opts["label"].tolist())
        row = opts[opts["label"] == pick].iloc[0]

        d1, d2, d3, d4 = st.columns(4)
        d1.metric(t("cov.col.stock"), f"{int(row['available_now'] or 0):,}")
        d2.metric(t("cov.col.weeks_fba"), weeks_label(row["coverage_weeks"]))
        d3.metric(t("cov.col.madrid"), f"{int(row['fbm_fallback_qty'] or 0):,}")
        d4.metric(t("cov.col.weeks_real"),
                  weeks_label(row["realistic_coverage_weeks"]))

        # предупреждение о конкуренции за общий мадридский запас
        pool_w = row.get("pool_exhaustion_weeks")
        total_w = row.get("total_coverage_weeks")
        if (pd.notna(pool_w) and pd.notna(total_w) and pool_w < total_w
                and int(row.get("competing_marketplaces") or 0) > 1):
            st.warning(t("cov.detail.pool_warn").format(
                n=int(row["competing_marketplaces"]),
                qty=int(row["fbm_fallback_qty"] or 0),
                demand=float(row["pool_total_weekly_demand"] or 0),
                pool_weeks=int(pool_w), promised=int(total_w)))

        proj = load_projection(row["sku"], row["marketplace"])
        if proj.empty:
            st.info(t("cov.detail.no_projection"))
        else:
            proj["week_start"] = pd.to_datetime(proj["week_start"])
            proj["label"] = proj["week_start"].dt.strftime("%d.%m")

            fig = make_subplots(specs=[[{"secondary_y": False}]])
            fig.add_trace(go.Bar(
                name=t("cov.proj.stock_begin"), x=proj["label"],
                y=proj["stock_begin"], marker_color=BLUE, opacity=0.55))
            fig.add_trace(go.Bar(
                name=t("cov.proj.incoming"), x=proj["label"],
                y=proj["incoming"], marker_color=GREEN))
            fig.add_trace(go.Scatter(
                name=t("cov.proj.forecast"), x=proj["label"], y=proj["forecast"],
                mode="lines+markers", line=dict(color=ACCENT, width=2)))
            fig.add_trace(go.Bar(
                name=t("cov.proj.unmet"), x=proj["label"],
                y=proj["unmet_demand"], marker_color=ACCENT, opacity=0.4))

            # общий мадридский запас кончится раньше, чем показывает расчёт
            # по этой стране — отмечаем неделю прямо на графике
            if (pd.notna(pool_w) and pd.notna(total_w) and pool_w < total_w
                    and int(row.get("competing_marketplaces") or 0) > 1):
                idx = int(pool_w)
                if 0 <= idx < len(proj):
                    fig.add_vline(
                        x=proj["label"].iloc[idx], line_dash="dash",
                        line_color=ACCENT, opacity=0.8,
                        annotation_text=t("cov.proj.pool_line"),
                        annotation_position="top")

            fig.update_layout(barmode="group", height=360,
                              margin=dict(l=10, r=10, t=30, b=10),
                              hovermode="x unified",
                              legend=dict(orientation="h", y=1.16))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

            tbl = proj.copy()
            tbl["week_start"] = tbl["week_start"].dt.strftime("%d.%m.%Y")
            tbl["covered"] = np.where(tbl["is_covered"],
                                      t("cov.proj.covered"), t("cov.proj.deficit"))
            st.dataframe(
                tbl[["week_num", "week_start", "stock_begin", "incoming",
                     "forecast", "stock_end", "unmet_demand", "covered"]],
                use_container_width=True, height=420, hide_index=True,
                column_config={
                    "week_num": st.column_config.NumberColumn(
                        t("cov.proj.week_num"), width="small"),
                    "week_start": st.column_config.TextColumn(
                        t("cov.proj.week_start"), width="small"),
                    "stock_begin": st.column_config.NumberColumn(
                        t("cov.proj.stock_begin"), format="%.0f"),
                    "incoming": st.column_config.NumberColumn(
                        t("cov.proj.incoming"), format="%.0f"),
                    "forecast": st.column_config.NumberColumn(
                        t("cov.proj.forecast"), format="%.1f"),
                    "stock_end": st.column_config.NumberColumn(
                        t("cov.proj.stock_end"), format="%.0f"),
                    "unmet_demand": st.column_config.NumberColumn(
                        t("cov.proj.unmet"), format="%.1f"),
                    "covered": st.column_config.TextColumn(
                        t("cov.proj.status"), width="small"),
                },
            )
            st.caption(t("cov.detail.note"))
            if (pd.notna(pool_w) and pd.notna(total_w) and pool_w < total_w
                    and int(row.get("competing_marketplaces") or 0) > 1):
                st.caption(t("cov.detail.chart_note"))


# ═══════════════════════════════════════════════════════════════════
# РАСПРЕДЕЛЕНИЕ
# ═══════════════════════════════════════════════════════════════════

with tab_dist:
    base_d = df[df["marketplace"].isin(mp_filter)].copy()
    if base_d.empty:
        st.info(t("common.no_data"))
    else:
        bins = [-0.1, 4, 13, 26, 999]
        labels = [t("cov.bucket.0_4"), t("cov.bucket.5_13"),
                  t("cov.bucket.14_26"), t("cov.bucket.26plus")]
        base_d["bucket"] = pd.cut(base_d["realistic_coverage_weeks"].fillna(0),
                                  bins=bins, labels=labels)

        by_b = (base_d.groupby("bucket", as_index=False, observed=False)
                      .size().rename(columns={"size": "cnt"}))
        fig = px.bar(by_b, x="bucket", y="cnt", text="cnt",
                     title=t("cov.dist.title"),
                     color="bucket",
                     color_discrete_sequence=[ACCENT, AMBER, BLUE, GREEN])
        fig.update_layout(height=340, showlegend=False,
                          xaxis_title=None, yaxis_title=t("cov.dist.pairs"),
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        by_mp = (base_d.groupby("marketplace", as_index=False)
                       .agg(pairs=("sku", "count"),
                            critical=("coverage_status",
                                      lambda s: int((s == "critical").sum())),
                            median_weeks=("realistic_coverage_weeks", "median")))
        by_mp["critical_pct"] = np.round(
            safe_div(by_mp["critical"], by_mp["pairs"]) * 100, 0)
        by_mp = by_mp.sort_values("critical", ascending=False)

        st.markdown(f"**{t('cov.dist.by_marketplace')}**")
        st.dataframe(
            by_mp[["marketplace", "pairs", "critical", "critical_pct",
                   "median_weeks"]],
            use_container_width=True, hide_index=True,
            column_config={
                "marketplace": st.column_config.TextColumn(t("cov.col.marketplace")),
                "pairs": st.column_config.NumberColumn(t("cov.dist.pairs")),
                "critical": st.column_config.NumberColumn(t("cov.st.critical")),
                "critical_pct": st.column_config.ProgressColumn(
                    t("cov.dist.critical_share"), format="%.0f%%",
                    min_value=0, max_value=100),
                "median_weeks": st.column_config.NumberColumn(
                    t("cov.dist.median_weeks"), format="%.0f"),
            },
        )
        st.caption(t("cov.dist.note"))
