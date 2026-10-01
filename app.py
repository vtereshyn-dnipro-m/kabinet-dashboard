# app.py — роутер + лого + переключатель языка + бейджи в сайдбаре
import streamlit as st
from i18n import init_lang, language_toggle, t
from db.connection import get_connection
import auth

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
    # Подписи метрик Streamlit режет многоточием в одну строку: в шести
    # колонках «Продажи по заказам» превращается в «Продажи по зака…».
    # Разрешаем перенос по словам — подпись занимает две строки, но
    # читается целиком. Правило одно на все страницы, потому что метрики
    # в узких колонках есть на восьми из них.
    '[data-testid="stMetricLabel"]{white-space:normal !important;}'
    '[data-testid="stMetricLabel"] p{white-space:normal !important;'
    "overflow:visible !important;text-overflow:clip !important;"
    "line-height:1.2 !important;}"
    '[data-testid="stMetricLabel"] > div{overflow:visible !important;}'
    # ...но переносить надо ПО СЛОВАМ. По умолчанию перенос рвёт слово в любом
    # месте, и на 1100 px подписи превращались в «Прода жи по заказа м» и
    # «Дней у старе йшего» — читается хуже обрезанной строки. Запрещаем разрыв
    # внутри слова и переносы по дефису; вместо этого подпись мельчает через
    # clamp, пока не уместится. Правило на подпись и на её <p> разом: Streamlit
    # ставит стиль на оба, и одного элемента не хватает.
    '[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p,'
    '[data-testid="stMetricLabel"] div{word-break:normal !important;'
    "overflow-wrap:normal !important;hyphens:none !important;}"
    '[data-testid="stMetricLabel"] p{'
    "font-size:clamp(0.66rem,0.55vw + 0.42rem,0.82rem) !important;}"
    # Длинный артикул или ASIN в подписи — единственное слово, которое всё
    # равно не уместится: ему разрыв разрешён, иначе он вылезет за карточку.
    '[data-testid="stMetricLabel"] p code{overflow-wrap:anywhere !important;}'
    # в сайдбаре между логотипом и пунктами меню остаётся пустая полоса —
    # поджимаем, чтобы навигация начиналась сразу под лого
    '[data-testid="stSidebarHeader"]{padding:0.6rem 1rem 0.2rem !important;}'
    '[data-testid="stSidebarUserContent"]{padding-top:0.4rem !important;}'
    '[data-testid="stSidebarNav"]{padding-top:0 !important;'
    "margin-top:0 !important;}"
    '[data-testid="stSidebarNav"] ul{padding-top:0 !important;}'
    'section[data-testid="stSidebar"] [data-testid="stLogo"]'
    "{margin-bottom:0.2rem !important;}"
    # Подсказка «?» по умолчанию тянется до 672px и привязана к иконке.
    # У метрики в правой колонке такая ширина уезжает за левый край экрана,
    # и половина текста не читается. Узкая подсказка переносится по строкам
    # и помещается при любой ширине окна.
    '[data-testid="stTooltipContent"]{max-width:340px !important;}'
    # Неактивная вкладка получает display:none, и всё внутри неё имеет
    # нулевую ширину. st.dataframe считает ширины колонок один раз при
    # монтировании — то есть по нулю — и кэширует их. При переходе на
    # вкладку canvas растягивается, а колонки остаются схлопнутыми, и
    # таблица выглядит одной колонкой, пока ресайз окна не заставит
    # пересчитать. Держим скрытые панели выложенными и полной ширины,
    # но убранными с экрана: тогда ширины считаются сразу правильно.
    '[data-testid="stTabs"]{position:relative !important;}'
    '[data-testid="stTabPanel"][inert]{display:block !important;'
    "position:absolute !important;left:-99999px !important;top:0 !important;"
    "width:100% !important;visibility:hidden !important;"
    "pointer-events:none !important;}"
    "</style>",
    unsafe_allow_html=True,
)

try:
    _dark = st.context.theme.type == "dark"
except Exception:
    _dark = True

st.logo("logo_dark.png" if _dark else "logo_light.png", size="large")

# Ворота стоят ЗДЕСЬ — раньше, чем читается хоть одна бизнес-таблица, и раньше
# навигации. Страницы собраны через st.navigation, поэтому любой URL проходит через
# app.py, и прямая ссылка на /Forecast закрывается этой же проверкой. Если навигацию
# когда-нибудь заменят на автоматическую (папка pages/ без роутера), страницы станут
# самостоятельными точками входа, и guard() придётся звать в начале каждой.
auth.guard()

language_toggle()
auth.header()

# ---------- навигация по правам ----------
# Список страниц объявлен в auth.PAGES: видимость страницы — такое же право, как любое
# другое, и держать два списка (страниц и прав) значило бы однажды их разойтись.
#
# Страница, которую роли видеть нельзя, НЕ исчезает из навигации — она становится
# скрытой заглушкой с тем же адресом. Разница существенная: просто убрать её из списка
# значило бы, что по прямой ссылке Streamlit покажет своё «Page not found» и молча
# перебросит на главную, а человек должен получить ОТКАЗ и понять, что страница есть,
# но ему закрыта.
def _адрес(файл: str) -> str:
    """Адрес страницы в ссылке — тот же, что Streamlit выводит из имени файла:
    отбрасывает путь, числовой префикс и расширение. `pages/1_Stock.py` → `Stock`.
    Нужен затем, чтобы заглушка отвечала по ТОМУ ЖЕ адресу, что и сама страница."""
    import re as _re
    имя = файл.rsplit("/", 1)[-1]
    if имя.endswith(".py"):
        имя = имя[:-3]
    return _re.sub(r"^\d+_", "", имя)


def _отказ():
    st.title(t("auth.page_closed_title"))
    st.error(t("auth.page_closed"))
    st.caption(t("auth.page_closed_hint"))


_видимые = [(к, ф, п, з) for к, ф, п, з in auth.PAGES if auth.can("page." + к)]
_закрытые = [(к, ф, п, з) for к, ф, п, з in auth.PAGES if not auth.can("page." + к)]

if not _видимые and not auth.can("admin"):
    # Ни одной открытой страницы — показываем отказ целиком, а не пустое меню
    _отказ()
    st.stop()

_список = []
for _i, (_к, _ф, _п, _з) in enumerate(_видимые):
    _список.append(st.Page(_ф, title=t(_п), icon=_з, default=(_i == 0)))
for _к, _ф, _п, _з in _закрытые:
    # visibility="hidden": из меню убрана, но адрес живёт и отвечает отказом
    _список.append(st.Page(_отказ, title=t(_п), icon=_з,
                           url_path=_адрес(_ф), visibility="hidden"))

# Админка — только администраторам. Скрытый пункт меню сам по себе не защита, поэтому
# на самой странице стоит своя проверка: туда можно прийти по прямой ссылке, и решает
# именно она, а не отсутствие ссылки в сайдбаре.
if auth.can("admin"):
    _список.append(st.Page("pages/10_Access.py", title=t("auth.admin.title"),
                           icon=":material/lock:"))

pages = st.navigation({t("nav.section"): _список})


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
