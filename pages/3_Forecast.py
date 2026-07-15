# pages/3_Forecast.py
import streamlit as st
from db.connection import run_query
from i18n import init_lang, t

init_lang()

st.title(t("fc.title"))
st.caption(t("fc.caption"))

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
        st.metric(t("fc.kpi.at_risk"), len(at_risk),
                  help=t("fc.kpi.at_risk_help"))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(t("fc.empty_title"))
        st.markdown(t("fc.empty_body"))
except Exception as e:
    st.error(t("fc.load_error").format(e=e))
