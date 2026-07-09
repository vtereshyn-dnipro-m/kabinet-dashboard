# home.py — главная страница
import streamlit as st

st.title("Кабинет Demand & Supply")
st.caption("Управление запасами и спросом: остатки · инциденты · прогноз · ИИ-агенты")
st.markdown(
    """
    Используйте меню слева для перехода между разделами:
    - **Остатки** — консолидированные остатки по всем складам (Amazon FBA + собственные/3PL)
    - **Инциденты** — алерты по рискам (низкий запас, зависшие поставки, аномалии продаж)
    - **Прогноз** — прогноз спроса и рекомендации по дозаказу
    """
)
with st.expander("Статус подключения"):
    try:
        from db.connection import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        st.success("✅ Подключение к базе работает")
        st.code(version, language="text")
    except Exception as e:
        st.error(f"❌ Ошибка подключения к базе: {e}")
