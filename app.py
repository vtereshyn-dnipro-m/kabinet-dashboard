# app.py — роутер (st.navigation)
import streamlit as st

st.set_page_config(
    page_title="Кабинет Demand & Supply — Dnipro-M",
    page_icon="📦",
    layout="wide",
)

pages = st.navigation({
    "Кабинет Demand & Supply": [
        st.Page("home.py", title="Обзор", icon="🏠", default=True),
        st.Page("pages/1_Stock.py", title="Остатки", icon="📦"),
        st.Page("pages/2_Incidents.py", title="Инциденты", icon="🚨"),
        st.Page("pages/3_Forecast.py", title="Прогноз", icon="📈"),
    ],
})
pages.run()
