# tiktok_tab.py — вкладка «TikTok Shop» на странице «Площадки» (pages/8_CM_Dashboard.py), 22.10.2026, решение
# владельца: отдельной страницы и своего права нет — вкладка живёт под правом страницы (page.cm). До сверки заказов с
# Seller Center её видит только администратор: флаг reorder_params.tiktok_tab_enabled (0 — только admin, 1 — все, кто
# видит «Площадки»), включает владелец.
#
# Источник — TikTok Shop API, не Power BI (исключение подтверждено владельцем 22.10.2026): реплики kabinet_data.
# raw_tiktok_* в Lakebase, их пишет Kabinet - TikTok Shop Loader. Деньги — как у TikTok, с НДС (сверяемо с Seller
# Center). Выручка продавца = sub_total + platform_discount (цена до скидок минус скидка продавца; скидку платформы
# платит TikTok) — так сходятся 109 из 113 заказов с выплатами (docs/tiktok-shop.md). Период — по дате создания
# заказа по Мадриду; без отмен и образцов, кроме блока образцов.
import pandas as pd
import streamlit as st

from db.connection import get_connection, data_version
from i18n import t

TZ = "Europe/Madrid"


@st.cache_data(ttl=300)
def tab_visible_to_all() -> bool:
    """tiktok_tab_enabled = 1 — вкладку видят все, кто видит страницу; иначе (или настройки нет) — только admin."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'tiktok_tab_enabled'")
        row = cur.fetchone()
        return bool(row) and int(row[0] or 0) == 1
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=300)
def replica_exists() -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('kabinet_data.raw_tiktok_orders') IS NOT NULL")
        return bool(cur.fetchone()[0])
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load(d_from, d_to, ver: str = "") -> dict:
    """Заказы, строки и операции выписок за период (дата создания заказа по Мадриду) и возвраты периода — по дате
    выписки возврата; возврат без даты выписки (statement_time пуст) — по дате заказа в периоде, refund_day у него пуст."""
    conn = get_connection()
    try:
        q = {"a": d_from, "b": d_to}
        orders = pd.read_sql("""
            SELECT order_id, status, is_sample_order, (create_time AT TIME ZONE 'Europe/Madrid')::date AS day,
                   currency, sub_total, coalesce(platform_discount, 0) AS platform_discount,
                   coalesce(seller_discount, 0) AS seller_discount
            FROM kabinet_data.raw_tiktok_orders
            WHERE (create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s""", conn, params=q)
        lines = pd.read_sql("""
            SELECT l.order_id, l.seller_sku, l.product_name, l.sale_price, coalesce(l.platform_discount, 0) AS platform_discount
            FROM kabinet_data.raw_tiktok_order_lines l
            JOIN kabinet_data.raw_tiktok_orders o ON o.shop_id = l.shop_id AND o.order_id = l.order_id
            WHERE (o.create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s""", conn, params=q)
        tx = pd.read_sql("""
            SELECT x.order_id, x.statement_time, x.payment_status, x.revenue_amount, x.fee_tax_amount, x.settlement_amount
            FROM kabinet_data.raw_tiktok_finance_tx x
            JOIN kabinet_data.raw_tiktok_orders o ON o.order_id = x.order_id AND o.shop_id = x.shop_id
            WHERE (o.create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s""", conn, params=q)
        # возвраты — по дате выписки возврата (Мадрид), а не по дате заказа: заказ июня, возвращённый в июле, — в июле;
        # возврат без даты выписки берётся по дате заказа в периоде и показывается отдельной строкой «без даты»
        refunds = pd.read_sql("""
            SELECT x.order_id, (x.statement_time AT TIME ZONE 'Europe/Madrid')::date AS refund_day,
                   x.revenue_amount, x.fee_tax_amount, x.settlement_amount,
                   (o.create_time AT TIME ZONE 'Europe/Madrid')::date AS day, o.status
            FROM kabinet_data.raw_tiktok_finance_tx x
            JOIN kabinet_data.raw_tiktok_orders o ON o.order_id = x.order_id AND o.shop_id = x.shop_id
            WHERE x.revenue_amount < 0 AND coalesce(o.status, '') <> 'CANCELLED' AND NOT coalesce(o.is_sample_order, false)
              AND ((x.statement_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s
                   OR x.statement_time IS NULL AND (o.create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s)""",
            conn, params=q)
        meta = pd.read_sql("SELECT max(loaded_at) AS loaded_at FROM kabinet_data.raw_tiktok_orders", conn)
    finally:
        conn.close()
    return {"orders": orders, "lines": lines, "tx": tx, "refunds": refunds,
            "loaded_at": meta["loaded_at"].iloc[0] if not meta.empty else None}


def render(P) -> None:
    """Содержимое вкладки «TikTok Shop». P — период страницы (period.Period из её общего переключателя)."""
    st.caption(t("tt.caption"))
    if not replica_exists():
        # реплики ещё нет (SQL sql/tiktok_page_2026-10-22.sql не применён или загрузчик ни разу не писал) — не ошибка
        st.info(t("tt.no_replica"))
        return

    # сегодняшний день — не день с данными (AGENTS.md): конец периода — не позже вчера по Мадриду
    _yday = (pd.Timestamp.now(tz=TZ).normalize() - pd.Timedelta(days=1)).date()
    d_from, d_to = P.start.date(), min(P.end.date(), _yday)
    try:
        data = load(d_from, d_to, data_version("raw_tiktok_orders", "loaded_at"))
    except Exception as e:
        st.error(f"{t('tt.db_error')}: {e}")
        return

    o, lines, tx = data["orders"], data["lines"], data["tx"]
    # возвраты идут по дате выписки возврата, поэтому у периода без заказов они могут быть — их показываем всё равно
    rf = data["refunds"].copy()
    for c in ("revenue_amount", "fee_tax_amount", "settlement_amount"):
        rf[c] = pd.to_numeric(rf[c], errors="coerce").fillna(0.0)
    rf["refund_day"] = pd.to_datetime(rf["refund_day"])
    rf["week"] = rf["refund_day"] - pd.to_timedelta(rf["refund_day"].dt.weekday, unit="D")
    rf = rf.sort_values(["refund_day", "order_id"], na_position="last")
    if o.empty:
        st.info(t("tt.empty"))
        if not rf.empty:
            nodate_warning(rf)
            k = st.columns(3)
            k[0].metric(t("tt.k.refunds"), eur0(rf["revenue_amount"].sum()))
            k[1].metric(t("tt.k.fee_refunds"), eur0(rf["fee_tax_amount"].sum()))
            k[2].metric(t("tt.k.payout"), eur0(rf["settlement_amount"].sum()), help=t("tt.k.payout_help"))
            st.caption(t("tt.refunds_line"))
            refunds_block(rf)
        source_line(data["loaded_at"])
        return

    o["day"] = pd.to_datetime(o["day"])
    for c in ("sub_total", "platform_discount", "seller_discount"):
        o[c] = pd.to_numeric(o[c], errors="coerce").fillna(0.0)
    o["sample"] = o["is_sample_order"].fillna(False).astype(bool)
    o["cancelled"] = o["status"].astype(str) == "CANCELLED"
    o["seller_rev"] = o["sub_total"] + o["platform_discount"]
    real = o[~o["sample"] & ~o["cancelled"]].copy()
    for c in ("revenue_amount", "fee_tax_amount", "settlement_amount"):
        tx[c] = pd.to_numeric(tx[c], errors="coerce").fillna(0.0)
    # комиссии и выплата заказа — только с операций продажи (выручка ≥ 0), по неделе заказа; возврат и возврат комиссии —
    # с операций возврата (rf), по неделе возврата: так возврат вычитается один раз и строка недели складывается
    # (решение владельца 23.10.2026)
    sale = tx[tx["revenue_amount"] >= 0]
    by_order = sale.groupby("order_id").agg(fee=("fee_tax_amount", "sum"), payout=("settlement_amount", "sum")).reset_index()
    real = real.merge(by_order, on="order_id", how="left")
    real["paid"] = real["payout"].notna()

    nodate_warning(rf)
    # ── плитки: два ряда, в целых евро (центы — в таблицах ниже) ──
    k = st.columns(4)
    k[0].metric(t("tt.k.orders"), f"{len(real)}")
    k[1].metric(t("tt.k.revenue"), eur0(real["seller_rev"].sum()))
    k[2].metric(t("tt.k.seller_discount"), eur0(real["seller_discount"].sum()))
    k[3].metric(t("tt.k.platform_discount"), eur0(real["platform_discount"].sum()))
    k = st.columns(5)
    k[0].metric(t("tt.k.fees"), eur0(real["fee"].fillna(0).sum()))
    k[1].metric(t("tt.k.refunds"), eur0(rf["revenue_amount"].sum()))
    k[2].metric(t("tt.k.fee_refunds"), eur0(rf["fee_tax_amount"].sum()))
    k[3].metric(t("tt.k.payout"), eur0(real["payout"].fillna(0).sum() + rf["settlement_amount"].sum()),
                help=t("tt.k.payout_help"))
    k[4].metric(t("tt.k.paid_share"), f"{real['paid'].mean() * 100:.0f} %" if len(real) else "—")
    st.caption(t("tt.vat_note"))
    st.caption(t("tt.refunds_line"))

    # ── по неделям ──
    st.subheader(t("tt.weeks"))
    real["week"] = real["day"] - pd.to_timedelta(real["day"].dt.weekday, unit="D")
    o["week"] = o["day"] - pd.to_timedelta(o["day"].dt.weekday, unit="D")
    wk = real.groupby("week").agg(orders=("order_id", "count"), revenue=("seller_rev", "sum"),
                                  seller_discount=("seller_discount", "sum"), platform_discount=("platform_discount", "sum"),
                                  fees=("fee", "sum"), payout=("payout", "sum"), paid=("paid", "mean")).reset_index()
    rw = rf[rf["refund_day"].notna()].groupby("week").agg(refund=("revenue_amount", "sum"), fee_refund=("fee_tax_amount", "sum"),
                                                          refund_payout=("settlement_amount", "sum")).reset_index()
    canc = o[o["cancelled"] & ~o["sample"]].groupby("week").size().rename("cancelled").reset_index()
    wk = wk.merge(canc, on="week", how="outer").fillna({"orders": 0, "cancelled": 0}).sort_values("week")
    wk = wk.merge(rw, on="week", how="outer").fillna({"orders": 0, "cancelled": 0, "refund": 0.0, "fee_refund": 0.0,
                                                      "refund_payout": 0.0})
    wk = wk.fillna({"revenue": 0.0, "seller_discount": 0.0, "platform_discount": 0.0, "fees": 0.0, "payout": 0.0})
    wk = wk.sort_values("week")
    nd = rf[rf["refund_day"].isna()]
    if not nd.empty:
        # возвраты без даты выписки — отдельной строкой в конце, чтобы недели вместе с ней сходились с плитками
        wk = pd.concat([wk, pd.DataFrame([{"week": pd.NaT, "orders": 0, "cancelled": 0, "revenue": 0.0,
                                           "seller_discount": 0.0, "platform_discount": 0.0, "fees": 0.0, "payout": 0.0,
                                           "paid": float("nan"), "refund": nd["revenue_amount"].sum(),
                                           "fee_refund": nd["fee_tax_amount"].sum(),
                                           "refund_payout": nd["settlement_amount"].sum()}])], ignore_index=True)
    _today = pd.Timestamp.now(tz=TZ).normalize().tz_localize(None)
    _last_full = min(pd.Timestamp(d_to), _today - pd.Timedelta(days=1))


    def week_label(w) -> str:
        if pd.isna(w):
            return t("tt.no_date")
        end = w + pd.Timedelta(days=6)
        lbl = f"{w:%d.%m} – {end:%d.%m.%Y}"
        return lbl + " · " + t("tt.partial") if end > _last_full or w < pd.Timestamp(d_from) else lbl


    # прочее с возврата (выплата по возврату минус возврат и возврат комиссии, например доставка) — колонкой, когда
    # оно есть: «К выплате» берёт выплату по возврату целиком, и без колонки строка на глаз разошлась бы на эту сумму
    wk["refund_other"] = wk["refund_payout"].fillna(0) - wk["refund"].fillna(0) - wk["fee_refund"].fillna(0)
    view = pd.DataFrame({
        t("tt.c.week"): wk["week"].map(week_label),
        t("tt.c.orders"): wk["orders"].astype(int),
        t("tt.c.cancelled"): wk["cancelled"].astype(int),
        t("tt.c.revenue"): wk["revenue"].round(2),
        t("tt.c.seller_discount"): wk["seller_discount"].round(2),
        t("tt.c.platform_discount"): wk["platform_discount"].round(2),
        t("tt.c.fees"): wk["fees"].fillna(0).round(2),
        t("tt.c.payout_sales"): wk["payout"].fillna(0).round(2),
        t("tt.c.refunds"): wk["refund"].fillna(0).round(2),
        t("tt.c.fee_refunds"): wk["fee_refund"].fillna(0).round(2),
        t("tt.c.payout"): (wk["payout"].fillna(0) + wk["refund_payout"].fillna(0)).round(2),
        # неделя без заказов (только возвраты или отмены) — доли нет, пусто, а не 0
        t("tt.c.paid_share"): (wk["paid"].where(wk["orders"] > 0) * 100).round(0),
    })
    if (wk["refund_other"].abs() >= 0.005).any():
        view.insert(view.columns.get_loc(t("tt.c.payout")), t("tt.c.refund_other"), wk["refund_other"].round(2) + 0.0)
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.caption(t("tt.weeks_note"))

    # ── по SKU ──
    st.subheader(t("tt.skus"))
    ln = lines[lines["order_id"].isin(real["order_id"])].copy()
    for c in ("sale_price", "platform_discount"):
        ln[c] = pd.to_numeric(ln[c], errors="coerce").fillna(0.0)
    ln["rev"] = ln["sale_price"] + ln["platform_discount"]
    sku = (ln.groupby("seller_sku").agg(name=("product_name", "first"), units=("order_id", "count"), revenue=("rev", "sum"),
                                        platform_discount=("platform_discount", "sum")).reset_index()
              .sort_values("revenue", ascending=False))
    sku["avg"] = sku["revenue"] / sku["units"]
    st.dataframe(pd.DataFrame({
        t("tt.c.sku"): sku["seller_sku"], t("tt.c.name"): sku["name"], t("tt.c.units"): sku["units"].astype(int),
        t("tt.c.revenue"): sku["revenue"].round(2), t("tt.c.avg"): sku["avg"].round(2),
        t("tt.c.platform_discount"): sku["platform_discount"].round(2)}), hide_index=True, use_container_width=True)

    # ── образцы ──
    st.subheader(t("tt.samples"))
    smp = o[o["sample"]]
    if smp.empty:
        st.caption(t("tt.none"))
    else:
        sl = lines[lines["order_id"].isin(smp["order_id"])]
        st.caption(t("tt.samples_n", n=len(smp)))
        st.dataframe(pd.DataFrame({
            t("tt.c.sku"): sl.groupby("seller_sku").size().index,
            t("tt.c.units"): sl.groupby("seller_sku").size().values}), hide_index=True, use_container_width=True)
        st.dataframe(pd.DataFrame({t("tt.c.status"): smp["status"].value_counts().index,
                                   t("tt.c.orders"): smp["status"].value_counts().values}), hide_index=True)

    refunds_block(rf)
    source_line(data["loaded_at"])


def eur0(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €".replace(",", " ")


def nodate_warning(rf) -> None:
    """Возврат без даты выписки не пропадает молча: предупреждение с числом и суммой (строка «без даты» — в неделях и
    в таблице возвратов)."""
    nd = rf[rf["refund_day"].isna()]
    if not nd.empty:
        st.warning(t("tt.refunds_nodate", n=len(nd), s=eur0(nd["revenue_amount"].sum())))


def refunds_block(rf) -> None:
    """Возвраты из финансов: те же строки, что у плитки «Возвраты» и колонки недель — по дате выписки возврата, без
    отмен и образцов; по дате возврата. Возвраты без даты выписки — в конце, с «без даты» в колонке даты."""
    st.subheader(t("tt.refunds"))
    if rf.empty:
        st.caption(t("tt.none"))
        return
    tbl = pd.DataFrame({
        t("tt.c.order"): rf["order_id"], t("tt.c.created"): pd.to_datetime(rf["day"]).dt.strftime("%d.%m.%Y"),
        t("tt.c.refund_day"): rf["refund_day"].dt.strftime("%d.%m.%Y").fillna(t("tt.no_date")),
        t("tt.c.status"): rf["status"], t("tt.c.refunds"): rf["revenue_amount"].round(2),
        t("tt.c.fee_refunds"): rf["fee_tax_amount"].round(2),
        t("tt.c.payout"): rf["settlement_amount"].round(2)})
    other = rf["settlement_amount"] - rf["revenue_amount"] - rf["fee_tax_amount"]
    if (other.abs() >= 0.005).any():
        tbl.insert(tbl.columns.get_loc(t("tt.c.payout")), t("tt.c.refund_other"), other.round(2) + 0.0)
    st.dataframe(tbl, hide_index=True, use_container_width=True)
    st.caption(t("tt.refunds_note"))


def source_line(_la) -> None:
    st.caption(t("tt.source", d=(pd.Timestamp(_la).tz_convert("Europe/Kyiv").strftime("%d.%m.%Y %H:%M")
                                  if _la is not None and not pd.isna(_la) else "—")))
