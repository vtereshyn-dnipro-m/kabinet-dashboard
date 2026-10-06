# auth.py — вход через Google и права по ролям (ТЗ 010)
"""Одно место, где решается «кто это и что ему можно».

Главное в устройстве — не экран входа, а то, что проверка вызывается **в обработчике
действия**, а не только при отрисовке. Скрытая кнопка — удобство; защита — отказ в
момент записи. Поэтому `can()` отвечает на вопрос «показывать ли», а `require()` —
«выполнять ли», и второй ещё и оставляет след в журнале, включая отказ.

Прямые ссылки закрыты тем, что страницы собраны через `st.navigation` в `app.py`:
любой URL проходит через него, и `guard()` там стоит раньше, чем читается хоть одна
бизнес-таблица. Если навигацию когда-нибудь заменят на автоматическую (папка `pages/`
без роутера), страницы станут самостоятельными точками входа — и `guard()` придётся
звать в начале каждой. Это записано здесь, потому что снаружи такая замена выглядит
безобидной перестановкой.

Режим входа живёт в базе (`reorder_params.auth_enabled`), а не в коде, и значений три:

    2 — раскатка: входа нет, кнопки у всех, как было до этой работы;
    1 — вход обязателен, роли работают;
    0 — авария: входа нет, у всех «Просмотр». Сюда переводят, если ляжет Google OAuth.

Средний режим нужен именно потому, что деплой и включение входа — разные моменты:
без него кнопки пропали бы у всех ещё до того, как вход вообще включили.
"""
import streamlit as st

from db.connection import get_connection
from i18n import t, get_lang
from util import as_text

# ---------- режимы ----------
MODE_OFF = 0      # авария: у всех «Просмотр»
MODE_ON = 1       # вход обязателен
MODE_ROLLOUT = 2  # раскатка: как было, без входа и с кнопками

DOMAIN = "dniprom.com"

VIEWER = "viewer"
COUNTRY_MANAGER = "country_manager"
DEMAND_PLANNER = "demand_planner"
ADMIN = "admin"

# Страницы Кабинета одним списком: ключ, файл, подпись, значок и адрес в ссылке.
# Объявление живёт ЗДЕСЬ, а не в app.py, потому что видимость страницы — такое же
# право, как любое другое, и список страниц обязан совпадать со списком прав. Раньше
# навигация была выписана в app.py ДВАЖДЫ — для админа и для остальных, — и любая
# новая страница требовала правки в двух местах; одно из них рано или поздно забыли бы.
#
# «Доступа» в этом списке нет намеренно: его видимость — это существующее право
# «Доступ: управление» (`admin`), и заводить вторую галочку про то же самое значило бы
# завести два правила, которые когда-нибудь разойдутся.
PAGES = [
    ("home",         "home.py",                  "nav.home",         ":material/home:"),
    ("stock",        "pages/1_Stock.py",         "nav.stock",        ":material/inventory_2:"),
    ("incidents",    "pages/2_Incidents.py",     "nav.incidents",    ":material/warning:"),
    ("reorder",      "pages/4_Reorder.py",       "nav.reorder",      ":material/shopping_cart:"),
    ("money",        "pages/5_Money.py",         "nav.money",        ":material/payments:"),
    # Реклама отдельной страницей, а не вкладкой в «Деньгах»: там считают прибыль,
    # здесь ведут ставки — разные читатели и разные вопросы
    ("ads",          "pages/9_Ads.py",           "nav.ads",          ":material/campaign:"),
    ("forecast",     "pages/3_Forecast.py",      "nav.forecast",     ":material/show_chart:"),
    ("reviews",      "pages/7_Reviews.py",       "nav.reviews",      ":material/rate_review:"),
    ("cm",           "pages/8_CM_Dashboard.py",  "nav.cm",           ":material/dashboard:"),
    ("dictionaries", "pages/6_Dictionaries.py",  "nav.dictionaries", ":material/library_books:"),
]

PAGE_ACTIONS = ["page." + ключ for ключ, *_ in PAGES]


# Матрица прав. Значение — роли, которым действие разрешено; `COUNTRY_SCOPED` говорит,
# что у странового менеджера оно ограничено его странами, а у остальных ролей — нет.
#
# Проведение намеренно НЕ у странового менеджера (решение владельца 30.09.2026): оно
# заменяет действующие записи и кормит покрытие, это последний шаг, и держать его в
# одних руках безопаснее. Реклама — только администратор: кнопки тратят деньги.
_MATRIX = {
    "forecast.edit":     {COUNTRY_MANAGER, DEMAND_PLANNER, ADMIN},
    "forecast.approve":  {COUNTRY_MANAGER, DEMAND_PLANNER, ADMIN},
    "forecast.upload":   {COUNTRY_MANAGER, DEMAND_PLANNER, ADMIN},
    "forecast.post":     {DEMAND_PLANNER, ADMIN},
    "forecast.replace":  {DEMAND_PLANNER, ADMIN},
    "ads.act":           {ADMIN},
    "dict.edit":         {DEMAND_PLANNER, ADMIN},
    # Эти два действия в ТЗ 010 не описаны — оно про прогнозы. Оставить их открытыми,
    # заперев прогноз, было бы непоследовательно, поэтому решение принято здесь и
    # названо вслух: пометка «заказано» и подтверждение переброски — снабжение, это
    # планировщик и администратор; приём и закрытие инцидента — рабочее действие
    # дежурного, его может делать любой, кроме «Просмотра».
    "reorder.act":       {DEMAND_PLANNER, ADMIN},
    "incident.act":      {COUNTRY_MANAGER, DEMAND_PLANNER, ADMIN},
    "admin":             {ADMIN},
}

# Видимость страниц — такое же право, и по умолчанию открыта всем: включение матрицы
# не должно ничего отнять у людей, которые вчера это видели.
for _ключ, *_ in PAGES:
    _MATRIX["page." + _ключ] = {VIEWER, COUNTRY_MANAGER, DEMAND_PLANNER, ADMIN}

# Действия, где у странового менеджера считаются его страны. У ролей выше страна не
# проверяется вовсе — у них все.
#
# Это ОСТАЁТСЯ В КОДЕ, когда сама матрица уехала в базу, и намеренно: страновое
# ограничение — не право, а смысл действия. Галочкой его переключать нечего; таблица
# отвечает «кому что можно», код — «что это действие означает».
_COUNTRY_SCOPED = {"forecast.edit", "forecast.approve", "forecast.upload"}

# Пара, без которой «Доступ» закрывается сам для всех: её нельзя снять ни галочкой,
# ни запросом (в базе стоит триггер). Здесь — чтобы интерфейс знал, что заблокировать.
# Экран «Доступ» эту пару больше отсюда не читает — у него свой список на два продукта
# (`ЗАПЕРТО` в `access_screen.py`), потому что запертых пар стало две. Константа оставлена
# как ответ на вопрос «что нельзя снять в Кабинете»: её читают проверки в scratchpad и
# она же стоит в триггере базы.
LOCKED = ("admin", ADMIN)

# ── Listing Suite ─────────────────────────────────────────────────────────────
# Роли и действия второго продукта здесь НЕ объявлены намеренно: его вокабуляр живёт в
# `access_screen.py` — там, где он нужен, то есть на общем экране «Доступ». Копия
# списка здесь однажды разошлась бы и с экраном, и с кодом другого репозитория.

ANON = "kabinet-app"

class User:
    """Кто сейчас на экране. Без входа — аноним с ролью по режиму."""

    def __init__(self, email="", name="", role=VIEWER, countries=(), logged_in=False,
                 known=False, is_qa=False):
        self.email = email
        self.name = name or email
        self.role = role
        self.countries = set(countries)
        self.logged_in = logged_in
        self.known = known  # есть строка в app_users
        # QA-агент: вошёл по тестовой ссылке, а не через Google. Отдельный признак, а не
        # «просто роль Просмотр», потому что ему запрещено ВСЁ жёстко, в обход матрицы:
        # матрицу правят галочками, и случайная галочка не должна дать роботу права
        self.is_qa = is_qa

    @property
    def actor(self) -> str:
        """Чем подписывать запись в журнале. Без входа — прежний `kabinet-app`:
        врать про авторство нельзя, а пустое поле читалось бы как потеря."""
        return self.email or ANON

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN


# ---------- чтение настроек и людей ----------
@st.cache_data(ttl=30)
def mode() -> int:
    """Режим входа из базы. Кеш короткий: аварийный переключатель обязан срабатывать
    быстро, а не через десять минут."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'auth_enabled'")
            row = cur.fetchone()
        # строки нет — ведём себя как на раскатке: отсутствие настройки не должно
        # внезапно отбирать кнопки у людей
        return int(row[0]) if row else MODE_ROLLOUT
    except Exception:
        # база недоступна — это не повод пускать больше обычного, но и не повод
        # закрывать Кабинет: отдаём раскатку, то есть прежнее поведение
        return MODE_ROLLOUT
    finally:
        conn.close()


@st.cache_data(ttl=60)
def _matrix():
    """Матрица прав из базы. None — «читать нечего, берём ту, что в коде».

    Пустая таблица и нечитаемая таблица трактуются одинаково: правила берутся из
    `_MATRIX`. Не потому что так безопаснее — потому что так ПРЕДСКАЗУЕМО. Считать
    пустую таблицу запретом всего значило бы, что несозданная таблица кладёт Кабинет,
    а считать разрешением всего — что она его открывает. Код остаётся тем, что было,
    пока в базе не сказано иное.

    Действие, которого в таблице нет, а в коде есть, запрещается всем: новая кнопка
    не должна начать работать раньше, чем кто-то решил, кому она доступна. На экране
    «Доступ» такие действия показываются отдельной строкой, а не молчат."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT action, role FROM kabinet_data.app_permissions WHERE allowed")
            rows = cur.fetchall()
    except Exception:
        return None
    finally:
        conn.close()
    if not rows:
        return None
    out = {}
    for action, role in rows:
        out.setdefault(action, set()).add(role)
    return out


@st.cache_data(ttl=60)
def _load_user(email: str):
    """Строка человека и его страны. None — если строки нет."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, is_active, access_until,
                       access_until IS NOT NULL AND access_until < current_date AS expired
                  FROM kabinet_data.app_users WHERE email = %s
            """, (email,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("""
                SELECT country FROM kabinet_data.app_user_countries WHERE email = %s
            """, (email,))
            countries = [r[0] for r in cur.fetchall()]
        # «истёк» считает база, а не Python: сервер живёт по UTC, и с полуночи до трёх
        # ночи по Киеву date.today() отдаёт вчерашнее число — доступ закрывался бы на
        # сутки позже, чем написано в карточке
        return {"role": row[0], "is_active": bool(row[1]),
                "access_until": row[2], "expired": bool(row[3]), "countries": countries}
    finally:
        conn.close()


def _log_login(email, result, reason=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kabinet_data.app_login_log (email, result, reason)
                VALUES (%s, %s, %s)
            """, (email or None, result, reason or None))
        conn.commit()
    except Exception:
        # журнал не должен мешать человеку войти; молчание тут не страшно, потому
        # что сам факт входа виден по last_login_at
        pass
    finally:
        conn.close()


def log_action(action, allowed, object_type=None, object_id=None, details=""):
    """След действия — и разрешённого, и отклонённого.

    Отклонённое писать важнее: попытка сделать то, на что права нет, — это ровно то,
    ради чего проверка стоит в обработчике, а не на кнопке."""
    u = current()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kabinet_data.app_action_log
                    (email, role, action, object_type, object_id, allowed, details, via)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (u.actor, u.role, action, object_type,
                  None if object_id is None else str(object_id), allowed, details or None,
                  # «через экран» или «запись кода»: у анонима и робота человека за
                  # действием нет, и выдавать их за людей в журнале незачем
                  "system" if (not u.email or u.email == ANON) else "ui"))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _touch_login(email, name, first: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if first:
                cur.execute("""
                    INSERT INTO kabinet_data.app_users (email, role, note, created_by, first_login_at, last_login_at)
                    VALUES (%s, 'viewer', %s, 'self:first-login', now(), now())
                    ON CONFLICT (email) DO UPDATE SET last_login_at = now()
                """, (email, f"первый вход: {name}" if name else None))
            else:
                cur.execute("""
                    UPDATE kabinet_data.app_users
                       SET last_login_at = now(),
                           first_login_at = COALESCE(first_login_at, now())
                     WHERE email = %s
                """, (email,))
        conn.commit()
    finally:
        conn.close()


# ---------- кто сейчас ----------
def current() -> User:
    """Текущий человек. Считается один раз за прогон и кладётся в session_state."""
    if "_auth_user" in st.session_state:
        return st.session_state["_auth_user"]
    # Тестовый вход проверяем ПЕРВЫМ, до режима: он работает и когда вход выключен
    # (режим 2 и 0), иначе проверять Кабинет было бы нечем ровно в те дни, когда это
    # нужнее всего. Но прав он не даёт никаких — см. `can()`.
    _qa = _qa_user_from_url()
    if _qa is not None:
        if not st.session_state.get("_qa_logged"):
            _log_login(QA_ACTOR, "ok", "тестовый вход по ссылке")
            st.session_state["_qa_logged"] = True
        st.session_state["_auth_user"] = _qa
        return _qa
    m = mode()
    if m == MODE_ROLLOUT:
        # как было: входа нет, права не ограничиваем. Роль администратора здесь —
        # не «повышение», а способ сказать «ограничений нет», и держится она ровно
        # до перевода режима в 1
        u = User(role=ADMIN)
    elif m == MODE_OFF:
        u = User(role=VIEWER)
    else:
        u = _from_login()
    st.session_state["_auth_user"] = u
    return u


def _logged_in():
    """True / False / None, где None — «OAuth не настроен».

    Отдельной функцией, потому что об этом спрашивают два места, и потому что
    локальная проверка экрана входа подменяет именно её: секретов `[auth]` на машине
    разработчика нет, а посмотреть на экран надо."""
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return None


def _from_login() -> User:
    if not _logged_in():
        return User(role=VIEWER, logged_in=False)
    email = as_text(getattr(st.user, "email", "")).strip().lower()
    name = as_text(getattr(st.user, "name", "")).strip()
    row = _load_user(email)
    if row is None:
        return User(email=email, name=name, role=VIEWER, logged_in=True, known=False)
    return User(email=email, name=name, role=row["role"], countries=row["countries"],
                logged_in=True, known=True)


QA_ACTOR = "qa-агент"


def _qa_enabled() -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT value FROM kabinet_data.reorder_params
                            WHERE key = 'qa_access_enabled'""")
            row = cur.fetchone()
        return bool(row) and int(row[0]) == 1
    except Exception:
        # не прочиталось — считаем выключенным: тестовый вход не та вещь, которая
        # должна открываться сама при неполадке
        return False
    finally:
        conn.close()


def qa_hash(token: str) -> str:
    """Хеш токена с «перцем» из секретов.

    Перец нужен затем, что открытый токен не хранится нигде: в базе лежит только хеш, и
    без перца укравший дамп мог бы подобрать токен перебором. С ним дамп сам по себе
    бесполезен. Перца нет — работаем без него, но говорим об этом на экране: молча
    ослаблять защиту хуже, чем сказать."""
    import hashlib
    перец = ""
    try:
        перец = str(st.secrets["qa"]["pepper"])
    except Exception:
        перец = ""
    return hashlib.sha256((перец + "|" + token.strip()).encode()).hexdigest()


def qa_pepper_set() -> bool:
    try:
        return bool(str(st.secrets["qa"]["pepper"]).strip())
    except Exception:
        return False


def _qa_user_from_url():
    """Пользователь по ссылке `?qa=токен`, если вход включён и токен жив.

    Сверка хешей идёт через `compare_digest`: обычное сравнение строк выходит из цикла
    на первом несовпавшем знаке, и по времени ответа токен подбирается посимвольно."""
    import hmac
    try:
        токен = st.query_params.get("qa", "")
    except Exception:
        токен = ""
    if not токен or not _qa_enabled():
        return None
    цель = qa_hash(токен)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, token_hash FROM kabinet_data.qa_tokens
                            WHERE revoked_at IS NULL AND expires_at > now()""")
            живые = cur.fetchall()
            нашли = next((i for i, h in живые if hmac.compare_digest(h, цель)), None)
            if нашли is None:
                return None
            cur.execute("""UPDATE kabinet_data.qa_tokens
                              SET last_used_at = now(), uses = uses + 1 WHERE id = %s""",
                        (нашли,))
        conn.commit()
    except Exception:
        return None
    finally:
        conn.close()
    return User(email=QA_ACTOR, name=QA_ACTOR, role=VIEWER, logged_in=True,
                known=False, is_qa=True)


def _allowed_to_enter(email: str, row) -> bool:
    """Пускаем по домену ИЛИ по строке-исключению. Отключённая строка не пускает
    даже своего: `is_active = false` — это «доступ снят», а не «нет записи».

    Истёкший срок закрывает доступ так же, но запись НЕ выключается: дата видна в
    карточке, и продлить её — значит вернуть дату, а не разбираться, кто и когда
    выключил человека молча."""
    if row is not None and not row["is_active"]:
        return False
    if row is not None and row.get("expired"):
        return False
    if email.endswith("@" + DOMAIN):
        return True
    return row is not None  # активное исключение вне домена


# ---------- права ----------
def can(action: str, countries=None) -> bool:
    """Можно ли показывать и делать. `countries` — страны объекта (одна или набор).

    Для странового менеджера требуется, чтобы ВСЕ страны объекта были его: пул из
    маркетплейсов разных стран иначе правил бы человек, которому принадлежит лишь
    часть. По ТЗ 004 пул одностранный, но правило строгое на случай ошибки в
    справочнике (решение владельца 30.09.2026)."""
    u = current()
    m = mode()
    if u.is_qa:
        # Жёстко и раньше всех прочих правил, включая режим раскатки: QA-агент смотрит,
        # и только. Иначе включённая на время проверки раскатка открыла бы роботу
        # кнопки, тратящие деньги.
        #
        # ВИДИМОСТЬ СТРАНИЦ — исключение, и без него вся затея теряет смысл: робот
        # должен видеть весь Кабинет, иначе проверять ему нечего. Поэтому «смотреть»
        # ему можно всё, а «делать» — ничего.
        return action in PAGE_ACTIONS
    if m == MODE_ROLLOUT:
        return True
    if m == MODE_OFF:
        return False
    if not u.logged_in:
        return False
    из_базы = _matrix()
    таблица = _MATRIX if из_базы is None else из_базы
    allowed_roles = таблица.get(action)
    if not allowed_roles or u.role not in allowed_roles:
        return False
    if u.role == COUNTRY_MANAGER and action in _COUNTRY_SCOPED:
        want = _as_country_set(countries)
        if not want:
            # страна объекта неизвестна — не угадываем в пользу доступа
            return False
        return want <= u.countries
    return True


def _as_country_set(countries) -> set:
    if countries is None:
        return set()
    if isinstance(countries, str):
        countries = [countries]
    return {as_text(c).strip().upper() for c in countries if as_text(c).strip()}


def require(action: str, countries=None, object_type=None, object_id=None) -> bool:
    """Проверка в момент действия. Отказ показывается и пишется в журнал.

    Возвращает True/False, а не бросает: обработчику надо не упасть, а не сделать."""
    ok = can(action, countries)
    log_action(action, ok, object_type, object_id,
               details="" if ok else f"режим {mode()}, роль {current().role}")
    if not ok:
        st.error(t("auth.denied"))
    return ok


class Denied(Exception):
    """Отказ, который нельзя не заметить.

    Нужен там, где запись идёт через общий путь (`exec_sql` в «Справочниках»): закрыть
    одну функцию надёжнее, чем двадцать семь кнопок по отдельности, — пропущенная
    кнопка тогда не становится дырой. Вызывающий код там уже обёрнут в `try`, поэтому
    текст отказа доезжает до человека тем же путём, что и любая ошибка сохранения."""


def demand(action: str, countries=None, object_type=None, object_id=None):
    """Жёсткая проверка: либо можно, либо исключение. Ничего не пишет и не рисует."""
    if not can(action, countries):
        log_action(action, False, object_type, object_id,
                   details=f"режим {mode()}, роль {current().role}")
        raise Denied(t("auth.denied"))
    log_action(action, True, object_type, object_id)


def actor() -> str:
    """Чем подписывать запись в журналах Кабинета."""
    return current().actor


# ---------- экраны ----------
def _screen(page_fn, title):
    """Показать ОДНУ страницу и ничего больше.

    Без этого Streamlit, не увидев `st.navigation` (а `guard()` останавливает прогон
    раньше него), собирает навигацию сам из папки `pages/` — и невошедшему видно всё
    оглавление Кабинета: Stock, Money, Forecast, Access. Страницы при этом не
    исполняются и данных не отдают, но показывать устройство системы тому, кого мы
    только что не пустили, незачем.

    Навигация из одной страницы с `position="hidden"` убирает список целиком:
    проверено на минимальном примере — имён страниц нет и в разметке, то есть это
    отсутствие, а не сокрытие стилями."""
    # Тот же экран отвечает и по адресам всех страниц Кабинета: иначе прямая ссылка
    # /Dictionaries у невошедшего (новая вкладка, ссылка из чата, тестовая сессия без
    # `?qa=`) давала Streamlit'овское «Page not found» и только потом экран входа —
    # выглядело как сломанная страница. Адреса уходят в служебное сообщение, а не в
    # разметку: меню по-прежнему нет, `position="hidden"`.
    страницы = [st.Page(page_fn, title=title, default=True)]
    for _к, файл, _п, _з in PAGES:
        страницы.append(st.Page(page_fn, title=title, url_path=page_path(файл), visibility="hidden"))
    st.navigation(страницы, position="hidden").run()
    st.stop()


def page_path(файл: str) -> str:
    """Адрес страницы в ссылке — тот же, что Streamlit выводит из имени файла:
    отбрасывает путь, числовой префикс и расширение. `pages/1_Stock.py` → `Stock`.
    Один на приложение: по нему отвечают и заглушки закрытых страниц, и экран входа."""
    import re as _re
    имя = файл.rsplit("/", 1)[-1]
    if имя.endswith(".py"):
        имя = имя[:-3]
    return _re.sub(r"^\d+_", "", имя)


def _login_screen():
    """Экран входа: переключатель языка на нём свой, потому что человек ещё не внутри
    и сайдбара с общим переключателем не видит. По умолчанию английский —
    решение владельца."""
    if "auth_lang" not in st.session_state:
        st.session_state["auth_lang"] = "en"
    lang = st.session_state["auth_lang"]
    texts = _LOGIN_TEXTS[lang]
    st.markdown("<div style='height:12vh'></div>", unsafe_allow_html=True)
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        picked = st.segmented_control(
            " ", ["RU", "UK", "EN"], default={"ru": "RU", "uk": "UK", "en": "EN"}[lang],
            key="auth_lang_pick", label_visibility="collapsed")
        # повторный клик по выбранному сегменту снимает выбор и возвращает None —
        # держим прежний язык, иначе экран останется без подписи
        if picked and {"RU": "ru", "UK": "uk", "EN": "en"}[picked] != lang:
            st.session_state["auth_lang"] = {"RU": "ru", "UK": "uk", "EN": "en"}[picked]
            st.rerun()
        st.title(texts["title"])
        st.caption(texts["only"])
        if st.button(texts["button"], type="primary", width="stretch"):
            st.login()


def _denied_screen(email):
    lang = st.session_state.get("auth_lang", "en")
    texts = _LOGIN_TEXTS[lang]
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        st.title(texts["title"])
        st.error(texts["denied"].format(email=email))
        st.caption(texts["only"])
        if st.button(texts["logout"], width="stretch"):
            st.logout()


# Тексты экрана входа держим здесь, а не в общем словаре: до входа язык интерфейса
# ещё не выбран, у экрана свой переключатель, и связывать их значило бы тащить
# состояние сайдбара туда, где сайдбара нет.
_LOGIN_TEXTS = {
    "ru": {
        "title": "Kabinet Sales, Demand & Supply",
        "only": "Только для сотрудников Dnipro-M",
        "button": "Войти через Google",
        "denied": "Доступ для {email} закрыт.",
        "logout": "Выйти",
    },
    "uk": {
        "title": "Kabinet Sales, Demand & Supply",
        "only": "Лише для співробітників Dnipro-M",
        "button": "Увійти через Google",
        "denied": "Доступ для {email} закрито.",
        "logout": "Вийти",
    },
    "en": {
        "title": "Kabinet Sales, Demand & Supply",
        "only": "Dnipro-M employees only",
        "button": "Sign in with Google",
        "denied": "Access for {email} is closed.",
        "logout": "Sign out",
    },
}


def guard():
    """Ворота. Зовётся в `app.py` раньше, чем читается хоть одна бизнес-таблица.

    В режимах 2 и 0 не спрашивает ничего: на раскатке всё как было, в аварии все
    получают «Просмотр». Вход спрашивается только в режиме 1."""
    m = mode()
    # замечаем смену режима в ЛЮБОМ режиме, до всякого ветвления: переход в аварийный
    # ноль надо увидеть ровно так же, как включение входа
    _note_mode(m)
    if current().is_qa:
        return   # вошёл по тестовой ссылке — экран входа ему не показываем
    if m != MODE_ON:
        return
    logged = _logged_in()
    if logged is None:
        # секреты [auth] не настроены — сказать об этом прямо лучше, чем пустить всех
        _screen(lambda: st.error(t("auth.no_oauth")), "Sign in")
        return
    if not logged:
        _screen(_login_screen, "Sign in")
        return
    email = as_text(getattr(st.user, "email", "")).strip().lower()
    row = _load_user(email)
    if not _allowed_to_enter(email, row):
        if row is None:
            _log_login(email, "denied_domain", "домен вне списка")
        elif row.get("expired"):
            _log_login(email, "denied_disabled",
                       f"срок доступа истёк {row['access_until']:%d.%m.%Y}")
        else:
            _log_login(email, "denied_disabled", "строка отключена")
        _screen(lambda: _denied_screen(email), "Access")
        return
    # первый вход заводит человека с ролью «Просмотр» и уведомляет администраторов
    if row is None:
        _touch_login(email, as_text(getattr(st.user, "name", "")), first=True)
        _log_login(email, "first_login", "заведён с ролью «Просмотр»")
        _load_user.clear()
        notify_new_user(email, as_text(getattr(st.user, "name", "")))
    elif not st.session_state.get("_auth_touched"):
        _touch_login(email, "", first=False)
        _log_login(email, "ok")
        st.session_state["_auth_touched"] = True


def _telegram(text: str):
    """Отправка в общий канал. Токен — в скоупе `kabinet-alerts`, читаем его тем же
    принципалом, что и базу; копии в `st.secrets` нет намеренно."""
    import base64
    import requests
    from db.connection import get_workspace_client
    w = get_workspace_client()
    token = base64.b64decode(
        w.secrets.get_secret(scope="kabinet-alerts", key="telegram-bot-token").value).decode()
    chat = base64.b64decode(
        w.secrets.get_secret(scope="kabinet-alerts", key="telegram-chat-id").value).decode()
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=10)


def notify_new_user(email, name):
    """Telegram администраторам о новом человеке.

    Неудачу кладём в журнал действий, а не глотаем: сторож досылает такие уведомления
    сам, и канал не должен молчать только потому, что грант на скоуп забыли выдать."""
    try:
        _telegram(f"👤 Новый человек в Кабинете: {name or ''} &lt;{email}&gt;\n"
                  f"Роль «Просмотр», действий нет. Назначить роль и страны — "
                  f"«Справочники → Доступ».")
        log_action("notify_new_user", True, "user", email, "отправлено приложением")
    except Exception as e:
        log_action("notify_new_user", False, "user", email,
                   f"приложение не отправило: {type(e).__name__}: {str(e)[:120]}")


@st.cache_data(ttl=60)
def _journaled_mode():
    """Режим, записанный в журнале последним. None — записи ещё нет.

    Порядок по `ts DESC, id DESC`, а не по одному `ts`: `now()` в Postgres — время
    НАЧАЛА транзакции, у строк одной транзакции оно совпадает до микросекунды, и
    «последняя» выбиралась бы произвольно."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT details FROM kabinet_data.app_action_log
                            WHERE action = 'auth_mode' ORDER BY ts DESC, id DESC LIMIT 1""")
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        import re
        m = re.search(r"режим (\d+)", row[0])
        return int(m.group(1)) if m else None
    except Exception:
        return None
    finally:
        conn.close()


def _note_mode(m: int):
    """Смену режима замечает и приложение — при первом же открытии страницы.

    Флаг правят ПРЯМО В БАЗЕ, и перехватить сам `UPDATE` нельзя, поэтому замечают
    двое: здесь и сторож на своём прогоне. Запись одна на смену состояния, а не на
    каждый прогон, иначе в чат уходило бы «режим 2» каждую минуту. Гонка между
    приложением и сторожем безобидна: кто записал первым, у второго сравнение уже
    сходится, и второго сообщения нет."""
    last = _journaled_mode()
    if last == m:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # подписываемся приложением: смену заметил не человек, а код, и приписывать
            # её кому-то из людей значило бы сказать, что он её и сделал
            cur.execute("""INSERT INTO kabinet_data.app_action_log
                               (email, role, action, allowed, details, via)
                           VALUES ('kabinet-app', NULL, 'auth_mode', true, %s, 'system')""",
                        (f"режим {m}" + (f", было {last}" if last is not None else ", первая запись"),))
        conn.commit()
    except Exception:
        return
    finally:
        conn.close()
    _journaled_mode.clear()
    if last is None:
        return  # первая запись — это не «изменение», сообщать не о чем
    words = {MODE_ROLLOUT: "раскатка — входа нет, кнопки у всех",
             MODE_ON: "вход обязателен, роли работают",
             MODE_OFF: "АВАРИЯ — входа нет, у всех «Просмотр»"}
    try:
        _telegram(f"🔑 Режим входа изменён: {last} → {m} ({words.get(m, '?')})")
    except Exception as e:
        log_action("auth_mode_notify", False, "mode", str(m),
                   f"приложение не отправило: {type(e).__name__}: {str(e)[:120]}")


# ---------- шапка ----------
def header():
    """Имя, роль, страны и «Выйти» — в сайдбаре под логотипом.

    В режимах 2 и 0 показываем не человека, а сам режим: иначе на раскатке в шапке
    стояло бы «Администратор», и это читалось бы как выданное право."""
    # Проверка «это робот?» идёт ПЕРВОЙ: в режиме раскатки и в аварии ветки ниже
    # возвращаются раньше, и QA-агент увидел бы в шапке «вход не включён» вместо
    # собственной пометки — то есть именно то, что мы обещали не прятать
    u = current()
    if u.is_qa:
        # Не прячем: в шапке и в журналах видно, что это робот, а не человек
        st.sidebar.caption(t("auth.qa_badge"))
        return
    m = mode()
    if m == MODE_ROLLOUT:
        st.sidebar.caption(t("auth.mode_rollout"))
        return
    if m == MODE_OFF:
        st.sidebar.caption(t("auth.mode_off"))
        return
    if not u.logged_in:
        return
    bits = [t(f"auth.role.{u.role}")]
    if u.role == COUNTRY_MANAGER:
        bits.append(", ".join(sorted(u.countries)) if u.countries else t("auth.no_countries"))
    st.sidebar.caption(f"**{u.name}**  \n{' · '.join(bits)}")
    if st.sidebar.button(t("auth.logout"), width="stretch"):
        _log_login(u.email, "logout")
        st.logout()
