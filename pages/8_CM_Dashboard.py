# pages/8_CM_Dashboard.py — CM Dashboard: сводка по площадкам и здоровье каналов
from datetime import datetime, timedelta

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
[data-testid="stMetricValue"] { font-size: 1.7rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("cm.title"))
st.caption(t("cm.caption"))

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"
AMBER = "#f2b134"
GREY = "#9aa4b2"
PLOTLY_CFG = {"displayModeBar": False}

# площадки: Amazon по странам + Leroy Merlin (Испания, через Mirakl)
LM_CODE = "LM"
LM_COUNTRY = "ES"

# пороги здоровья канала Leroy Merlin: (ok при >=, warn при >=) либо обратные
# совпадают с порогами загрузчика LM Health — иначе цвет на странице
# расходился бы с алертами
LM_THRESHOLDS = {
    "acceptance_rate_pct": {"ok": 95, "warn": 90, "higher_better": True},
    "tracking_rate_pct": {"ok": 95, "warn": 85, "higher_better": True},
    "on_time_ship_pct": {"ok": 95, "warn": 85, "higher_better": True},
    "avg_acceptance_h": {"ok": 24, "warn": 48, "higher_better": False},
    "p90_acceptance_h": {"ok": 48, "warn": 72, "higher_better": False},
    "incident_rate_pct": {"ok": 0, "warn": 3, "higher_better": False},
    "waiting_acceptance": {"ok": 0, "warn": 3, "higher_better": False},
}


def health_level(metric: str, value) -> str:
    """ok / warn / crit по порогам канала."""
    rule = LM_THRESHOLDS.get(metric)
    if rule is None or value is None or pd.isna(value):
        return "none"
    v = float(value)
    if rule["higher_better"]:
        return "ok" if v >= rule["ok"] else ("warn" if v >= rule["warn"] else "crit")
    return "ok" if v <= rule["ok"] else ("warn" if v <= rule["warn"] else "crit")


LEVEL_COLOR = {"ok": GREEN, "warn": AMBER, "crit": ACCENT, "none": GREY}


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
def load_marketplaces() -> list:
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT DISTINCT marketplace
            FROM kabinet_data.economics_summary
            WHERE marketplace IS NOT NULL
            ORDER BY 1
        """, conn)
    finally:
        conn.close()
    return df["marketplace"].tolist()


@st.cache_data(ttl=600)
def load_sales(days: int) -> pd.DataFrame:
    """Продажи по площадкам за период, SKU нормализован до базового кода."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT SUBSTRING(norm_sku FROM '([0-9]{{5,}})') AS base_sku,
                   marketplace,
                   MAX(product_name)                    AS product_name,
                   SUM(units_ordered)                   AS units,
                   SUM(ordered_product_sales)           AS revenue,
                   SUM(net_proceeds_total)              AS net_proceeds,
                   SUM(total_fees)                      AS fees,
                   SUM(COALESCE(cogs, 0) * units_ordered) AS cogs_total
            FROM kabinet_data.economics_summary
            WHERE sales_date >= CURRENT_DATE - INTERVAL '{days} days'
              AND SUBSTRING(norm_sku FROM '([0-9]{{5,}})') IS NOT NULL
            GROUP BY 1, 2
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_stock() -> pd.DataFrame:
    """Остатки: физический товар и квоты каналов раздельно."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT SUBSTRING(sku FROM '([0-9]{5,})') AS base_sku,
                   source,
                   availability_status,
                   location,
                   warehouse_name,
                   SUM(quantity) AS qty
            FROM kabinet_data.stock_local
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
              AND SUBSTRING(sku FROM '([0-9]{5,})') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_lm_health(days: int) -> pd.DataFrame:
    """Показатели канала. Берём все колонки — состав таблицы может меняться."""
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            SELECT *
            FROM kabinet_data.lm_health_daily
            WHERE calc_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY calc_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    # недостающие показатели добавляем пустыми, чтобы страница не падала
    for col in ("orders_total", "acceptance_rate_pct", "avg_acceptance_h",
                "p90_acceptance_h", "tracking_rate_pct", "on_time_ship_pct",
                "incident_rate_pct", "open_incidents", "waiting_acceptance"):
        if col not in df.columns:
            df[col] = np.nan
    return df


@st.cache_data(ttl=600)
def load_lm_open_orders() -> pd.DataFrame:
    """Заказы Leroy Merlin, ожидающие акцепта. Может отсутствовать — проверяем."""
    if not table_exists("raw_lm_orders"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT order_id,
                   created_date,
                   order_state,
                   total_price,
                   ROUND(EXTRACT(EPOCH FROM (NOW() - created_date)) / 3600.0, 1) AS hours_open
            FROM kabinet_data.raw_lm_orders
            WHERE order_state IN ('WAITING_ACCEPTANCE', 'WAITING_DEBIT')
            ORDER BY created_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT incident_type, severity, sku, warehouse_name,
                   message, source, created_at,
                   DATE_PART('day', NOW() - created_at)::int AS days_open
            FROM kabinet_data.incidents
            WHERE status = 'open'
            ORDER BY created_at
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_returns(days: int) -> pd.DataFrame:
    """Возвраты за период. SKU нормализуем до базового кода, как везде."""
    if not table_exists("raw_amazon_returns"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT SUBSTRING(sku FROM '([0-9]{{5,}})') AS base_sku,
                   marketplace,
                   return_date,
                   COALESCE(NULLIF(return_reason, ''), '—') AS reason,
                   fulfillment_type,
                   MAX(product_name)      AS product_name,
                   SUM(quantity)          AS qty,
                   SUM(refunded_amount)   AS refunded
            FROM kabinet_data.raw_amazon_returns
            WHERE return_date >= CURRENT_DATE - INTERVAL '{days} days'
              AND SUBSTRING(sku FROM '([0-9]{{5,}})') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def fmt_money(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €"


# ═══════════════════════════════════════════════════════════════════
# ФИЛЬТРЫ
# ═══════════════════════════════════════════════════════════════════

all_mp = load_marketplaces()
countries = sorted({m for m in all_mp if m != LM_CODE})

f1, f2 = st.columns([2, 3])
with f1:
    country = st.selectbox(
        t("cm.filter.country"),
        [t("cm.filter.all_countries")] + countries,
        index=(countries.index(LM_COUNTRY) + 1 if LM_COUNTRY in countries else 0),
    )
with f2:
    period = st.segmented_control(
        t("cm.filter.period"), options=["7", "30", "60", "90"], default="30")
DAYS = int(period or 30)

is_all = country == t("cm.filter.all_countries")
# Leroy Merlin работает только в Испании — показываем его вместе с ES
mp_scope = all_mp if is_all else (
    [country, LM_CODE] if country == LM_COUNTRY else [country])

sales = load_sales(DAYS)
stock = load_stock()

st.markdown(f"""
<div style="border:1px solid rgba(128,128,128,0.22); border-left:3px solid {BLUE};
            border-radius:10px; padding:12px 18px; margin:14px 0 4px 0;
            background:rgba(31,119,180,0.045);">
  <div style="font-size:0.72rem; font-weight:700; letter-spacing:.06em;
              text-transform:uppercase; color:{BLUE}; margin-bottom:4px;">
    {t("cm.intro.title")}</div>
  <div style="font-size:0.93rem; line-height:1.55;">{t("cm.intro.body")}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

tab_sum, tab_lm, tab_amz, tab_all = st.tabs(
    [t("cm.tab.summary"), t("cm.tab.lm_health"),
     t("cm.tab.amazon_health"), t("cm.tab.all_countries")]
)


# ═══════════════════════════════════════════════════════════════════
# СВОД ПО ТОВАРАМ: AMAZON ПРОТИВ LEROY MERLIN
# ═══════════════════════════════════════════════════════════════════

with tab_sum:
    scoped = sales[sales["marketplace"].isin(mp_scope)].copy()

    if scoped.empty:
        st.info(t("common.no_data"))
    else:
        scoped["platform"] = np.where(
            scoped["marketplace"] == LM_CODE, "lm", "amazon")

        agg = (scoped.groupby(["base_sku", "platform"], as_index=False)
                     .agg(product_name=("product_name", "first"),
                          units=("units", "sum"), revenue=("revenue", "sum"),
                          net=("net_proceeds", "sum"), cogs=("cogs_total", "sum")))
        agg["avg_price"] = np.round(safe_div(agg["revenue"], agg["units"]), 2)

        wide = agg.pivot(index="base_sku", columns="platform",
                         values=["units", "revenue", "avg_price", "net"])
        wide.columns = [f"{a}_{b}" for a, b in wide.columns]
        wide = wide.reset_index().fillna(0)

        names = (agg.sort_values("revenue", ascending=False)
                    .drop_duplicates("base_sku").set_index("base_sku")["product_name"])
        wide["product_name"] = wide["base_sku"].map(names).fillna("—")

        # остатки: физический товар и выделенная квота канала
        phys = (stock[stock["availability_status"] == "available"]
                .groupby("base_sku", as_index=False)["qty"].sum()
                .rename(columns={"qty": "stock_amazon"}))
        quota = (stock[stock["source"] == "mirakl-offers"]
                 .groupby("base_sku", as_index=False)["qty"].sum()
                 .rename(columns={"qty": "stock_lm"}))
        wide = wide.merge(phys, on="base_sku", how="left") \
                   .merge(quota, on="base_sku", how="left")
        wide[["stock_amazon", "stock_lm"]] = \
            wide[["stock_amazon", "stock_lm"]].fillna(0)

        # доля возвратов от проданного — сразу видно проблемные позиции
        rets_all = load_returns(DAYS)
        if not rets_all.empty:
            rq = (rets_all[rets_all["marketplace"].isin(mp_scope)]
                  .groupby("base_sku", as_index=False)["qty"].sum()
                  .rename(columns={"qty": "returns_qty"}))
            wide = wide.merge(rq, on="base_sku", how="left")
        if "returns_qty" not in wide.columns:
            wide["returns_qty"] = 0
        wide["returns_qty"] = wide["returns_qty"].fillna(0)

        for col in ("units_amazon", "units_lm", "revenue_amazon", "revenue_lm",
                    "avg_price_amazon", "avg_price_lm"):
            if col not in wide.columns:
                wide[col] = 0.0

        sold_total = wide["units_amazon"] + wide["units_lm"]
        wide["returns_pct"] = np.where(
            sold_total > 0,
            np.round(wide["returns_qty"] / sold_total * 100, 1),
            np.nan)
        wide["returns_alert"] = wide["returns_pct"] > 15

        # расхождение цены между площадками — только там, где продаётся на обеих
        both = (wide["avg_price_amazon"] > 0) & (wide["avg_price_lm"] > 0)
        wide["price_gap_pct"] = np.where(
            both,
            np.round((wide["avg_price_lm"] - wide["avg_price_amazon"])
                     / wide["avg_price_amazon"].replace(0, np.nan) * 100, 1),
            np.nan)
        wide["price_alert"] = both & (wide["price_gap_pct"].abs() > 10)

        wide = wide.sort_values("revenue_amazon", ascending=False)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric(t("cm.kpi.skus"), f"{len(wide):,}")
        k2.metric(t("cm.kpi.revenue_amazon"), fmt_money(wide["revenue_amazon"].sum()))
        k3.metric(t("cm.kpi.revenue_lm"), fmt_money(wide["revenue_lm"].sum()))
        k4.metric(t("cm.kpi.price_alerts"), f"{int(wide['price_alert'].sum()):,}",
                  help=t("cm.kpi.price_alerts_help"))
        k5.metric(t("cm.kpi.return_alerts"), f"{int(wide['returns_alert'].sum()):,}",
                  help=t("cm.kpi.return_alerts_help"))

        fl1, fl2 = st.columns([1, 1])
        with fl1:
            only_alerts = st.toggle(t("cm.summary.only_alerts"), value=False)
        with fl2:
            only_returns = st.toggle(t("cm.summary.only_returns"), value=False)

        view = wide
        if only_alerts:
            view = view[view["price_alert"]]
        if only_returns:
            view = view[view["returns_alert"]]

        if view.empty:
            st.success(t("cm.summary.no_alerts"))
        else:
            st.dataframe(
                view[["base_sku", "product_name",
                      "units_amazon", "revenue_amazon", "avg_price_amazon", "stock_amazon",
                      "units_lm", "revenue_lm", "avg_price_lm", "stock_lm",
                      "price_gap_pct", "returns_pct"]],
                use_container_width=True, height=560, hide_index=True,
                column_config={
                    "base_sku": st.column_config.TextColumn("SKU", width="small"),
                    "product_name": st.column_config.TextColumn(
                        t("cm.col.product"), width="medium"),
                    "units_amazon": st.column_config.NumberColumn(
                        t("cm.col.units_amazon"), width="small"),
                    "revenue_amazon": st.column_config.NumberColumn(
                        t("cm.col.revenue_amazon"), format="%.0f €"),
                    "avg_price_amazon": st.column_config.NumberColumn(
                        t("cm.col.price_amazon"), format="%.2f €"),
                    "stock_amazon": st.column_config.NumberColumn(
                        t("cm.col.stock_amazon"), width="small",
                        help=t("cm.col.stock_amazon_help")),
                    "units_lm": st.column_config.NumberColumn(
                        t("cm.col.units_lm"), width="small"),
                    "revenue_lm": st.column_config.NumberColumn(
                        t("cm.col.revenue_lm"), format="%.0f €"),
                    "avg_price_lm": st.column_config.NumberColumn(
                        t("cm.col.price_lm"), format="%.2f €"),
                    "stock_lm": st.column_config.NumberColumn(
                        t("cm.col.stock_lm"), width="small",
                        help=t("cm.col.stock_lm_help")),
                    "price_gap_pct": st.column_config.NumberColumn(
                        t("cm.col.price_gap"), format="%+.1f%%",
                        help=t("cm.col.price_gap_help")),
                    "returns_pct": st.column_config.NumberColumn(
                        t("cm.col.returns_pct"), format="%.0f%%",
                        help=t("cm.col.returns_pct_help")),
                },
            )
            st.caption(t("cm.summary.note"))

            st.download_button(
                t("cm.download"),
                view.to_csv(index=False).encode("utf-8-sig"),
                file_name="cm_summary.csv", mime="text/csv", key="dl_cm_sum")


# ═══════════════════════════════════════════════════════════════════
# ЗДОРОВЬЕ КАНАЛА LEROY MERLIN
# ═══════════════════════════════════════════════════════════════════

with tab_lm:
    if not table_exists("lm_health_daily"):
        st.info(t("cm.lm.no_table"))
    else:
        lm = load_lm_health(DAYS)
        if lm.empty:
            st.info(t("common.no_data"))
        else:
            last = lm.iloc[-1]
            st.caption(t("cm.lm.as_of").format(
                d=pd.to_datetime(last["calc_date"]).strftime("%d.%m.%Y")))

            cards = [
                ("acceptance_rate_pct", t("cm.lm.acceptance"), "{:.0f}%"),
                ("avg_acceptance_h", t("cm.lm.avg_time"), "{:.1f} ч"),
                ("p90_acceptance_h", t("cm.lm.p90_time"), "{:.0f} ч"),
                ("tracking_rate_pct", t("cm.lm.tracking"), "{:.0f}%"),
                ("incident_rate_pct", t("cm.lm.incidents"), "{:.1f}%"),
                ("waiting_acceptance", t("cm.lm.waiting"), "{:.0f}"),
            ]
            cc = st.columns(len(cards))
            for col, (field, label, fmt) in zip(cc, cards):
                val = last.get(field)
                lvl = health_level(field, val)
                shown = "—" if val is None or pd.isna(val) else fmt.format(float(val))
                with col:
                    st.markdown(
                        f'<div style="border:1px solid rgba(128,128,128,0.35);'
                        f'border-left:3px solid {LEVEL_COLOR[lvl]};border-radius:12px;'
                        f'padding:12px 14px;">'
                        f'<div style="font-size:0.72rem;color:var(--text-secondary);'
                        f'margin-bottom:4px;">{label}</div>'
                        f'<div style="font-size:1.5rem;font-weight:500;">{shown}</div>'
                        f'</div>', unsafe_allow_html=True)

            st.markdown("")
            o1, o2, o3 = st.columns(3)
            o1.metric(t("cm.lm.orders"), f"{int(last.get('orders_total') or 0):,}")
            o2.metric(t("cm.lm.on_time"),
                      f"{float(last.get('on_time_ship_pct') or 0):.0f}%")
            o3.metric(t("cm.lm.open_incidents"),
                      f"{int(last.get('open_incidents') or 0):,}")

            st.divider()

            # ---- тренд по дням ----
            st.markdown(f"**{t('cm.lm.trend')}**")
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(name=t("cm.lm.orders"), x=lm["calc_date"],
                                 y=lm["orders_total"], marker_color=BLUE),
                          secondary_y=False)
            fig.add_trace(go.Scatter(name=t("cm.lm.acceptance"), x=lm["calc_date"],
                                     y=lm["acceptance_rate_pct"], mode="lines+markers",
                                     line=dict(color=GREEN, width=2)), secondary_y=True)
            fig.add_trace(go.Scatter(name=t("cm.lm.tracking"), x=lm["calc_date"],
                                     y=lm["tracking_rate_pct"], mode="lines+markers",
                                     line=dict(color=AMBER, width=2, dash="dot")),
                          secondary_y=True)
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                              hovermode="x unified",
                              legend=dict(orientation="h", y=1.14))
            fig.update_yaxes(title_text=t("cm.lm.orders"), secondary_y=False)
            fig.update_yaxes(range=[0, 105], ticksuffix="%", showgrid=False,
                             secondary_y=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

            # ---- заказы, ждущие акцепта ----
            waiting = load_lm_open_orders()
            st.markdown(f"**{t('cm.lm.waiting_title')}**")
            if waiting.empty:
                st.success(t("cm.lm.waiting_none"))
            else:
                waiting["created_date"] = pd.to_datetime(
                    waiting["created_date"]).dt.strftime("%d.%m %H:%M")
                st.dataframe(
                    waiting[["order_id", "created_date", "order_state",
                             "total_price", "hours_open"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "order_id": st.column_config.TextColumn(
                            t("cm.col.order"), width="medium"),
                        "created_date": st.column_config.TextColumn(
                            t("cm.col.created"), width="small"),
                        "order_state": st.column_config.TextColumn(
                            t("cm.col.state"), width="small"),
                        "total_price": st.column_config.NumberColumn(
                            t("cm.col.amount"), format="%.2f €"),
                        "hours_open": st.column_config.NumberColumn(
                            t("cm.col.hours_open"), format="%.0f ч"),
                    },
                )
                st.warning(t("cm.lm.waiting_warn").format(n=len(waiting)))


# ═══════════════════════════════════════════════════════════════════
# ЗДОРОВЬЕ AMAZON
# ═══════════════════════════════════════════════════════════════════

with tab_amz:
    inc = load_incidents()

    if inc.empty:
        st.success(t("cm.amz.no_incidents"))
    else:
        # инциденты Leroy Merlin живут в общем журнале — здесь показываем
        # только амазоновские, чтобы вкладки не дублировали друг друга
        inc["source"] = inc["source"].fillna("amazon")
        amz = inc[~inc["source"].str.contains("leroy|lm", case=False, na=False)].copy()

        a1, a2, a3, a4 = st.columns(4)
        a1.metric(t("cm.amz.open_incidents"), f"{len(amz):,}")
        a2.metric(t("cm.amz.critical"),
                  f"{int((amz['severity'] == 'critical').sum()):,}")
        a3.metric(t("cm.amz.high"),
                  f"{int((amz['severity'] == 'high').sum()):,}")
        a4.metric(t("cm.amz.oldest"),
                  f"{int(amz['days_open'].max()) if len(amz) else 0}",
                  help=t("cm.amz.oldest_help"))

        st.divider()

        # по типу — что именно чаще всего требует внимания
        by_type = (amz.groupby("incident_type", as_index=False)
                      .agg(cnt=("incident_type", "size"),
                           oldest=("days_open", "max"))
                      .sort_values("cnt", ascending=False))
        fig = px.bar(by_type.sort_values("cnt"), x="cnt", y="incident_type",
                     orientation="h", text="cnt",
                     title=t("cm.amz.by_type"),
                     color_discrete_sequence=[ACCENT])
        fig.update_layout(height=max(240, 40 * len(by_type)),
                          xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.markdown(f"**{t('cm.amz.incidents_title')}**")
        view = amz.sort_values("days_open", ascending=False).copy()
        view["created_at"] = pd.to_datetime(view["created_at"]).dt.strftime("%d.%m.%Y")
        st.dataframe(
            view[["created_at", "days_open", "severity", "incident_type",
                  "sku", "warehouse_name", "message"]],
            use_container_width=True, height=420, hide_index=True,
            column_config={
                "created_at": st.column_config.TextColumn(
                    t("cm.col.created"), width="small"),
                "days_open": st.column_config.NumberColumn(
                    t("cm.col.days_open"), width="small",
                    help=t("cm.col.days_open_help")),
                "severity": st.column_config.TextColumn(
                    t("cm.col.severity"), width="small"),
                "incident_type": st.column_config.TextColumn(
                    t("cm.col.type"), width="small"),
                "sku": st.column_config.TextColumn("SKU", width="small"),
                "warehouse_name": st.column_config.TextColumn(
                    t("cm.col.warehouse"), width="medium"),
                "message": st.column_config.TextColumn(
                    t("cm.col.description"), width="large"),
            },
        )
        st.caption(t("cm.amz.incidents_note"))

    # ---- возвраты ----
    rets = load_returns(DAYS)
    st.divider()
    st.markdown(f"**{t('cm.amz.returns_title')}**")

    if rets.empty:
        st.info(t("cm.amz.no_returns"))
    else:
        scoped_ret = rets[rets["marketplace"].isin(mp_scope)] if not is_all else rets

        r1, r2, r3 = st.columns(3)
        r1.metric(t("cm.amz.returns"), f"{int(scoped_ret['qty'].sum()):,}",
                  help=t("cm.amz.returns_help").format(d=DAYS))
        r2.metric(t("cm.amz.refunded"), fmt_money(scoped_ret["refunded"].sum()))
        r3.metric(t("cm.amz.return_skus"), f"{scoped_ret['base_sku'].nunique():,}")

        rc1, rc2 = st.columns([1, 1])
        with rc1:
            top = (scoped_ret.groupby(["base_sku", "product_name"], as_index=False)
                             ["qty"].sum().nlargest(12, "qty"))
            if not top.empty:
                fig = px.bar(top.sort_values("qty"), x="qty", y="base_sku",
                             orientation="h", text="qty",
                             title=t("cm.amz.top_returns"),
                             color_discrete_sequence=[ACCENT])
                fig.update_layout(height=max(280, 28 * len(top)),
                                  xaxis_title=None, yaxis_title=None,
                                  margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        with rc2:
            # причина приходит только по FBA — по остальным Amazon её не отдаёт
            by_reason = (scoped_ret.groupby("reason", as_index=False)["qty"].sum()
                                   .sort_values("qty", ascending=False))
            if not by_reason.empty:
                fig = px.pie(by_reason, names="reason", values="qty", hole=0.5,
                             title=t("cm.amz.by_reason"))
                fig.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
                st.caption(t("cm.amz.reason_note"))


# ═══════════════════════════════════════════════════════════════════
# СВОД ПО ВСЕМ СТРАНАМ
# ═══════════════════════════════════════════════════════════════════

with tab_all:
    if sales.empty:
        st.info(t("common.no_data"))
    else:
        by_mp = (sales.groupby("marketplace", as_index=False)
                      .agg(skus=("base_sku", "nunique"), units=("units", "sum"),
                           revenue=("revenue", "sum"), net=("net_proceeds", "sum"),
                           fees=("fees", "sum"), cogs=("cogs_total", "sum")))
        by_mp["cm"] = by_mp["net"] - by_mp["cogs"]
        by_mp["cm_pct"] = np.round(safe_div(by_mp["cm"], by_mp["revenue"]) * 100, 1)
        by_mp["fees_pct"] = np.round(safe_div(by_mp["fees"], by_mp["revenue"]) * 100, 1)
        by_mp["platform"] = np.where(by_mp["marketplace"] == LM_CODE,
                                     t("cm.platform.lm"), t("cm.platform.amazon"))
        by_mp = by_mp.sort_values("revenue", ascending=False)

        cc = st.columns(min(len(by_mp), 5) or 1)
        for i, (_, r) in enumerate(by_mp.iterrows()):
            with cc[i % len(cc)]:
                st.metric(r["marketplace"], fmt_money(r["revenue"]),
                          delta=f"{r['cm_pct']:.0f}%",
                          help=t("cm.all.metric_help"))

        fig = px.bar(by_mp, x="marketplace", y="revenue", color="platform",
                     title=t("cm.all.chart"), text="revenue",
                     color_discrete_map={t("cm.platform.amazon"): BLUE,
                                         t("cm.platform.lm"): GREEN})
        fig.update_traces(texttemplate="%{text:.0f}")
        fig.update_layout(height=360, xaxis_title=None,
                          yaxis_title="€", margin=dict(l=10, r=10, t=50, b=10),
                          legend=dict(orientation="h", y=1.12, title_text=""))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.dataframe(
            by_mp[["marketplace", "platform", "skus", "units", "revenue",
                   "fees", "fees_pct", "cogs", "cm", "cm_pct"]],
            use_container_width=True, hide_index=True,
            column_config={
                "marketplace": st.column_config.TextColumn(t("cm.col.marketplace")),
                "platform": st.column_config.TextColumn(t("cm.col.platform")),
                "skus": st.column_config.NumberColumn(t("cm.col.skus"), width="small"),
                "units": st.column_config.NumberColumn(t("cm.col.units"), width="small"),
                "revenue": st.column_config.NumberColumn(
                    t("cm.col.revenue"), format="%.0f €"),
                "fees": st.column_config.NumberColumn(
                    t("cm.col.fees"), format="%.0f €"),
                "fees_pct": st.column_config.NumberColumn(
                    t("cm.col.fees_pct"), format="%.0f%%"),
                "cogs": st.column_config.NumberColumn("COGS", format="%.0f €"),
                "cm": st.column_config.NumberColumn(t("cm.col.cm"), format="%.0f €"),
                "cm_pct": st.column_config.NumberColumn(
                    t("cm.col.cm_pct"), format="%.1f%%"),
            },
        )
        st.caption(t("cm.all.note"))
