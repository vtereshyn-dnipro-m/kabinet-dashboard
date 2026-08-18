# pages/5_Money.py — Деньги: полная P&L (Contribution Margin)
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.9rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("money.title"))
st.caption(t("money.caption"))


def clean_sku(sku: str) -> str:
    s = str(sku or "").strip()
    s = re.sub(r"^amzn\.gr\.", "", s)
    s = s.replace("-FBA", "").replace("-FBM", "")
    s = re.sub(r"-[A-Za-z0-9]{8,}$", "", s)
    s = re.sub(r"-[A-Za-z]$", "", s)
    return s.strip(" -")


# домены Amazon по коду маркетплейса — ссылка на листинг строится по стране,
# а не всегда на amazon.es. Каналы вне Amazon (LM и т.п.) ссылки не получают.
AMAZON_DOMAIN = {
    "ES": "amazon.es", "DE": "amazon.de", "FR": "amazon.fr", "IT": "amazon.it",
    "NL": "amazon.nl", "BE": "amazon.com.be", "SE": "amazon.se", "PL": "amazon.pl",
    "IE": "amazon.ie", "UK": "amazon.co.uk", "GB": "amazon.co.uk",
}


def amazon_url(marketplace: str, asin) -> str | None:
    """Ссылка на листинг Amazon. Для не-Amazon каналов возвращает None."""
    dom = AMAZON_DOMAIN.get(str(marketplace or "").upper())
    if not dom or asin is None or str(asin) in ("None", "nan", ""):
        return None
    return f"https://www.{dom}/dp/{asin}"


WINDOW_DEFAULT = 30


@st.cache_data(ttl=600)
def load_pnl(days: int, d_from=None, d_to=None):
    conn = get_connection()
    if d_from and d_to:
        where = f"e.sales_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = f"""e.sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days} days'
                               FROM kabinet_data.economics_summary)"""
    df = pd.read_sql(f"""
        SELECT e.norm_sku, e.product_name, e.marketplace, e.sales_date,
               e.units_ordered      AS units,
               e.ordered_product_sales AS gross_revenue,
               e.net_product_sales  AS revenue,
               e.total_fees         AS fees,
               e.net_proceeds_total AS net_proceeds,
               COALESCE(e.cogs, 0)  AS cogs_unit,
               COALESCE(a.total_spend, 0) AS ads,
               s.asin
        FROM kabinet_data.economics_summary e
        LEFT JOIN (
            -- схлопываем рекламу до одной строки на ключ: иначе несколько
            -- кампаний по одному SKU размножат строку экономики,
            -- и выручка посчитается дважды
            SELECT date, marketplace, norm_sku,
                   SUM(total_spend) AS total_spend
            FROM kabinet_data.ads_spend
            GROUP BY 1, 2, 3
        ) a
          ON a.date = e.sales_date
         AND a.marketplace = e.marketplace
         AND a.norm_sku = e.norm_sku
        LEFT JOIN (
            -- ASIN ищем по базовому коду товара: формы SKU расходятся
            -- (S2_78713000_, 41324000-A, 22539000-FBA_), и обрезка только
            -- по «-FBA» их не сводит — половина товаров оставалась без ссылки.
            -- Группировка снаружи UNION ALL: иначе SKU, известный и по
            -- остаткам, и по заказам, дал бы две строки и удвоил экономику
            SELECT base_sku, MAX(asin) AS asin
            FROM (
                SELECT SUBSTRING(sku FROM '([0-9]{{5,}})') AS base_sku, asin
                FROM kabinet_data.stock_local
                WHERE asin IS NOT NULL
                UNION ALL
                SELECT SUBSTRING(sku FROM '([0-9]{{5,}})') AS base_sku, asin
                FROM kabinet_data.orders_history
                WHERE asin IS NOT NULL
            ) u
            WHERE base_sku IS NOT NULL
            GROUP BY base_sku
        ) s ON s.base_sku = SUBSTRING(e.norm_sku FROM '([0-9]{{5,}})')
        WHERE {where}
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_ordered_sales(days: int, d_from=None, d_to=None):
    """Витринная выручка — то же число, что в Seller Central."""
    if d_from and d_to:
        where = f"snapshot_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = (f"snapshot_date >= (SELECT MAX(snapshot_date) - INTERVAL '{days} days' "
                 f"FROM kabinet_data.sales_traffic_daily)")
    conn = get_connection()
    try:
        r = pd.read_sql(f"""
            SELECT COALESCE(SUM(ordered_sales), 0) AS ordered_sales,
                   COALESCE(SUM(units_ordered), 0) AS units
            FROM kabinet_data.sales_traffic_daily
            WHERE {where}
        """, conn)
        return float(r["ordered_sales"].iloc[0])
    except Exception:
        return None
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_control_total(days: int, d_from=None, d_to=None):
    """Контрольная выручка прямо из таблицы, без соединений.
    Если основной запрос разойдётся с ней — значит строки размножились
    при JOIN, и цифры на странице завышены. Такое уже случалось."""
    if d_from and d_to:
        where = f"sales_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = (f"sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days} days' "
                 f"FROM kabinet_data.economics_summary)")
    conn = get_connection()
    try:
        r = pd.read_sql(f"""
            SELECT COALESCE(SUM(net_product_sales), 0) AS revenue,
                   COALESCE(SUM(units_ordered), 0)     AS units,
                   COUNT(*)                            AS rows
            FROM kabinet_data.economics_summary
            WHERE {where}
        """, conn)
        return r.iloc[0].to_dict()
    except Exception:
        return {}
    finally:
        conn.close()


# ---------- выбор периода ----------
pc1, pc2 = st.columns([2, 2])
with pc1:
    period = st.segmented_control(
        t("money.period.label"),
        options=["7", "30", "60", "90",
                 t("money.period.month"), t("money.period.custom")],
        default="30",
    )
with pc2:
    d_from = d_to = None
    if period == t("money.period.custom"):
        rng = st.date_input(t("money.period.range"), value=[], format="DD.MM.YYYY")
        if len(rng) == 2:
            d_from, d_to = rng[0], rng[1]

if period == t("money.period.month"):
    from datetime import date as _date
    _today = _date.today()
    d_from, d_to = _today.replace(day=1), _today
    WINDOW = (d_to - d_from).days + 1
    df = load_pnl(0, d_from, d_to)
elif period == t("money.period.custom"):
    if not (d_from and d_to):
        st.info(t("money.period.pick"))
        st.stop()
    WINDOW = (d_to - d_from).days + 1
    df = load_pnl(0, d_from, d_to)
else:
    WINDOW = int(period)
    df = load_pnl(WINDOW)

if df.empty:
    st.info(t("money.empty"))
    st.stop()

# подпись периода — как на Обзоре: показываем выбранный диапазон,
# а под ним предупреждаем, если данные за конец периода ещё не пришли
_dates = pd.to_datetime(df["sales_date"], errors="coerce")
_last = _dates.max()

if d_from and d_to:
    _ptitle = t("money.period_title").format(
        f=pd.Timestamp(d_from).strftime("%d.%m"),
        to=pd.Timestamp(d_to).strftime("%d.%m.%Y"))
else:
    _ptitle = t("money.period_days").format(d=WINDOW)
st.markdown(f"##### {_ptitle}")

if pd.notna(_last):
    _lag = (pd.Timestamp(pd.Timestamp.now().date()) - _last).days
    if _lag >= 2:
        st.caption(t("money.period_lag").format(
            d=_last.strftime("%d.%m"), n=_lag))

# сверяем с контрольной суммой: расхождение означает размножение строк
_ctrl = (load_control_total(0, d_from, d_to) if (d_from and d_to)
         else load_control_total(WINDOW))
if _ctrl and _ctrl.get("rows"):
    _mine = float(pd.to_numeric(df["revenue"], errors="coerce").fillna(0).sum())
    _real = float(_ctrl["revenue"])
    if _real > 0 and abs(_mine - _real) / _real > 0.01:
        st.error(t("money.mismatch").format(
            mine=_mine, real=_real,
            k=(_mine / _real if _real else 0),
            rows=int(len(df)), ctrl_rows=int(_ctrl["rows"])))

df["sku_display"] = df["norm_sku"].apply(clean_sku)
for c in ["units", "gross_revenue", "revenue", "fees", "net_proceeds", "cogs_unit", "ads"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
df["cogs_total"] = df["cogs_unit"] * df["units"]

# ---------- фильтры ----------
c1, c2 = st.columns([1, 2])
with c1:
    mp_filter = st.multiselect(
        t("money.filter.marketplace"),
        sorted(df["marketplace"].dropna().unique().tolist()),
        placeholder=t("money.filter.marketplace_ph"),
    )
with c2:
    search = st.text_input(t("money.filter.search"), placeholder=t("money.filter.search_ph"))

f = df.copy()
if mp_filter:
    f = f[f["marketplace"].isin(mp_filter)]
if search:
    f = f[f["sku_display"].str.contains(search, case=False, na=False)]

# ---------- KPI: полная воронка P&L ----------
tot_rev = f["revenue"].sum()
tot_net = f["net_proceeds"].sum()
tot_cogs = f["cogs_total"].sum()
tot_ads = f["ads"].sum()
cm = tot_net - tot_cogs - tot_ads
cm_pct = (cm / tot_rev * 100) if tot_rev > 0 else 0

_ordered = (load_ordered_sales(0, d_from, d_to) if (d_from and d_to)
            else load_ordered_sales(WINDOW))

k0, k1, k2, k3, k4, k5 = st.columns(6)
k0.metric(t("money.kpi.ordered"),
          f"{_ordered:,.0f} €" if _ordered else "—",
          help=t("money.kpi.ordered_help"))
k1.metric(t("money.kpi.revenue").format(d=WINDOW), f"{tot_rev:,.0f} €",
          help=t("money.kpi.revenue_help"))
k2.metric(t("money.kpi.net"), f"{tot_net:,.0f} €", help=t("money.kpi.net_help"))
k3.metric(t("money.kpi.cogs"), f"−{tot_cogs:,.0f} €", help=t("money.kpi.cogs_help"))
k4.metric(t("money.kpi.ads"), f"−{tot_ads:,.0f} €", help=t("money.kpi.ads_help"))
k5.metric(t("money.kpi.cm"), f"{cm:,.0f} €", delta=f"{cm_pct:.1f}%",
          help=t("money.kpi.cm_help"))

st.divider()

tab_pnl, tab_country, tab_fees, tab_alerts = st.tabs(
    [t("money.tab.pnl"), t("money.tab.by_marketplace"), t("money.tab.fees"),
     t("money.tab.alerts")]
)

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


# ---------- P&L по товарам ----------
with tab_pnl:
    by_sku = (f.groupby(["sku_display", "norm_sku"], as_index=False)
                .agg(product_name=("product_name", "first"),
                     asin=("asin", "first"),
                     marketplace=("marketplace", "first"),
                     units=("units", "sum"), revenue=("revenue", "sum"),
                     fees=("fees", "sum"), net_proceeds=("net_proceeds", "sum"),
                     cogs=("cogs_total", "sum"), ads=("ads", "sum")))
    by_sku["cm"] = by_sku["net_proceeds"] - by_sku["cogs"] - by_sku["ads"]
    by_sku["cm_pct"] = np.round(safe_div(by_sku["cm"], by_sku["revenue"]) * 100, 1)
    by_sku["acos_pct"] = np.round(safe_div(by_sku["ads"], by_sku["revenue"]) * 100, 1)
    by_sku["amazon_url"] = [
        amazon_url(mp, a) for mp, a in zip(by_sku["marketplace"], by_sku["asin"])
    ]

    def flag(row):
        if row["cm"] < 0:
            return "🔴"
        if row["cm_pct"] < 5:
            return "🟠"
        if row["cm_pct"] < 15:
            return "🟡"
        return "🟢"

    by_sku["flag_col"] = by_sku.apply(flag, axis=1)

    @st.cache_data(ttl=600)
    def load_annotations():
        conn = get_connection()
        try:
            adf = pd.read_sql("""
                SELECT sku, annotation_type, note
                FROM kabinet_data.pnl_annotations
            """, conn)
        except Exception:
            adf = pd.DataFrame(columns=["sku", "annotation_type", "note"])
        conn.close()
        return adf

    ann = load_annotations()
    ANN_ICON = {"vine": "🌿", "promo": "🏷️", "repricing": "💱", "issue": "⚠️"}
    if not ann.empty:
        ann["badge"] = ann["annotation_type"].map(lambda x: ANN_ICON.get(x, "📌"))
        ann_map = ann.groupby("sku").agg(
            badge=("badge", "first"), note=("note", " | ".join)).to_dict("index")
    else:
        ann_map = {}
    by_sku["ann_col"] = by_sku["norm_sku"].map(
        lambda s: ann_map.get(s, {}).get("badge", ""))
    by_sku["ann_note"] = by_sku["norm_sku"].map(
        lambda s: ann_map.get(s, {}).get("note", ""))

    by_sku = by_sku.sort_values("cm", ascending=False)

    # алерты: только РЕАЛЬНЫЕ проблемы (есть продажи и заметная выручка)
    MIN_REV_ALERT = 100   # € за период — ниже это хвост, не сигнал
    losers = by_sku[(by_sku["cm"] < 0) & (by_sku["units"] > 0)
                    & (by_sku["revenue"] >= MIN_REV_ALERT)]
    thin = by_sku[(by_sku["cm"] >= 0) & (by_sku["cm_pct"] < 5)
                  & (by_sku["revenue"] >= MIN_REV_ALERT * 5)]

    # предупреждения работают как фильтр: нажал — в таблице остались
    # только проблемные позиции, искать их глазами не нужно
    if "pnl_quick" not in st.session_state:
        st.session_state.pnl_quick = None

    def _pnl_toggle(key: str):
        st.session_state.pnl_quick = (
            None if st.session_state.pnl_quick == key else key)

    if not losers.empty or not thin.empty:
        al, ar = st.columns(2)
        if not losers.empty:
            with al:
                st.warning(t("money.alert.losers").format(
                    n=len(losers), skus=", ".join(losers["sku_display"].head(5))))
                st.button(
                    t("money.alert.show_losers").format(n=len(losers)),
                    key="btn_losers", use_container_width=True,
                    type=("primary" if st.session_state.pnl_quick == "losers"
                          else "secondary"),
                    on_click=_pnl_toggle, args=("losers",))
        if not thin.empty:
            with ar:
                st.warning(t("money.alert.thin").format(
                    n=len(thin), skus=", ".join(thin["sku_display"].head(5))))
                st.button(
                    t("money.alert.show_thin").format(n=len(thin)),
                    key="btn_thin", use_container_width=True,
                    type=("primary" if st.session_state.pnl_quick == "thin"
                          else "secondary"),
                    on_click=_pnl_toggle, args=("thin",))

    # ---------- Waterfall: как выручка превращается в прибыль ----------
    st.markdown(f"**{t('money.waterfall_title')}**")
    wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=[t("money.wf.revenue"), t("money.wf.fees"), t("money.wf.cogs"),
           t("money.wf.ads"), t("money.wf.cm")],
        y=[tot_rev, -(tot_rev - tot_net), -tot_cogs, -tot_ads, 0],
        text=[f"{tot_rev:,.0f}€", f"−{tot_rev - tot_net:,.0f}€",
              f"−{tot_cogs:,.0f}€", f"−{tot_ads:,.0f}€", f"{cm:,.0f}€"],
        textposition="outside",
        connector={"line": {"color": "#9aa4b2"}},
        decreasing={"marker": {"color": ACCENT}},
        increasing={"marker": {"color": GREEN}},
        totals={"marker": {"color": GREEN if cm >= 0 else ACCENT}},
    ))
    wf.update_layout(height=380, showlegend=False,
                     margin=dict(l=10, r=10, t=10, b=10),
                     yaxis_title="€")
    st.plotly_chart(wf, use_container_width=True)
    st.caption(t("money.waterfall_caption"))

    st.markdown(f"**{t('money.pnl_table')}**")

    _quick = st.session_state.pnl_quick
    if _quick == "losers":
        by_sku = by_sku[by_sku["sku_display"].isin(losers["sku_display"])]
        st.caption(t("money.alert.filtered_losers").format(n=len(by_sku)))
    elif _quick == "thin":
        by_sku = by_sku[by_sku["sku_display"].isin(thin["sku_display"])]
        st.caption(t("money.alert.filtered_thin").format(n=len(by_sku)))

    st.dataframe(
        by_sku[["flag_col", "ann_col", "sku_display", "product_name", "units", "revenue",
                "net_proceeds", "cogs", "ads", "cm", "cm_pct", "acos_pct",
                "amazon_url"]],
        use_container_width=True, height=480, hide_index=True,
        column_config={
            "flag_col": st.column_config.TextColumn(t("money.col.flag"), width="small",
                help=t("money.col.flag_help")),
            "ann_col": st.column_config.TextColumn(t("money.col.ann"), width="small",
                help=t("money.col.ann_help")),
            "sku_display": st.column_config.TextColumn("SKU", width="small"),
            "product_name": st.column_config.TextColumn(t("money.col.product"), width="medium"),
            "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €",
                help=t("money.col.net_help")),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €",
                help=t("money.col.cogs_help")),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €",
                help=t("money.col.cm_help")),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
            "acos_pct": st.column_config.NumberColumn("ACOS", format="%.1f%%",
                help=t("money.col.acos_help")),
            "amazon_url": st.column_config.LinkColumn(
                "ASIN", display_text=r"/dp/([A-Z0-9]{10})", width="small",
                help=t("money.col.asin_help")),
        },
    )
    st.caption(t("money.legend"))
    st.caption(t("money.pnl_note"))

    st.download_button(
        t("money.download"),
        by_sku.to_csv(index=False).encode("utf-8-sig"),
        file_name="pnl_by_sku.csv", mime="text/csv",
    )

# ---------- по маркетплейсам ----------
with tab_country:
    by_c = (f.groupby("marketplace", as_index=False)
              .agg(units=("units", "sum"), revenue=("revenue", "sum"),
                   net_proceeds=("net_proceeds", "sum"),
                   cogs=("cogs_total", "sum"), ads=("ads", "sum")))
    by_c["cm"] = by_c["net_proceeds"] - by_c["cogs"] - by_c["ads"]
    by_c["cm_pct"] = np.round(safe_div(by_c["cm"], by_c["revenue"]) * 100, 1)
    by_c = by_c.sort_values("cm", ascending=False)

    cc = st.columns(min(len(by_c), 5) or 1)
    for i, (_, r) in enumerate(by_c.iterrows()):
        with cc[i % len(cc)]:
            st.metric(r["marketplace"], f"{r['cm']:,.0f} €",
                     delta=f"{r['cm_pct']:.0f}%",
                     help=t("money.country_metric_help"))

    melt = by_c.melt(id_vars="marketplace",
                     value_vars=["cm", "cogs", "ads"],
                     var_name="part", value_name="eur")
    part_names = {"cm": t("money.col.cm"), "cogs": "COGS", "ads": t("money.col.ads")}
    melt["part"] = melt["part"].map(part_names)
    fig = px.bar(melt, x="marketplace", y="eur", color="part",
                 title=t("money.marketplace_chart"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT])
    fig.update_layout(height=380, xaxis_title=None, yaxis_title="€",
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_c[["marketplace", "units", "revenue", "net_proceeds", "cogs", "ads", "cm", "cm_pct"]],
        use_container_width=True, hide_index=True,
        column_config={
            "marketplace": st.column_config.TextColumn(t("money.col.marketplace")),
            "units": st.column_config.NumberColumn(t("money.col.units")),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €"),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €"),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €"),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
        },
    )

# ---------- комиссии/структура ----------
with tab_fees:
    st.markdown(f"**{t('money.struct_title')}**")
    total_rev = f["revenue"].sum()
    parts = pd.DataFrame({
        "part": [t("money.col.cm"), "COGS", t("money.col.ads"),
                 t("money.struct.fees")],
        "value": [max(cm, 0), tot_cogs, tot_ads, f["fees"].sum()],
    })
    fig = px.pie(parts, names="part", values="value", hole=0.5,
                 title=t("money.struct_pie_title"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT, "#f2b134"])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    fee_share = (f.groupby("marketplace", as_index=False)
                   .agg(revenue=("revenue", "sum"), fees=("fees", "sum")))
    fee_share["fees_pct"] = np.round(safe_div(fee_share["fees"], fee_share["revenue"]) * 100, 1)
    fig = px.bar(fee_share.sort_values("fees_pct", ascending=False),
                 x="marketplace", y="fees_pct", text="fees_pct",
                 title=t("money.fees_by_marketplace"), color_discrete_sequence=["#f2b134"])
    fig.update_traces(texttemplate="%{text:.0f}%")
    fig.update_layout(height=340, xaxis_title=None, yaxis_title=t("money.fees_axis"),
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(t("money.pnl_note"))

# ---------- рекламные алерты ----------
with tab_alerts:
    @st.cache_data(ttl=600)
    def load_ads_alerts():
        conn = get_connection()
        adf = pd.read_sql("""
            SELECT sku, alert_type, units, ads_spend, cm, details
            FROM kabinet_data.ads_alerts
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.ads_alerts)
            ORDER BY CASE alert_type
                WHEN 'zero_sales' THEN 0
                WHEN 'negative_cm' THEN 1
                ELSE 2 END,
                ads_spend DESC NULLS LAST
        """, conn)
        conn.close()
        return adf

    alerts = load_ads_alerts()
    if alerts.empty:
        st.success(t("money.alerts.none"))
    else:
        alerts["sku_display"] = alerts["sku"].apply(clean_sku)
        TYPE_LABEL = {
            "zero_sales": t("money.alerts.zero"),
            "negative_cm": t("money.alerts.negcm"),
            "wasted_days": t("money.alerts.wasted"),
        }
        alerts["type_label"] = alerts["alert_type"].map(TYPE_LABEL)

        z = alerts[alerts["alert_type"] == "zero_sales"]
        n = alerts[alerts["alert_type"] == "negative_cm"]
        w = alerts[alerts["alert_type"] == "wasted_days"]

        a1, a2, a3 = st.columns(3)
        a1.metric(t("money.alerts.zero"), len(z),
                  delta=f"−{z['ads_spend'].sum():,.0f} €" if len(z) else None,
                  delta_color="inverse", help=t("money.alerts.zero_help"))
        a2.metric(t("money.alerts.negcm"), len(n),
                  delta=f"{n['cm'].sum():,.0f} €" if len(n) else None,
                  delta_color="inverse")
        a3.metric(t("money.alerts.wasted"), len(w))

        st.dataframe(
            alerts[["type_label", "sku_display", "units", "ads_spend", "cm", "details"]],
            use_container_width=True, height=480, hide_index=True,
            column_config={
                "type_label": st.column_config.TextColumn(t("money.alerts.col_type"), width="small"),
                "sku_display": st.column_config.TextColumn("SKU", width="small"),
                "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
                "ads_spend": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
                "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €"),
                "details": st.column_config.TextColumn(t("money.alerts.col_details"), width="large"),
            },
        )
        st.caption(t("money.alerts.note"))
