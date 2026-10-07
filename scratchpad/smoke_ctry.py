# -*- coding: utf-8 -*-
"""«Справочники → Страны» на живой базе (ТЗ 002): список и поиск, создание с ошибками под полями, дубли по всем
записям, карточка, переименование, деактивация с зависимостями и планом миграции (§8), возврат, «Просмотр».
Таблицы стран подменяются временными копиями — данные не меняются, всё исчезает с откатом."""
import sys, json, re, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
TABLES = ("countries", "country_change_log")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_c.execute("CREATE TEMP SEQUENCE ccl_s START 1000000; ALTER TABLE pg_temp.country_change_log ALTER id SET DEFAULT nextval('ccl_s')")
_RX = re.compile(r"kabinet_data\.(countries|country_change_log)\b")
def _rw(sql):
    return _RX.sub(r"pg_temp.\1", sql) if isinstance(sql, str) else sql
class Cur:
    def __init__(self, c): self.c = c
    def execute(self, sql, p=None): return self.c.execute(_rw(sql), p)
    def __getattr__(self, n): return getattr(self.c, n)
    def __iter__(self): return iter(self.c)
    def __enter__(self): return self
    def __exit__(self, *a): pass
class Shared:
    def cursor(self, *a, **k): return Cur(real.cursor(*a, **k))
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
    def __getattr__(self, n): return getattr(real, n)
import db.connection as dbc
dbc.get_connection = lambda: Shared()
import streamlit as st
st.page_link = lambda *a, **k: None
import auth
ROLE = [auth.ADMIN]
auth.mode = lambda: auth.MODE_ON
auth.current = lambda: auth.User(email="test@dniprom.com", role=ROLE[0], logged_in=True, known=True)
from streamlit.testing.v1 import AppTest
cur = real.cursor()
def one(sql, p=()):
    cur.execute(_rw(sql), p); return cur.fetchone()
ok = []
def check(name, cond, extra=""):
    ok.append(bool(cond)); print(("  ок   " if cond else "  ПРОВАЛ ") + name + (f" — {extra}" if extra else ""))
def new_at():
    at = AppTest.from_file(f"{R}/pages/6_Dictionaries.py", default_timeout=300)
    at.session_state["dict_section"] = "ctry"; at.session_state["dict_section_last"] = "ctry"
    at.run(); return at
def open_card(at, a2):
    at.session_state["ctry_card"] = a2
    at.session_state["ctry_card__gen"] = (at.session_state["ctry_card__gen"] + 1) if "ctry_card__gen" in at.session_state else 1
    at.run()
def btn(at, label):
    return [b for b in at.button if b.label == label][0]
errs = lambda at: [e.value for e in at.error]

at = new_at()
check("раздел открылся без ошибок", not at.exception and not errs(at), [str(e.value)[:200] for e in at.exception] + errs(at))
check("сводка списка", [c.value for c in at.caption if c.value.startswith("Показано")])
check("инструкция наверху", any("Справочник стран" in m.value for m in at.markdown))
check("форма создания на месте", any(b.label == "Создать" for b in at.button))
# пустая форма — ошибки под каждым из четырёх полей
btn(at, "Создать").click().run()
e = errs(at)
check("пустая форма: четыре ошибки, по одной на поле", len(e) == 4 and any("Alpha-2" in x for x in e)
      and any("Numeric" in x for x in e) and any("Название" in x for x in e), e)
# дубли: коды и название чужой страны, название с другим регистром и пробелами
at.text_input(key="ctry_add_a2").set_value("es"); at.text_input(key="ctry_add_a3").set_value("ESP")
at.text_input(key="ctry_add_num").set_value("724"); at.text_input(key="ctry_add_name").set_value("  spain ")
btn(at, "Создать").click().run()
e = errs(at)
check("дубли Alpha-2/Alpha-3/Numeric/названия — все четыре", len(e) == 4 and all("Spain" in x for x in e), e)
# свободная пара пользовательского диапазона ISO (XA…XZ / 900+), которой нет в справочнике
free = next(c for c in ("XA", "XB", "XC", "XD") if not one("SELECT 1 FROM kabinet_data.countries WHERE alpha2=%s", (c,)))
num = next(n for n in range(901, 999) if not one('SELECT 1 FROM kabinet_data.countries WHERE "numeric"=%s', (n,)))
at.text_input(key="ctry_add_a2").set_value(free); at.text_input(key="ctry_add_a3").set_value(free + "X")
at.text_input(key="ctry_add_num").set_value(str(num)); at.text_input(key="ctry_add_name").set_value("Testland")
btn(at, "Создать").click().run()
r = one('SELECT alpha3, "numeric", name, is_active FROM kabinet_data.countries WHERE alpha2=%s', (free,))
check(f"страна {free} создана активной", r and r[3] and r[2] == "Testland", r)
lg = one("SELECT actor FROM kabinet_data.country_change_log WHERE alpha2=%s AND field='created'", (free,))
check("журнал создания с автором", lg and lg[0] == "test@dniprom.com", lg)
check("после создания открыта её карточка", at.session_state["ctry_card"] == free if "ctry_card" in at.session_state else False)
# поиск: по Alpha-3 и по numeric с ведущими нулями
at2 = new_at()
at2.text_input(key="ctry_search").set_value("ESP").run()
cap = [c.value for c in at2.caption if c.value.startswith("Показано")]
check("поиск по Alpha-3 находит одну страну", cap and cap[0].startswith("Показано 1 "), cap)
at2.text_input(key="ctry_search").set_value("040").run()
cap = [c.value for c in at2.caption if c.value.startswith("Показано")]
check("поиск по numeric с ведущим нулём (040 — Австрия)", cap and cap[0].startswith("Показано 1 "), cap)
# переименование в чужое название — ошибка под полем, ничего не записано
at2.text_input(key="ctry_search").set_value("").run()
open_card(at2, free)
at2.text_input(key=f"cname_{free}").set_value("GERMANY")
[b for b in at2.button if b.key == f"ctry_save_{free}"][0].click().run()
check("переименование в дубль отклонено", any("Germany" in x for x in errs(at2))
      and one("SELECT name FROM kabinet_data.countries WHERE alpha2=%s", (free,))[0] == "Testland", errs(at2))
at2.text_input(key=f"cname_{free}").set_value("Testland  Two")
[b for b in at2.button if b.key == f"ctry_save_{free}"][0].click().run()
check("переименование сохранено как введено", one("SELECT name FROM kabinet_data.countries WHERE alpha2=%s", (free,))[0] == "Testland  Two")
# деактивация страны без зависимостей
at3 = new_at(); open_card(at3, free)
btn(at3, "Сделать неактивной").click().run()
check("первое нажатие ничего не пишет", one("SELECT is_active FROM kabinet_data.countries WHERE alpha2=%s", (free,))[0] is True)
check("без зависимостей сказано, что можно", any("ничего не зависит" in i.value for i in at3.info))
btn(at3, "Да, сделать неактивной").click().run()
check("страна неактивна", one("SELECT is_active FROM kabinet_data.countries WHERE alpha2=%s", (free,))[0] is False)
open_card(at3, free)
btn(at3, "Сделать активной").click().run()
check("возврат активности", one("SELECT is_active FROM kabinet_data.countries WHERE alpha2=%s", (free,))[0] is True)
# деактивация Испании: зависимости и план миграции обязательны
at4 = new_at(); open_card(at4, "ES")
btn(at4, "Сделать неактивной").click().run()
w = [x.value for x in at4.warning if "зависит" in x.value]
check("ES: показаны маркетплейсы, пулы, матрица, прогнозы, склады", w and "AMZ-ES" in w[0] and "пулы" in w[0]
      and "матриц" in w[0] and "прогноз" in w[0], w[0][:400] if w else "")
yes = btn(at4, "Да, сделать неактивной")
check("без плана миграции кнопка неактивна", yes.disabled)
at4.text_area(key="ctry_plan_ES").set_value("тест: план миграции").run()
btn(at4, "Да, сделать неактивной").click().run()
check("с планом — неактивна, план в истории", one("SELECT is_active FROM kabinet_data.countries WHERE alpha2='ES'")[0] is False
      and one("SELECT new_value FROM kabinet_data.country_change_log WHERE alpha2='ES' AND field='migration_plan' ORDER BY id DESC LIMIT 1")[0] == "тест: план миграции")
# только просмотр
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
check("Просмотр: нет формы создания и смены активности", "Создать" not in labels and "Сделать неактивной" not in labels, labels[-6:])
real.rollback(); real.close()
print("итог:", f"{sum(ok)} из {len(ok)}")
