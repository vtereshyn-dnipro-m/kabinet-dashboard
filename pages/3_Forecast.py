import streamlit as st
from db.connection import run_query

st.set_page_config(page_title="Прогноз", page_icon="📈", layout="wide")

st.title("Прогноз")
st.caption("Прогноз спроса и рекомендации по дозаказу")

query = """
    SELECT
        sku,
        warehouse_name,
        quantity AS current_stock,
        avg_daily_sales,
        lead_time_days,
        ROUND(quantity / NULLIF(avg_daily_sales, 0), 1) AS days_of_stock,
        suggested_qty,
        status,
        created_at
    FROM kabinet_data.draft_orders
    ORDER BY created_at DESC
"""

try:
    df = run_query(query)

    if not df.empty:
        at_risk = df[df["days_of_stock"] < df["lead_time_days"]]
        st.metric("Товаров в зоне риска", len(at_risk))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Пока нет данных для прогноза.")

except Exception as e:
    st.error(f"Не удалось загрузить прогноз: {e}")
    st.info("Таблица `kabinet_data.draft_orders` появится после запуска агента автозаказов.")
