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


@st.cache_data(ttl=300)
def fee_split_exists() -> bool:
    """Колонки раскладки комиссий в реплике операций (sql/tiktok_fee_split_2026-10-25.sql) уже есть."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT count(*) FROM information_schema.columns WHERE table_schema = 'kabinet_data'
                         AND table_name = 'raw_tiktok_finance_tx' AND column_name IN
                         ('commission_tiktok', 'commission_affiliate', 'fee_other')""")
        return int(cur.fetchone()[0]) == 3
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_requests(d_from, d_to, ver: str = "") -> dict:
    """Заявки на возврат и отмены за период — по дате создания заявки (Мадрид), из реплик raw_tiktok_returns и
    raw_tiktok_cancellations (27.10.2026). Операционная картина: деньги по заявкам в выручку и «К выплате» не входят
    (там — возвраты по выпискам). Реплики ещё нет — None, а не пустой кадр: «заявок нет» и «не загружены» — разное."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('kabinet_data.raw_tiktok_returns') IS NOT NULL "
                    "AND to_regclass('kabinet_data.raw_tiktok_cancellations') IS NOT NULL")
        if not cur.fetchone()[0]:
            return {"returns": None, "cancels": None}
        q = {"a": d_from, "b": d_to}
        # заглушка позиции «#…» — только у возврата без настоящих позиций (docs/tiktok-shop.md): upsert реплики ничего не
        # удаляет, и заглушка могла остаться рядом с позициями, пришедшими позже. У возврата без позиций («#0») суммы по
        # позиции нет — берём сумму возврата целиком
        returns = pd.read_sql("""
            SELECT r.return_id, r.order_id, (r.create_time AT TIME ZONE 'Europe/Madrid')::date AS day, r.return_type,
                   r.return_status, r.return_reason_text, r.seller_sku, r.product_name,
                   CASE WHEN r.return_line_item_id = '#0' THEN coalesce(r.refund_total, r.return_refund_total)
                        ELSE r.refund_total END AS refund_total,
                   r.seller_paid_return_shipping_fee
            FROM kabinet_data.raw_tiktok_returns r
            WHERE (r.create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s
              AND NOT (left(r.return_line_item_id, 1) = '#' AND EXISTS (
                  SELECT 1 FROM kabinet_data.raw_tiktok_returns x
                  WHERE x.shop_id = r.shop_id AND x.return_id = r.return_id AND left(x.return_line_item_id, 1) <> '#'))
            ORDER BY r.create_time, r.return_id, r.return_line_item_id""", conn, params=q)
        cancels = pd.read_sql("""
            SELECT c.cancel_id, c.order_id, (c.create_time AT TIME ZONE 'Europe/Madrid')::date AS day, c.cancel_status,
                   c.cancel_reason_text, c.role, c.seller_sku
            FROM kabinet_data.raw_tiktok_cancellations c
            WHERE (c.create_time AT TIME ZONE 'Europe/Madrid')::date BETWEEN %(a)s AND %(b)s
              AND NOT (left(c.cancel_line_item_id, 1) = '#' AND EXISTS (
                  SELECT 1 FROM kabinet_data.raw_tiktok_cancellations x
                  WHERE x.shop_id = c.shop_id AND x.cancel_id = c.cancel_id AND left(x.cancel_line_item_id, 1) <> '#'))""",
                              conn, params=q)
    finally:
        conn.close()
    return {"returns": returns, "cancels": cancels}


@st.cache_data(ttl=600)
def load(d_from, d_to, ver: str = "", split: bool = False) -> dict:
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
        tx = pd.read_sql(f"""
            SELECT x.order_id, x.statement_time, x.payment_status, x.revenue_amount, x.fee_tax_amount, x.settlement_amount
                   {", x.commission_tiktok, x.commission_affiliate, x.fee_other" if split else ""}
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
        data = load(d_from, d_to, data_version("raw_tiktok_orders", "loaded_at"), fee_split_exists())
    except Exception as e:
        st.error(f"{t('tt.db_error')}: {e}")
        return

    st.caption(t("tt.as_of", d=as_of(data["loaded_at"])))
    o, lines, tx = data["orders"], data["lines"], data["tx"]
    # возвраты идут по дате выписки возврата, поэтому у периода без заказов они могут быть — их показываем всё равно
    rf = data["refunds"].copy()
    for c in ("revenue_amount", "fee_tax_amount", "settlement_amount"):
        rf[c] = pd.to_numeric(rf[c], errors="coerce").fillna(0.0)
    rf["refund_day"] = pd.to_datetime(rf["refund_day"])
    rf["week"] = rf["refund_day"] - pd.to_timedelta(rf["refund_day"].dt.weekday, unit="D")
    rf = rf.sort_values(["refund_day", "order_id"], na_position="last")
    # прочее по возврату — выплата по возврату минус возврат и возврат комиссии (например доставка). «К выплате» берёт
    # выплату по возврату целиком, поэтому, если прочее есть хоть у одного возврата периода, оно показано плиткой,
    # колонкой в неделях и в таблице возвратов — по одному условию
    rf["other"] = rf["settlement_amount"] - rf["revenue_amount"] - rf["fee_tax_amount"]
    has_other = bool((rf["other"].abs() >= 0.005).any())
    if o.empty:
        st.info(t("tt.empty"))
        if not rf.empty:
            nodate_warning(rf)
            k = st.columns(4 if has_other else 3)
            k[0].metric(t("tt.k.refunds"), eur0(rf["revenue_amount"].sum()))
            k[1].metric(t("tt.k.fee_refunds"), eur0(rf["fee_tax_amount"].sum()))
            if has_other:
                k[2].metric(t("tt.k.refund_other"), eur0(rf["other"].sum()))
            k[-1].metric(t("tt.k.payout"), eur0(rf["settlement_amount"].sum()), help=t("tt.k.payout_help"))
            st.caption(t("tt.refunds_line"))
            refunds_block(rf, has_other)
        requests_block(d_from, d_to)
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
    # раскладка комиссий (TikTok, аффилиаты, прочие сборы) — только если колонки есть и заполнены у всех операций продажи:
    # иначе (SQL не применён или загрузчик ещё не дописал колонки) — одной колонкой, как раньше
    SPLIT = ("commission_tiktok", "commission_affiliate", "fee_other")
    split_ok = all(c in sale.columns for c in SPLIT) and not sale[list(SPLIT)].isna().any().any() if not sale.empty else False
    if split_ok:
        sale = sale.copy()
        for c in SPLIT:
            sale[c] = pd.to_numeric(sale[c], errors="coerce").fillna(0.0)
    agg = {"fee": ("fee_tax_amount", "sum"), "payout": ("settlement_amount", "sum")}
    if split_ok:
        agg.update({"fee_tt": ("commission_tiktok", "sum"), "fee_aff": ("commission_affiliate", "sum"),
                    "fee_oth": ("fee_other", "sum")})
    by_order = sale.groupby("order_id").agg(**agg).reset_index()
    real = real.merge(by_order, on="order_id", how="left")
    real["paid"] = real["payout"].notna()

    nodate_warning(rf)
    # срез — словами над плитками (28.10.2026): «57» за 01.10–27.10 и «59» за 30 дней (28.09–27.10) — оба верны, но без
    # периода и отсева рядом с числом выглядели расхождением
    st.caption(t("tt.slice", a=d_from.strftime("%d.%m.%Y"), b=d_to.strftime("%d.%m.%Y"), n=len(real),
                 c=int((o["cancelled"] & ~o["sample"]).sum()), s=int(o["sample"].sum())))
    # ── плитки: два ряда, в целых евро (центы — в таблицах ниже) ──
    k = st.columns(4)
    k[0].metric(t("tt.k.orders"), f"{len(real)}")
    k[1].metric(t("tt.k.revenue"), eur0(real["seller_rev"].sum()))
    k[2].metric(t("tt.k.seller_discount"), eur0(real["seller_discount"].sum()))
    k[3].metric(t("tt.k.platform_discount"), eur0(real["platform_discount"].sum()))
    k = st.columns(6 if has_other else 5)
    k[0].metric(t("tt.k.fees"), eur0(real["fee"].fillna(0).sum()),
                help=t("tt.k.fees_help", a=eur0(real["fee_tt"].fillna(0).sum()), b=eur0(real["fee_aff"].fillna(0).sum()),
                       c=eur0(real["fee_oth"].fillna(0).sum())) if split_ok else None)
    k[1].metric(t("tt.k.refunds"), eur0(rf["revenue_amount"].sum()))
    k[2].metric(t("tt.k.fee_refunds"), eur0(rf["fee_tax_amount"].sum()))
    if has_other:
        k[3].metric(t("tt.k.refund_other"), eur0(rf["other"].sum()))
    k[-2].metric(t("tt.k.payout"), eur0(real["payout"].fillna(0).sum() + rf["settlement_amount"].sum()),
                 help=t("tt.k.payout_help"))
    k[-1].metric(t("tt.k.paid_share"), f"{real['paid'].mean() * 100:.0f} %" if len(real) else "—")
    st.caption(t("tt.vat_note"))
    st.caption(t("tt.refunds_line"))

    # ── по неделям ──
    st.subheader(t("tt.weeks"))
    real["week"] = real["day"] - pd.to_timedelta(real["day"].dt.weekday, unit="D")
    o["week"] = o["day"] - pd.to_timedelta(o["day"].dt.weekday, unit="D")
    wk = real.groupby("week").agg(orders=("order_id", "count"), revenue=("seller_rev", "sum"),
                                  seller_discount=("seller_discount", "sum"), platform_discount=("platform_discount", "sum"),
                                  fees=("fee", "sum"), payout=("payout", "sum"), paid=("paid", "mean"),
                                  **({"fee_tt": ("fee_tt", "sum"), "fee_aff": ("fee_aff", "sum"), "fee_oth": ("fee_oth", "sum")}
                                     if split_ok else {})).reset_index()
    rw = rf[rf["refund_day"].notna()].groupby("week").agg(refund=("revenue_amount", "sum"), fee_refund=("fee_tax_amount", "sum"),
                                                          refund_payout=("settlement_amount", "sum")).reset_index()
    canc = o[o["cancelled"] & ~o["sample"]].groupby("week").size().rename("cancelled").reset_index()
    wk = wk.merge(canc, on="week", how="outer").fillna({"orders": 0, "cancelled": 0}).sort_values("week")
    wk = wk.merge(rw, on="week", how="outer").fillna({"orders": 0, "cancelled": 0, "refund": 0.0, "fee_refund": 0.0,
                                                      "refund_payout": 0.0})
    wk = wk.fillna({"revenue": 0.0, "seller_discount": 0.0, "platform_discount": 0.0, "fees": 0.0, "payout": 0.0,
                    "fee_tt": 0.0, "fee_aff": 0.0, "fee_oth": 0.0})
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


    # прочее по возвратам недели — колонкой при том же условии, что плитка (has_other)
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
    if has_other:
        view.insert(view.columns.get_loc(t("tt.c.payout")), t("tt.c.refund_other"), wk["refund_other"].round(2) + 0.0)
    if split_ok:
        # комиссии тремя колонками вместо одной; в сумме — та же «Комиссии, €»
        _at = view.columns.get_loc(t("tt.c.fees"))
        view = view.drop(columns=[t("tt.c.fees")])
        for _i, (_k, _c) in enumerate((("tt.c.fee_tt", "fee_tt"), ("tt.c.fee_aff", "fee_aff"), ("tt.c.fee_oth", "fee_oth"))):
            view.insert(_at + _i, t(_k), wk[_c].fillna(0).round(2) + 0.0)
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

    refunds_block(rf, has_other)
    requests_block(d_from, d_to)
    source_line(data["loaded_at"])


def requests_block(d_from, d_to) -> None:
    """Заявки на возврат (по позициям) и отмены за период — по дате заявки. Деньги здесь — сумма заявки, а не выплата:
    в плитки, недели и «К выплате» они не входят (возврат учитывается по выписке, решение владельца 27.10.2026)."""
    st.subheader(t("tt.requests"))
    try:
        req = load_requests(d_from, d_to, data_version("raw_tiktok_returns", "loaded_at"))
    except Exception as e:
        st.error(t("tt.requests_error", e=f"{type(e).__name__}: {str(e)[:150]}"))
        return
    rq, cn = req["returns"], req["cancels"]
    if rq is None:
        st.caption(t("tt.requests_no_replica"))
        return
    st.caption(t("tt.requests_note"))
    if rq.empty:
        st.caption(t("tt.requests_none"))
    else:
        for c in ("refund_total", "seller_paid_return_shipping_fee"):
            rq[c] = pd.to_numeric(rq[c], errors="coerce")
        # обратная доставка — на возврат целиком, а не на позицию: показываем один раз, в первой строке возврата
        rq.loc[rq["return_id"].duplicated(), "seller_paid_return_shipping_fee"] = float("nan")
        st.dataframe(pd.DataFrame({
            t("tt.c.order"): rq["order_id"], t("tt.c.created"): pd.to_datetime(rq["day"]).dt.strftime("%d.%m.%Y"),
            t("tt.c.status"): rq["return_status"], t("tt.c.return_type"): rq["return_type"],
            t("tt.c.reason"): rq["return_reason_text"], t("tt.c.sku"): rq["seller_sku"], t("tt.c.name"): rq["product_name"],
            t("tt.c.requested"): rq["refund_total"].round(2),
            t("tt.c.seller_shipping"): rq["seller_paid_return_shipping_fee"].round(2)}), hide_index=True,
            use_container_width=True)
    if cn.empty:
        st.caption(t("tt.cancels_none"))
    else:
        by = (cn.groupby(["cancel_reason_text", "role"], dropna=False)["cancel_id"].nunique()
                .rename("n").reset_index().sort_values("n", ascending=False))
        st.caption(t("tt.cancels_n", n=int(cn["cancel_id"].nunique())))
        st.dataframe(pd.DataFrame({t("tt.c.reason"): by["cancel_reason_text"].fillna("—"),
                                   t("tt.c.role"): by["role"].fillna("—"), t("tt.c.orders"): by["n"].astype(int)}),
                     hide_index=True)


def eur0(v) -> str:
    # round(…) + 0.0 — без «-0 €», когда сумма округляется к нулю с минусом
    return "—" if v is None or pd.isna(v) else f"{round(float(v)) + 0.0:,.0f} €".replace(",", " ")


def nodate_warning(rf) -> None:
    """Возврат без даты выписки не пропадает молча: предупреждение с числом и суммой (строка «без даты» — в неделях и
    в таблице возвратов)."""
    nd = rf[rf["refund_day"].isna()]
    if not nd.empty:
        st.warning(t("tt.refunds_nodate", n=len(nd), s=eur0(nd["revenue_amount"].sum())))


def refunds_block(rf, has_other: bool) -> None:
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
    if has_other:
        tbl.insert(tbl.columns.get_loc(t("tt.c.payout")), t("tt.c.refund_other"), rf["other"].round(2) + 0.0)
    st.dataframe(tbl, hide_index=True, use_container_width=True)
    st.caption(t("tt.refunds_note"))


def as_of(_la) -> str:
    """«ДД.ММ ЧЧ:ММ» (Киев) последней загрузки реплики или «—»."""
    return pd.Timestamp(_la).tz_convert("Europe/Kyiv").strftime("%d.%m %H:%M") if _la is not None and not pd.isna(_la) else "—"


def source_line(_la) -> None:
    st.caption(t("tt.source", d=(pd.Timestamp(_la).tz_convert("Europe/Kyiv").strftime("%d.%m.%Y %H:%M")
                                  if _la is not None and not pd.isna(_la) else "—")))
