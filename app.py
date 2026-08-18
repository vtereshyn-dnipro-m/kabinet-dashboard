# app.py — роутер + лого + переключатель языка + бейджи в сайдбаре
import streamlit as st
from i18n import init_lang, language_toggle, t
from db.connection import get_connection

init_lang()

st.set_page_config(
    page_title=t("app.page_title"),
    page_icon="📦",
    layout="wide",
)

# ---------- скрываем служебные элементы Streamlit Cloud ----------
# ВАЖНО: CSS собирается конкатенацией без переносов строк.
# Многострочный литерал с отступами Streamlit markdown принимает
# за блок кода и печатает CSS текстом на странице.
st.markdown(
    "<style>"
    # Панель инструментов НЕ скрываем целиком: внутри неё живёт кнопка
    # раскрытия свёрнутого сайдбара. display:none на предке выбрасывает
    # всё поддерево, и вернуть кнопку правилами на ней самой невозможно.
    # Гасим точечно только то, что действительно лишнее.
    '[data-testid="stToolbarActions"]{display:none !important;}'
    '[data-testid="stActionButtonIcon"]{display:none !important;}'
    '[data-testid="stAppDeployButton"]{display:none !important;}'
    '[data-testid="stMainMenu"]{display:none !important;}'
    '[data-testid="manage-app-button"]{display:none !important;}'
    '[data-testid="stStatusWidget"]{visibility:hidden;}'
    "header{background:transparent !important;}"
    "footer{visibility:hidden !important;}"
    # Streamlit оставляет сверху пустую полосу — заголовок проваливается
    # ниже логотипа в сайдбаре. Поджимаем на всех страницах разом.
    '[data-testid="stHeader"]{background:transparent !important;}'
    '[data-testid="stMainBlockContainer"]{padding-top:1rem !important;}'
    ".block-container{padding-top:1rem !important;}"
    '[data-testid="stHeader"]{height:2.2rem !important;}'
    '[data-testid="stAppViewContainer"] > .main{padding-top:0 !important;}'
    '[data-testid="stMain"]{padding-top:0 !important;}'
    "h1{margin-top:0 !important;padding-top:0 !important;}"
    # в сайдбаре между логотипом и пунктами меню остаётся пустая полоса —
    # поджимаем, чтобы навигация начиналась сразу под лого
    '[data-testid="stSidebarHeader"]{padding:0.6rem 1rem 0.2rem !important;}'
    '[data-testid="stSidebarUserContent"]{padding-top:0.4rem !important;}'
    '[data-testid="stSidebarNav"]{padding-top:0 !important;'
    "margin-top:0 !important;}"
    '[data-testid="stSidebarNav"] ul{padding-top:0 !important;}'
    'section[data-testid="stSidebar"] [data-testid="stLogo"]'
    "{margin-bottom:0.2rem !important;}"
    "</style>",
    unsafe_allow_html=True,
)

try:
    _dark = st.context.theme.type == "dark"
except Exception:
    _dark = True

st.logo("logo_dark.png" if _dark else "logo_light.png", size="large")
language_toggle()

pages = st.navigation({
    t("nav.section"): [
        st.Page("home.py", title=t("nav.home"), icon=":material/home:", default=True),
        st.Page("pages/1_Stock.py", title=t("nav.stock"), icon=":material/inventory_2:"),
        st.Page("pages/2_Incidents.py", title=t("nav.incidents"), icon=":material/warning:"),
        st.Page("pages/4_Reorder.py", title=t("nav.reorder"), icon=":material/shopping_cart:"),
        st.Page("pages/5_Money.py", title=t("nav.money"), icon=":material/payments:"),
        st.Page("pages/3_Forecast.py", title=t("nav.forecast"), icon=":material/show_chart:"),
        st.Page("pages/7_Reviews.py", title=t("nav.reviews"),
                icon=":material/rate_review:"),
        st.Page("pages/8_CM_Dashboard.py", title=t("nav.cm"),
                icon=":material/dashboard:"),
        st.Page("pages/6_Dictionaries.py", title=t("nav.dictionaries"),
                icon=":material/library_books:"),
    ],
})


# ---------- бейджи-счётчики в сайдбаре ----------
@st.cache_data(ttl=60)
def get_nav_badge_counts():
    """Открытых инцидентов и SKU к заказу (critical+warning) — для бейджей.

    Инциденты считаются по всем источникам: остатки, реклама, Leroy Merlin и т.д.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM kabinet_data.incidents WHERE status = 'open'")
            incidents = cur.fetchone()[0]
            cur.execute("""
                SELECT count(*) FROM kabinet_data.reorder_recommendations
                WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.reorder_recommendations)
                  AND urgency IN ('critical','warning')
                  AND COALESCE(order_status,'new') != 'ordered'
            """)
            reorder = cur.fetchone()[0]
        return {"incidents": incidents, "reorder": reorder}
    except Exception:
        return {"incidents": 0, "reorder": 0}
    finally:
        conn.close()


def inject_nav_badges(counts: dict):
    """Streamlit не поддерживает бейджи в st.Page нативно — добавляем через JS.
    Ищем ссылки в сайдбар-навигации по тексту и дописываем пилюлю справа."""
    import json
    labels_to_counts = {
        t("nav.incidents"): counts.get("incidents", 0),
        t("nav.reorder"): counts.get("reorder", 0),
    }
    payload = json.dumps({k: v for k, v in labels_to_counts.items() if v}, ensure_ascii=False)
    st.markdown(f"""
    <script>
    const badgeData = {payload};
    function applyNavBadges() {{
        const doc = window.parent.document;
        const links = doc.querySelectorAll('[data-testid="stSidebarNav"] a');
        links.forEach(link => {{
            const label = link.textContent.trim();
            for (const key in badgeData) {{
                if (label.includes(key)) {{
                    link.style.display = 'flex';
                    link.style.alignItems = 'center';
                    link.style.justifyContent = 'space-between';
                    let badge = link.querySelector('.nav-badge');
                    if (!badge) {{
                        badge = document.createElement('span');
                        badge.className = 'nav-badge';
                        badge.style.cssText = 'margin-left:auto;background:#F7C1C1;color:#791F1F;font-size:11px;font-weight:600;padding:1px 8px;border-radius:10px;';
                        link.appendChild(badge);
                    }}
                    badge.textContent = badgeData[key];
                }}
            }}
        }});
    }}
    if (window.__navBadgeObserver) window.__navBadgeObserver.disconnect();
    window.__navBadgeObserver = new MutationObserver(applyNavBadges);
    window.__navBadgeObserver.observe(window.parent.document.body, {{childList: true, subtree: true}});
    applyNavBadges();
    </script>
    """, unsafe_allow_html=True)


inject_nav_badges(get_nav_badge_counts())
pages.run()
