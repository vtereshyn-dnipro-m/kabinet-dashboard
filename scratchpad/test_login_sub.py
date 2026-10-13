import sys, types, time
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
ОТВЕТЫ = {"user": None, "bind": "ok"}
ЗАВЕДЕНО, ВХОДЫ, ВЫХОДЫ, ОТКАЗЫ, ДЕЙСТВИЯ, ТГ = [], [], [], [], [], []
class Cur:
    def __init__(s): s.r = []
    def execute(s, sql, p=None):
        q = " ".join(sql.split())
        if "auth_enabled" in q: s.r = [(1,)]
        elif "auth_max_login_hours" in q: s.r = [(168,)]
        elif "app_user_bind_sub" in q:
            r = ОТВЕТЫ["bind"]
            if r.startswith("archived:"): ОТВЕТЫ["user"] = None
            s.r = [(r,)]
        elif q.startswith("INSERT INTO kabinet_data.app_users"):
            ЗАВЕДЕНО.append((p[0], p[2])); ОТВЕТЫ["user"] = ("viewer", True, None, False); s.r = []
        elif "FROM kabinet_data.app_user_countries" in q: s.r = []
        elif "FROM kabinet_data.app_users" in q: s.r = [] if ОТВЕТЫ["user"] is None else [ОТВЕТЫ["user"]]
        else: s.r = []
    def fetchone(s): return s.r[0] if s.r else None
    def fetchall(s): return s.r
    def __enter__(s): return s
    def __exit__(s, *a): return False
class Conn:
    def cursor(s): return Cur()
    def commit(s): pass
    def rollback(s): pass
    def close(s): pass
import db.connection as dbc
dbc.get_connection = lambda: Conn()
import auth
auth.get_connection = lambda: Conn()
auth.st.session_state = {}; auth.st.query_params = {}
auth.st.logout = lambda: ВЫХОДЫ.append(1)
auth._log_login = lambda e, r, reason="": ВХОДЫ.append(r)
auth.log_action = lambda a, ok, *x, **k: ДЕЙСТВИЯ.append(a)
auth._telegram = lambda t: ТГ.append(t)
auth.notify_new_user = lambda *a, **k: ТГ.append("new")
auth._screen = lambda *a, **k: ОТКАЗЫ.append(a)
auth._note_mode = lambda m: None
FAILS = []
def check(n, c): print(("  OK   " if c else "  FAIL ") + n); c or FAILS.append(n)
def войти(почта, user, возраст_ч=1.0, bind="ok"):
    for l in (ЗАВЕДЕНО, ВХОДЫ, ВЫХОДЫ, ОТКАЗЫ, ДЕЙСТВИЯ, ТГ): l.clear()
    ОТВЕТЫ.update(user=user, bind=bind)
    auth.st.session_state = {}
    for f in (auth.mode, auth._load_user, auth._max_login_hours): f.clear()
    auth.st.user = types.SimpleNamespace(is_logged_in=True, email=почта, name="Новый", sub="sub-NEW", iat=time.time() - возраст_ч*3600)
    auth.guard()
    return auth.current()
u = войти("кто@dniprom.com", ("demand_planner", True, None, False), возраст_ч=200)
check("вход старше 168 ч — повторный вход через Google", ВЫХОДЫ == [1] and "relogin" in ВХОДЫ and "ok" not in ВХОДЫ)
u = войти("кто@dniprom.com", ("demand_planner", True, None, False), возраст_ч=100)
check("вход моложе 168 ч — внутри, роль своя", not ВЫХОДЫ and u.role == "demand_planner")
u = войти("кто@dniprom.com", ("demand_planner", True, None, False), bind="archived:кто@dniprom.com~20261014-1200")
check("адрес у другого Google-аккаунта — новая карточка «Просмотр» с его Google ID",
      "reassigned" in ВХОДЫ and "card_archived" in ДЕЙСТВИЯ and ЗАВЕДЕНО == [("кто@dniprom.com", "sub-NEW")] and u.role == "viewer" and not ОТКАЗЫ)
check("…и администраторам ушло сообщение об архиве", any("другого Google-аккаунта" in t for t in ТГ if isinstance(t, str)))
u = войти("artem@gmail.com", ("admin", True, None, False), bind="archived:artem@gmail.com~20261014-1200")
check("исключение вне домена у другого Google-аккаунта — отказ", not ЗАВЕДЕНО and ОТКАЗЫ)
u = войти("новый@dniprom.com", None, bind="none")
check("первый вход — карточка сразу с Google ID", ЗАВЕДЕНО == [("новый@dniprom.com", "sub-NEW")] and u.role == "viewer")
print("ИТОГ:", "всё ок" if not FAILS else FAILS); sys.exit(1 if FAILS else 0)
