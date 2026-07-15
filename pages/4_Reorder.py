# ═════════════════════════════════════════════════════════════
# СЕКЦИЯ «ПЕРЕБРОСКА МЕЖДУ СТРАНАМИ» для pages/4_Reorder.py
# Вставить ПОСЛЕ блока KPI (после st.divider() за метриками),
# ПЕРЕД фильтрами таблицы заказа.
# Логика: сначала переброска со своих складов, потом заказ у поставщика.
# ═════════════════════════════════════════════════════════════
from i18n import t  # уже должен быть импортирован в шапке файла вместе с init_lang()

@st.cache_data(ttl=120)
def load_transfers():
    conn = get_connection()
    df = pd.read_sql("""
        SELECT sku, product_name, from_location, to_location, transfer_qty,
               from_stock, from_cover_days, to_stock, to_cover_days,
               COALESCE(status, 'new') AS status
        FROM kabinet_data.transfer_recommendations
        WHERE calc_date = (SELECT MAX(calc_date)
                           FROM kabinet_data.transfer_recommendations)
    """, conn)
    conn.close()
    return df

def set_transfer_status(keys, new_status):
    """keys: list of (sku, from_location, to_location)"""
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT MAX(calc_date) FROM kabinet_data.transfer_recommendations")
    d = cur.fetchone()[0]
    for sku, fl, tl in keys:
        cur.execute("""
            UPDATE kabinet_data.transfer_recommendations
            SET status = %s
            WHERE calc_date = %s AND sku = %s
              AND from_location = %s AND to_location = %s
        """, (new_status, d, sku, fl, tl))
    conn.commit(); cur.close(); conn.close()

transfers = load_transfers()
active_tr = transfers[transfers["status"] == "new"]

if not active_tr.empty:
    col_confirm = t("reorder.transfer.col_confirm")
    col_sku = t("reorder.transfer.col_sku")
    col_product = t("reorder.transfer.col_product")
    col_route = t("reorder.transfer.col_route")
    col_qty = t("reorder.transfer.col_qty")
    col_from_stock = t("reorder.transfer.col_from_stock")
    col_to_cover = t("reorder.transfer.col_to_cover")
    unit = t("reorder.transfer.unit_pcs")

    st.markdown(f"#### {t('reorder.transfer.section_title')}")
    st.caption(t("reorder.transfer.section_caption"))

    tr = active_tr.copy()
    tr.insert(0, col_confirm, True)
    tr[col_route] = tr["from_location"] + " → " + tr["to_location"]
    tr[col_from_stock] = tr["from_stock"].astype(int).astype(str) + f" {unit}"
    tr[col_to_cover] = tr["to_cover_days"].round(0).astype(int)

    tr_edited = st.data_editor(
        tr[[col_confirm, "sku", "product_name", col_route, "transfer_qty",
            col_from_stock, col_to_cover]],
        use_container_width=True, hide_index=True,
        column_config={
            col_confirm: st.column_config.CheckboxColumn(col_confirm, width="small"),
            "sku": st.column_config.TextColumn(col_sku, width="small", disabled=True),
            "product_name": st.column_config.TextColumn(col_product, width="large", disabled=True),
            col_route: st.column_config.TextColumn(col_route, width="small", disabled=True),
            "transfer_qty": st.column_config.NumberColumn(
                col_qty, width="small", min_value=0, step=1),
            col_from_stock: st.column_config.TextColumn(
                col_from_stock, width="small", disabled=True),
            col_to_cover: st.column_config.NumberColumn(
                col_to_cover, width="small", disabled=True,
                help=t("reorder.transfer.col_to_cover_help")),
        },
        key="transfer_editor",
    )

    chosen_tr = tr_edited[tr_edited[col_confirm]]
    tc1, tc2 = st.columns([1, 1])
    with tc1:
        if st.button(t("reorder.transfer.confirm_button").format(n=len(chosen_tr)),
                     use_container_width=True, disabled=chosen_tr.empty):
            keys = [(r["sku"],) + tuple(r[col_route].split(" → "))
                    for _, r in chosen_tr.iterrows()]
            set_transfer_status(keys, "confirmed")
            st.cache_data.clear()
            st.success(t("reorder.transfer.confirm_success").format(n=len(chosen_tr)))
            st.rerun()
    with tc2:
        st.download_button(
            t("reorder.transfer.export_button"),
            chosen_tr.to_csv(index=False).encode("utf-8-sig")
            if not chosen_tr.empty else b"",
            file_name="transfers.csv", mime="text/csv",
            use_container_width=True, disabled=chosen_tr.empty,
        )
    st.divider()
