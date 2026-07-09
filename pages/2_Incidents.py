import streamlit as st
from db.connection import run_query

st.set_page_config(page_title="Инциденты", page_icon="🚨", layout="wide")

st.title("Инциденты")
st.caption("Алерты по рискам: низкий запас, зависшие поставки, аномалии продаж")

query = """
    SELECT
        created_at,
        incident_type,
        sku,
        warehouse_name,
        severity,
        message,
        status
    FROM kabinet_data.incidents
    ORDER BY created_at DESC
    LIMIT 200
"""

try:
    df = run_query(query)

    col1, col2 = st.columns(2)
    with col1:
        severity_filter = st.multiselect(
            "Уровень серьёзности",
            options=df["severity"].unique().tolist() if not df.empty else [],
            default=df["severity"].unique().tolist() if not df.empty else []
        )
    with col2:
        status_filter = st.multiselect(
            "Статус",
            options=df["status"].unique().tolist() if not df.empty else [],
            default=df["status"].unique().tolist() if not df.empty else []
        )

    if not df.empty:
        df = df[df["severity"].isin(severity_filter) & df["status"].isin(status_filter)]

    open_count = (df["status"] == "open").sum() if not df.empty else 0
    st.metric("Открытых инцидентов", open_count)

    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Не удалось загрузить инциденты: {e}")
    st.info("Таблица `kabinet_data.incidents` пока не создана или пуста.")
