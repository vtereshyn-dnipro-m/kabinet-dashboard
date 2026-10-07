# -*- coding: utf-8 -*-
"""«Справочники → Нормативы» на живой базе: список, добавление, карточка по клику, пересмотр новой версией (прежняя
закрывается днём раньше), закрытие датой в два шага, журнал правила, «Просмотр». Таблицы нормативов подменяются
временными копиями — данные не меняются, всё исчезает с откатом."""
import sys, json, re, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
TABLES = ("coverage_norm_rules", "coverage_norm_log")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_c.execute("CREATE TEMP SEQUENCE nr_s START 100000; ALTER TABLE pg_temp.coverage_norm_rules ALTER id SET DEFAULT nextval('nr_s')")
_c.execute("CREATE TEMP SEQUENCE nl_s START 1000000; ALTER TABLE pg_temp.coverage_norm_log ALTER id SET DEFAULT nextval('nl_s')")
_RX = re.compile(r"kabinet_data\.(coverage_norm_rules|coverage_norm_log)\b")
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
    at.session_state["dict_section"] = "norm"; at.session_state["dict_section_last"] = "norm"
    at.run(); return at
def open_card(at, cid):
    at.session_state["norm_card"] = cid
    at.session_state["norm_card__gen"] = (at.session_state["norm_card__gen"] + 1) if "norm_card__gen" in at.session_state else 1
    at.run()
def btn(at, label):
    return [b for b in at.button if b.label == label][0]
errs = lambda at: [e.value for e in at.error]

from datetime import date, timedelta
today = date.today()
at = new_at()
check("раздел открылся без ошибок", not at.exception and not errs(at), [str(e.value)[:200] for e in at.exception] + errs(at))
check("инструкция наверху", any("Нормативы покрытия" in m.value for m in at.markdown))
check("форма добавления на месте", any(b.label == "Добавить норматив" for b in at.button))
n0 = one("SELECT count(*) FROM kabinet_data.coverage_norm_rules")[0]
# порядок порогов
at.number_input(key="norm_mn").set_value(70); at.number_input(key="norm_tg").set_value(60)
btn(at, "Добавить норматив").click().run()
check("минимум > цели отклонён", any("минимум" in x for x in errs(at)) and one("SELECT count(*) FROM kabinet_data.coverage_norm_rules")[0] == n0, errs(at))
# норматив «по умолчанию» на маркетплейс
at.radio(key="norm_lvl").set_value("default").run()
at.number_input(key="norm_mn").set_value(30); at.number_input(key="norm_tg").set_value(60); at.number_input(key="norm_mx").set_value(90)
btn(at, "Добавить норматив").click().run()
r = one("SELECT id, level, min_days, target_days, max_days, effective_from, updated_by FROM kabinet_data.coverage_norm_rules ORDER BY id DESC LIMIT 1")
check("норматив создан, автор — пользователь", r and r[1] == "default" and r[2:5] == (30, 60, 90) and r[6] == "test@dniprom.com", r)
rid = r[0]
check("журнал: created", one("SELECT action FROM kabinet_data.coverage_norm_log WHERE rule_id=%s", (rid,)) == ("created",))
# карточка и пересмотр
at2 = new_at(); open_card(at2, rid)
check("карточка открылась", any(f"#{rid}" in m.value for m in at2.markdown), [m.value[:60] for m in at2.markdown][-5:])
at2.number_input(key=f"norm_rev_tg_{rid}").set_value(75)
at2.date_input(key=f"norm_rev_from_{rid}").set_value(today + timedelta(days=10))
[b for b in at2.button if b.key == f"norm_rev_btn_{rid}"][0].click().run()
old = one("SELECT effective_to FROM kabinet_data.coverage_norm_rules WHERE id=%s", (rid,))
new = one("SELECT id, target_days, effective_from FROM kabinet_data.coverage_norm_rules WHERE id > %s ORDER BY id DESC LIMIT 1", (rid,))
check("пересмотр: прежняя закрыта днём раньше, новая с даты", old[0] == today + timedelta(days=9)
      and new and new[1] == 75 and new[2] == today + timedelta(days=10), (old, new))
# новая версия — «с будущей даты»: в её карточке нет пересмотра и закрытия
at3 = new_at(); at3.selectbox(key="norm_state_f").set_value("all").run(); open_card(at3, new[0])
check("будущая версия: пересмотра и закрытия нет, сказано почему",
      not any(b.key == f"norm_rev_btn_{new[0]}" for b in at3.button) and any("будущей даты" in c.value for c in at3.caption))
# закрытие действующей в два шага
at4 = new_at(); open_card(at4, rid)
[b for b in at4.button if b.key == f"ask_normclose_{rid}"][0].click().run()
check("первое нажатие ничего не закрывает", one("SELECT effective_to FROM kabinet_data.coverage_norm_rules WHERE id=%s", (rid,))[0] == today + timedelta(days=9))
[b for b in at4.button if b.key == f"yes_normclose_{rid}"][0].click().run()
check("второе — закрыт сегодняшней датой, в журнале closed",
      one("SELECT effective_to FROM kabinet_data.coverage_norm_rules WHERE id=%s", (rid,))[0] == today
      and one("SELECT count(*) FROM kabinet_data.coverage_norm_log WHERE rule_id=%s AND action='closed'", (rid,))[0] >= 2)
# только просмотр
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
check("Просмотр: формы добавления нет", "Добавить норматив" not in labels, labels[-6:])
real.rollback(); real.close()
print("итог:", f"{sum(ok)} из {len(ok)}")
