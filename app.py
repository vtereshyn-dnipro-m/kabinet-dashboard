import streamlit as st

st.set_page_config(
    page_title="Кабинет управления",
    page_icon="📊",
    layout="wide"
)

st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 4px; margin-bottom: 20px;">
        <img src="https://dnipro-m.ua/img/svgo/dnipro-M-logo.svg" width="160">
        <span style="
            background-color: #1a1a1a;
            color: white;
            font-weight: bold;
            font-size: 20px;
            padding: 2px 8px;
            border-radius: 4px;
        ">M</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("Кабинет управления")
st.caption("Консолидация остатков, продаж, товаров в пути · контроль инцидентов · ИИ-агенты")

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
        st.success(f"✅ Подключение к базе работает")
        st.code(version, language="text")
    except Exception as e:
        st.error(f"❌ Ошибка подключения к базе: {e}")
