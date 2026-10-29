# worten_tab.py — вкладка «Worten» на странице «Площадки» (pages/8_CM_Dashboard.py), 29.10.2026, решение владельца:
# Worten — новый источник по API, как TikTok Shop, а не реплика Power BI; Power BI Кабинет не ждёт. Отдельной
# страницы и своего права нет — вкладка живёт под правом страницы (page.cm). Флага у вкладки нет: «Продажи пока
# только на „Площадках“. На „Обзор“ — только после сверки, за выключенным флагом» (ответ владельца на аудит 28.10.2026;
# строка «Обзора» — за флагом worten_overview_enabled, home.py).
#
# Источник — Worten API (Mirakl), не Power BI: реплики kabinet_data.raw_worten_* в Lakebase, их пишет
# Kabinet - Worten Loader (docs/worten.md). Деньги — как у Worten: с НДС, в евро. Продажи — по строкам заказа без
# отмен, отказов и возвратов, как у Leroy Merlin в v_sales_vat_incl_daily. День заказа — по Лиссабону: created_at в
# реплике — часы Лиссабона, записанные как UTC, поэтому день — дата этого времени в UTC (решение владельца 28.10.2026).
import pandas as pd
import streamlit as st

from db.connection import get_connection, data_version
from i18n import t

TZ = "Europe/Lisbon"
# строки, которые продажей не считаются: тот же список, что у Leroy Merlin в v_sales_vat_incl_daily
NOT_SALE = ("REFUNDED", "CANCELED", "REFUSED")


@st.cache_data(ttl=300)
def replica_exists() -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('kabinet_data.raw_worten_order_lines') IS NOT NULL")
        return bool(cur.fetchone()[0])
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load(d_from, d_to, ver: str = "") -> dict:
    """Строки заказов периода (день заказа по Лиссабону) и офферы последнего снимка."""
    conn = get_connection()
    q = {"a": d_from, "b": d_to}
    try:
        lines = pd.read_sql("""
            SELECT o.order_id, o.order_state, (o.created_at AT TIME ZONE 'UTC')::date AS day, o.country,
                   l.order_line_id, l.order_line_state, l.shop_sku, l.product_title, l.quantity, l.price,
                   l.commission_fee, l.tax_amount
            FROM kabinet_data.raw_worten_order_lines l
            JOIN kabinet_data.raw_worten_orders o ON o.shop_id = l.shop_id AND o.order_id = l.order_id
            WHERE (o.created_at AT TIME ZONE 'UTC')::date BETWEEN %(a)s AND %(b)s
            ORDER BY o.created_at, l.order_line_id""", conn, params=q)
        offers = pd.read_sql("""
            SELECT shop_sku, product_title, active, quantity, price, origin_price, promo_active, discount_end,
                   in_last_load
            FROM kabinet_data.raw_worten_offers ORDER BY shop_sku""", conn)
        meta = pd.read_sql("SELECT max(loaded_at) AS loaded_at FROM kabinet_data.raw_worten_offers", conn)
    finally:
        conn.close()
    return {"lines": lines, "offers": offers, "loaded_at": meta["loaded_at"].iloc[0] if not meta.empty else None}


def render(P) -> None:
    """Содержимое вкладки «Worten». P — период страницы (period.Period из её общего переключателя)."""
    st.caption(t("wt.caption"))
    if not replica_exists():
        st.info(t("wt.no_replica"))
        return

    # сегодняшний день — не день с данными (AGENTS.md): конец периода — не позже вчера по Лиссабону
    _yday = (pd.Timestamp.now(tz=TZ).normalize() - pd.Timedelta(days=1)).date()
    d_from, d_to = P.start.date(), min(P.end.date(), _yday)
    if d_to < d_from:   # период — только сегодня: полного дня ещё нет
        st.info(t("wt.today_only"))
        return
    try:
        data = load(d_from, d_to, data_version("raw_worten_offers", "loaded_at"))
    except Exception as e:
        st.error(f"{t('wt.db_error')}: {e}")
        return

    st.caption(t("wt.as_of", d=as_of(data["loaded_at"])))
    ln = data["lines"].copy()
    for c in ("price", "commission_fee", "tax_amount", "quantity"):
        ln[c] = pd.to_numeric(ln[c], errors="coerce").fillna(0.0)
    # строка без статуса — не продажа, как у Leroy Merlin (NULL <> ALL(...) там тоже не проходит)
    ln["sale"] = ln["order_line_state"].notna() & ~ln["order_line_state"].astype(str).str.upper().isin(NOT_SALE)
    sale = ln[ln["sale"]]
    st.caption(t("wt.slice", a=d_from.strftime("%d.%m.%Y"), b=d_to.strftime("%d.%m.%Y"),
                 n=sale["order_id"].nunique(), c=int((~ln["sale"]).sum())))

    k = st.columns(4)
    k[0].metric(t("wt.k.orders"), f"{sale['order_id'].nunique()}")
    k[1].metric(t("wt.k.sales"), eur0(sale["price"].sum()))
    k[2].metric(t("wt.k.commission"), eur0(-sale["commission_fee"].sum()))
    k[3].metric(t("wt.k.units"), f"{int(sale['quantity'].sum())}")
    st.caption(t("wt.vat_note"))

    st.subheader(t("wt.orders"))
    if ln.empty:
        st.caption(t("wt.empty"))
    else:
        st.dataframe(pd.DataFrame({
            t("wt.c.day"): pd.to_datetime(ln["day"]).dt.strftime("%d.%m.%Y"), t("wt.c.order"): ln["order_id"],
            t("wt.c.state"): ln["order_line_state"], t("wt.c.sku"): ln["shop_sku"], t("wt.c.title"): ln["product_title"],
            t("wt.c.qty"): ln["quantity"].astype(int), t("wt.c.price"): ln["price"].round(2),
            t("wt.c.commission"): (-ln["commission_fee"]).round(2) + 0.0, t("wt.c.tax"): ln["tax_amount"].round(2)}),
            hide_index=True, use_container_width=True)

    # офферы — снимок на время загрузки, а не за период: цена для покупателя (цена канала WRT_PT_ONLINE по сроку скидки)
    of = data["offers"].copy()
    st.subheader(t("wt.offers"))
    st.caption(t("wt.offers_snapshot", d=as_of(data["loaded_at"])))
    if of.empty:
        st.caption(t("wt.none"))
    else:
        live = of[of["in_last_load"].fillna(False).astype(bool)]
        k = st.columns(3)
        k[0].metric(t("wt.k.offers_active"), f"{int(live['active'].fillna(False).astype(bool).sum())} / {len(live)}")
        _act = live["active"].fillna(False).astype(bool)
        k[1].metric(t("wt.k.offers_promo"), f"{int((live['promo_active'].fillna(False).astype(bool) & _act).sum())}")
        k[2].metric(t("wt.k.offers_stock"), f"{int((pd.to_numeric(live['quantity'], errors='coerce') > 0).sum())}")
        st.dataframe(pd.DataFrame({
            t("wt.c.sku"): live["shop_sku"], t("wt.c.title"): live["product_title"],
            t("wt.c.active"): live["active"].fillna(False).astype(bool),
            t("wt.c.qty"): pd.to_numeric(live["quantity"], errors="coerce"),
            t("wt.c.buyer_price"): pd.to_numeric(live["price"], errors="coerce").round(2),
            t("wt.c.origin_price"): pd.to_numeric(live["origin_price"], errors="coerce").round(2),
            t("wt.c.promo"): live["promo_active"].fillna(False).astype(bool),
            t("wt.c.promo_end"): pd.to_datetime(live["discount_end"], utc=True).dt.tz_convert(TZ).dt.strftime("%d.%m.%Y")}),
            hide_index=True, use_container_width=True)
    st.caption(t("wt.source", d=(pd.Timestamp(data["loaded_at"]).tz_convert("Europe/Kyiv").strftime("%d.%m.%Y %H:%M")
                                  if data["loaded_at"] is not None and not pd.isna(data["loaded_at"]) else "—")))


def eur0(v) -> str:
    # round(…) + 0.0 — без «-0 €», когда сумма округляется к нулю с минусом
    return "—" if v is None or pd.isna(v) else f"{round(float(v)) + 0.0:,.0f} €".replace(",", " ")


def as_of(_la) -> str:
    """«ДД.ММ ЧЧ:ММ» (Киев) последней загрузки реплики или «—»."""
    return pd.Timestamp(_la).tz_convert("Europe/Kyiv").strftime("%d.%m %H:%M") if _la is not None and not pd.isna(_la) else "—"
