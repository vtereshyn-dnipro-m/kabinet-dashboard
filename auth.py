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

# Действия, где у странового менеджера считаются его страны. У ролей выше страна не
# проверяется вовсе — у них все.
_COUNTRY_SCOPED = {"forecast.edit", "forecast.approve", "forecast.upload"}

ANON = "kabinet-app"


class User:
    """Кто сейчас на экране. Без входа — аноним с ролью по режиму."""

    def __init__(self, email="", name="", role=VIEWER, countries=(), logged_in=False,
                 known=False):
        self.email = email
        self.name = name or email
        self.role = role
        self.countries = set(countries)
        self.logged_in = logged_in
        self.known = known  # есть строка в app_users

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
def _load_user(email: str):
    """Строка человека и его страны. None — если строки нет."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, is_active FROM kabinet_data.app_users WHERE email = %s
            """, (email,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("""
                SELECT country FROM kabinet_data.app_user_countries WHERE email = %s
            """, (email,))
            countries = [r[0] for r in cur.fetchall()]
        return {"role": row[0], "is_active": bool(row[1]), "countries": countries}
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
                    (email, role, action, object_type, object_id, allowed, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (u.email or None, u.role, action, object_type,
                  None if object_id is None else str(object_id), allowed, details or None))
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


def _from_login() -> User:
    try:
        logged = bool(st.user.is_logged_in)
    except Exception:
        logged = False
    if not logged:
        return User(role=VIEWER, logged_in=False)
    email = as_text(getattr(st.user, "email", "")).strip().lower()
    name = as_text(getattr(st.user, "name", "")).strip()
    row = _load_user(email)
    if row is None:
        return User(email=email, name=name, role=VIEWER, logged_in=True, known=False)
    return User(email=email, name=name, role=row["role"], countries=row["countries"],
                logged_in=True, known=True)


def _allowed_to_enter(email: str, row) -> bool:
    """Пускаем по домену ИЛИ по строке-исключению. Отключённая строка не пускает
    даже своего: `is_active = false` — это «доступ снят», а не «нет записи»."""
    if row is not None and not row["is_active"]:
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
    if m == MODE_ROLLOUT:
        return True
    if m == MODE_OFF:
        return False
    if not u.logged_in:
        return False
    allowed_roles = _MATRIX.get(action)
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
        st.stop()


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
    st.stop()


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
    if m != MODE_ON:
        return
    try:
        logged = bool(st.user.is_logged_in)
    except Exception:
        # секреты [auth] не настроены — сказать об этом прямо лучше, чем пустить всех
        st.error(t("auth.no_oauth"))
        st.stop()
    if not logged:
        _login_screen()
        return
    email = as_text(getattr(st.user, "email", "")).strip().lower()
    row = _load_user(email)
    if not _allowed_to_enter(email, row):
        _log_login(email, "denied_disabled" if row is not None else "denied_domain",
                   "строка отключена" if row is not None else "домен вне списка")
        _denied_screen(email)
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


def notify_new_user(email, name):
    """Telegram администраторам о новом человеке.

    Токен лежит в скоупе `kabinet-alerts`, и принципалу приложения READ на него нужен
    отдельно. Без гранта отправка молча не выходит — поэтому неудача пишется в журнал
    действий, а сторож досылает такие уведомления сам: канал не должен молчать только
    потому, что грант забыли выдать."""
    try:
        import base64
        import requests
        from db.connection import get_workspace_client
        w = get_workspace_client()
        token = base64.b64decode(
            w.secrets.get_secret(scope="kabinet-alerts", key="telegram-bot-token").value).decode()
        chat = base64.b64decode(
            w.secrets.get_secret(scope="kabinet-alerts", key="telegram-chat-id").value).decode()
        text = (f"👤 Новый человек в Кабинете: {name or ''} &lt;{email}&gt;\n"
                f"Роль «Просмотр», действий нет. Назначить роль и страны — "
                f"«Справочники → Доступ».")
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=10)
        log_action("notify_new_user", True, "user", email, "отправлено приложением")
    except Exception as e:
        log_action("notify_new_user", False, "user", email,
                   f"приложение не отправило: {type(e).__name__}: {str(e)[:120]}")


# ---------- шапка ----------
def header():
    """Имя, роль, страны и «Выйти» — в сайдбаре под логотипом.

    В режимах 2 и 0 показываем не человека, а сам режим: иначе на раскатке в шапке
    стояло бы «Администратор», и это читалось бы как выданное право."""
    m = mode()
    if m == MODE_ROLLOUT:
        st.sidebar.caption(t("auth.mode_rollout"))
        return
    if m == MODE_OFF:
        st.sidebar.caption(t("auth.mode_off"))
        return
    u = current()
    if not u.logged_in:
        return
    bits = [t(f"auth.role.{u.role}")]
    if u.role == COUNTRY_MANAGER:
        bits.append(", ".join(sorted(u.countries)) if u.countries else t("auth.no_countries"))
    st.sidebar.caption(f"**{u.name}**  \n{' · '.join(bits)}")
    if st.sidebar.button(t("auth.logout"), width="stretch"):
        _log_login(u.email, "logout")
        st.logout()
