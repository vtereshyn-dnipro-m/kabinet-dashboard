# -*- coding: utf-8 -*-
"""Матрица прав проверяется поведением, а не чтением словаря: словарь можно прочитать
и глазами, а вот что `can()` делает со странами и режимами — нет."""
import sys, json, psycopg2, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
import db.connection as dbc
dbc.get_connection = lambda: psycopg2.connect(DSN)
import auth
auth.get_connection = dbc.get_connection

ACTIONS = ["forecast.edit", "forecast.approve", "forecast.upload", "forecast.post",
           "forecast.replace", "ads.act", "dict.edit", "reorder.act", "incident.act", "admin"]
ROLES = [auth.VIEWER, auth.COUNTRY_MANAGER, auth.DEMAND_PLANNER, auth.ADMIN]

def setup(m, role, countries=(), logged=True):
    auth.mode = lambda: m
    u = auth.User(email="x@dniprom.com", role=role, countries=countries, logged_in=logged)
    auth.current = lambda: u

беда = 0
def ждём(что, ожидание, факт):
    global беда
    if bool(ожидание) != bool(факт):
        print(f"  РАСХОЖДЕНИЕ: {что} — ждали {ожидание}, получили {факт}")
        беда += 1

# --- режим 1: роли работают ---
ОЖИДАНИЕ = {
    auth.VIEWER:          set(),
    auth.COUNTRY_MANAGER: {"forecast.edit", "forecast.approve", "forecast.upload", "incident.act"},
    auth.DEMAND_PLANNER:  {"forecast.edit", "forecast.approve", "forecast.upload", "forecast.post",
                           "forecast.replace", "dict.edit", "reorder.act", "incident.act"},
    auth.ADMIN:           set(ACTIONS),
}
print("=== режим 1 (вход включён), объект — страна ES, у менеджера ES ===")
for role in ROLES:
    setup(1, role, {"ES"})
    for a in ACTIONS:
        ждём(f"{role}/{a}", a in ОЖИДАНИЕ[role], auth.can(a, "ES"))

print("=== страновой менеджер и чужая страна ===")
setup(1, auth.COUNTRY_MANAGER, {"ES"})
ждём("ES своя", True, auth.can("forecast.edit", "ES"))
ждём("FR чужая", False, auth.can("forecast.edit", "FR"))
ждём("пул ES+FR — нужна ВСЯ страна", False, auth.can("forecast.edit", {"ES", "FR"}))
ждём("пул ES+ES", True, auth.can("forecast.edit", {"ES"}))
ждём("страна неизвестна — не угадываем", False, auth.can("forecast.edit", None))
ждём("проведение не его", False, auth.can("forecast.post", "ES"))
setup(1, auth.COUNTRY_MANAGER, {"ES", "FR"})
ждём("две страны, пул ES+FR", True, auth.can("forecast.edit", {"ES", "FR"}))

print("=== вошёл, но роли нет (первый вход) ===")
setup(1, auth.VIEWER, set())
ждём("новичок ничего не может", False, any(auth.can(a, "ES") for a in ACTIONS))

print("=== не вошёл при включённом входе ===")
setup(1, auth.ADMIN, {"ES"}, logged=False)
ждём("без входа даже админу нельзя", False, any(auth.can(a, "ES") for a in ACTIONS))

print("=== режим 2 (раскатка): всё как было ===")
for role in ROLES:
    setup(2, role, set(), logged=False)
    ждём(f"раскатка/{role}", True, all(auth.can(a, "ES") for a in ACTIONS))

print("=== режим 0 (авария): только просмотр ===")
for role in ROLES:
    setup(0, role, {"ES"})
    ждём(f"авария/{role}", False, any(auth.can(a, "ES") for a in ACTIONS))

print("=== матрица берётся из БАЗЫ и совпадает с кодом ===")
из_базы = auth._matrix()
ждём("таблица прочиталась", True, из_базы is not None)
if из_базы is not None:
    for действие, роли in auth._MATRIX.items():
        ждём(f"{действие}: база = код", роли, из_базы.get(действие, set()))
    лишние = set(из_базы) - set(auth._MATRIX)
    ждём("в базе нет действий, которых нет в коде", set(), лишние)

print("=== таблица не прочиталась или пуста — берём код ===")
настоящая = auth._matrix
auth._matrix = lambda: None
setup(1, auth.DEMAND_PLANNER, {"ES"})
ждём("планировщик проводит по коду", True, auth.can("forecast.post", "ES"))
ждём("просмотру всё так же нельзя", False, (setup(1, auth.VIEWER), auth.can("forecast.post", "ES"))[1])

print("=== база ПЕРЕОПРЕДЕЛЯЕТ код ===")
auth._matrix = lambda: {"ads.act": {auth.VIEWER}}
setup(1, auth.VIEWER, set())
ждём("дали просмотру рекламу — можно", True, auth.can("ads.act"))
setup(1, auth.ADMIN, set())
ждём("забрали у админа — нельзя", False, auth.can("ads.act"))
ждём("действия нет в таблице — запрещено всем", False, auth.can("forecast.post"))
auth._matrix = настоящая

print(f"\nрасхождений: {беда}")
