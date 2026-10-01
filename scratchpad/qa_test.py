# -*- coding: utf-8 -*-
"""Тестовый вход QA: пускает ли живой токен и правда ли роботу ничего нельзя.

Всё в транзакции с откатом — боевой выключатель и токены не трогаем.
"""
import sys, json, psycopg2, warnings, secrets
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
import db.connection as dbc
_общее = psycopg2.connect(DSN)          # одно соединение на весь опыт, без autocommit
class Обёртка:
    def cursor(self, *a, **k): return _общее.cursor(*a, **k)
    def commit(self): pass              # не фиксируем: всё откатим
    def rollback(self): pass
    def close(self): pass
dbc.get_connection = lambda: Обёртка()
import auth
auth.get_connection = dbc.get_connection

беда = 0
def ждём(что, ожидание, факт):
    global беда
    if bool(ожидание) != bool(факт):
        print(f"  ПРОВАЛ {что}: ждали {ожидание}, вышло {факт}"); беда += 1
    else:
        print(f"  ок     {что}")

cur = _общее.cursor()
ТОКЕН = secrets.token_urlsafe(32)
cur.execute("""INSERT INTO kabinet_data.qa_tokens (token_hash, label, created_by, expires_at)
               VALUES (%s, 'тест', 'тест', now() + interval '1 day')""", (auth.qa_hash(ТОКЕН),))

# подменяем только адресную строку и настройки сессии
class ПсевдоПараметры(dict):
    def get(self, k, d=None): return dict.get(self, k, d)
auth.st.query_params = ПсевдоПараметры({"qa": ТОКЕН})
auth.st.session_state = {}

cur.execute("UPDATE kabinet_data.reorder_params SET value = 0 WHERE key='qa_access_enabled'")
ждём("выключатель в нуле — токен не пускает", False, auth._qa_user_from_url() is not None)

cur.execute("UPDATE kabinet_data.reorder_params SET value = 1 WHERE key='qa_access_enabled'")
кто = auth._qa_user_from_url()
ждём("включили — живой токен пускает", True, кто is not None)
if кто:
    ждём("роль строго «Просмотр»", True, кто.role == auth.VIEWER)
    ждём("помечен как робот", True, кто.is_qa)
    ждём("в журнале пойдёт как qa-агент", True, кто.actor == auth.QA_ACTOR)

auth.st.query_params = ПсевдоПараметры({"qa": ТОКЕН + "x"})
ждём("чужой токен не пускает", False, auth._qa_user_from_url() is not None)
auth.st.query_params = ПсевдоПараметры({})
ждём("без токена не пускает", False, auth._qa_user_from_url() is not None)

# просроченный и погашенный
cur.execute("UPDATE kabinet_data.qa_tokens SET expires_at = now() - interval '1 hour' WHERE label='тест'")
auth.st.query_params = ПсевдоПараметры({"qa": ТОКЕН})
ждём("просроченный не пускает", False, auth._qa_user_from_url() is not None)
cur.execute("UPDATE kabinet_data.qa_tokens SET expires_at = now() + interval '1 day', revoked_at = now() WHERE label='тест'")
ждём("погашенный не пускает", False, auth._qa_user_from_url() is not None)

# и главное: роботу нельзя НИЧЕГО, в любом режиме
print("  --- что может робот ---")
auth.current = lambda: auth.User(email=auth.QA_ACTOR, role=auth.VIEWER, logged_in=True, is_qa=True)
ДЕЙСТВИЯ = ["forecast.edit", "forecast.post", "ads.act", "dict.edit",
            "reorder.act", "incident.act", "admin"]
for режим, имя in ((2, "раскатка"), (1, "вход включён"), (0, "авария")):
    auth.mode = lambda m=режим: m
    можно = [д for д in ДЕЙСТВИЯ if auth.can(д, "ES")]
    ждём(f"режим «{имя}» — роботу нельзя ничего", True, not можно)

# даже если матрица вдруг разрешит «Просмотру» всё
auth._matrix = lambda: {д: {auth.VIEWER, auth.ADMIN} for д in ДЕЙСТВИЯ}
auth.mode = lambda: 1
ждём("матрица открыла «Просмотру» всё — роботу всё равно нельзя", True,
     not [д for д in ДЕЙСТВИЯ if auth.can(д, "ES")])

_общее.rollback()
cur = _общее.cursor()
cur.execute("SELECT value::int FROM kabinet_data.reorder_params WHERE key='qa_access_enabled'")
print(f"\nпосле отката выключатель: {cur.fetchone()[0]} (должен быть 0)")
cur.execute("SELECT count(*) FROM kabinet_data.qa_tokens")
print(f"токенов в базе: {cur.fetchone()[0]} (должно быть 0)")
print(f"расхождений: {беда}")
_общее.close()
