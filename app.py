# app.py — роутер + лого
import streamlit as st

st.set_page_config(
    page_title="Кабинет Demand & Supply — Dnipro-M",
    page_icon="📦",
    layout="wide",
)

# Лого в сайдбаре: белая "M" для тёмной темы, чёрная для светлой
try:
    theme = st.context.theme.type  # "light" | "dark"
except Exception:
    theme = "light"

logo_file = "logo_dark.webp" if theme == "dark" else "Dnipro-M_logo.svg.webp"
st.logo(logo_file, size="large")

pages = st.navigation({
    "Кабинет Demand & Supply": [
        st.Page("home.py", title="Обзор", icon="🏠", default=True),
        st.Page("pages/1_Stock.py", title="Остатки", icon="📦"),
        st.Page("pages/2_Incidents.py", title="Инциденты", icon="🚨"),
        st.Page("pages/3_Forecast.py", title="Прогноз", icon="📈"),
    ],
})
pages.run()
