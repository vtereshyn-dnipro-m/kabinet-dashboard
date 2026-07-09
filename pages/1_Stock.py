import streamlit as st
import pandas as pd
from db.connection import run_query

st.set_page_config(page_title="Остатки", page_icon="📦", layout="wide")

st.title("Остатки")
st.caption("Консолидация по складам: Amazon FBA + собственные/3PL")

col1, col2, col3 = st.columns(3)
with col1:
    warehouse_filter = st.text_input("Склад (часть названия)", "")
with col2:
    sku_filter = st.text_input("SKU / артикул", "")
with col3:
    status_filter = st.selectbox(
        "Статус доступности",
        ["Все", "available", "transit", "reserve", "inbound", "quarantine"]
    )

query = """
    SELECT
        sku,
        product_name,
        warehouse_name,
        warehouse_country,
        snapshot_date,
        availability_status,
        quality_status,
        quantity,
        sync_status
    FROM kabinet_data.stock_local
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
"""

try:
    df = run_query(query)

    if warehouse_filter:
        df = df[df["warehouse_name"].str.contains(warehouse_filter, case=False, na=False)]
    if sku_filter:
        df = df[df["sku"].str.contains(sku_filter, case=False, na=False)]
    if status_filter != "Все":
        df = df[df["availability_status"] == status_filter]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Всего SKU", df["sku"].nunique())
    m2.metric("Складов", df["warehouse_name"].nunique())
    m3.metric("Суммарный остаток", int(df["quantity"].sum()))
    sync_errors = (df["sync_status"] == "sync_error").sum()
    m4.metric("Ошибок синка", sync_errors, delta_color="inverse")

    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Не удалось загрузить данные: {e}")
    st.info(
        "Убедитесь, что таблица `kabinet_data.stock_local` создана и в неё уже "
        "загружены данные лоадером (Databricks → Lakebase)."
    )
