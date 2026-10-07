# -*- coding: utf-8 -*-
"""«Справочники → Площадки» на живой базе: список, создание, дубль пары, ошибки формы, архив с
подтверждением, возврат, режим «Просмотр». Таблицы маркетплейсов подменяются временными копиями
(роль теста не может писать в таблицу владельца), всё откатывается."""
import sys, json, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
# Роль теста не может писать в таблицу владельца marketplaces_new (у приложения право есть).
# Поэтому три таблицы маркетплейсов подменяются временными копиями: запросы переписываются на
# pg_temp, данные те же, всё исчезает с откатом.
TABLES = ("platforms", "platform_attributes", "marketplace_change_log")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_c.execute("CREATE TEMP SEQUENCE mp_seq START 1000; ALTER TABLE pg_temp.platforms ALTER id SET DEFAULT nextval('mp_seq')")
_c.execute("CREATE TEMP SEQUENCE log_seq START 1000000; ALTER TABLE pg_temp.marketplace_change_log ALTER id SET DEFAULT nextval('log_seq')")
def _rw(sql):
    if isinstance(sql, str):
        for t in TABLES:
            sql = sql.replace(f"kabinet_data.{t}", f"pg_temp.{t}")
    return sql
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
    at.session_state["dict_section"] = "plat"; at.session_state["dict_section_last"] = "plat"
    at.run(); return at
at = new_at()
check("раздел открылся без ошибок", not at.exception and not at.error, [str(e.value)[:150] for e in at.exception] + [e.value for e in at.error])
check("сводка и список", [c.value for c in at.caption if c.value.startswith("Показано")])
check("форма создания на месте", any(b.label == "Создать" for b in at.button))
at.text_input(key="plat_add_short").set_value("otto"); at.text_input(key="plat_add_name").set_value("OTTO")
at.text_input(key="plat_add_pe").set_value("OTTO-ID")
[b for b in at.button if b.label == "Создать"][0].click().run()
r = one("SELECT id, short_name FROM kabinet_data.platforms WHERE short_name='OTTO'")
check("площадка создана, краткое название приведено к заглавным", r, r)
if r:
    a = one("SELECT is_active, product_entity_label FROM kabinet_data.platform_attributes WHERE platform_id=%s", (r[0],))
    lg = one("SELECT object_id, new_value FROM kabinet_data.marketplace_change_log WHERE object_type='platform' AND field='created' AND new_value LIKE 'OTTO%%'")
    check("активна, обозначение записано, журнал привязан к её id", a and a[0] and a[1] == "OTTO-ID" and lg and lg[0] == r[0], (a, lg))
    check("после создания открыта её карточка", at.session_state["plat_card"] == r[0], [x.value for x in at.success])
at.text_input(key="plat_add_short").set_value("AMZ"); at.text_input(key="plat_add_name").set_value("Dup")
[b for b in at.button if b.label == "Создать"][0].click().run()
check("дубль краткого названия отклонён", any("уже есть" in e.value for e in at.error), [e.value for e in at.error])
at2 = new_at()
at2.text_input(key="plat_add_short").set_value("A-1"); at2.text_input(key="plat_add_name").set_value("")
[b for b in at2.button if b.label == "Создать"][0].click().run()
errs = [e.value for e in at2.error]
check("неверное краткое и пустое название — две ошибки", len(errs) == 2, errs)
if r:
    at3 = new_at(); at3.session_state["plat_card"] = r[0]; at3.session_state["plat_card__gen"] = at3.session_state["plat_card__gen"] + 1 if "plat_card__gen" in at3.session_state else 1; at3.run()
    [b for b in at3.button if b.label == "В архив"][0].click().run()
    check("первое «В архив» ничего не пишет", one("SELECT is_active FROM kabinet_data.platform_attributes WHERE platform_id=%s", (r[0],))[0] is True)
    [b for b in at3.button if b.label == "Да, в архив"][0].click().run()
    check("«Да, в архив» — в архиве", one("SELECT is_active FROM kabinet_data.platform_attributes WHERE platform_id=%s", (r[0],))[0] is False)
    at3.selectbox(key="plat_state_f").set_value("all").run()
    at3.session_state["plat_card"] = r[0]; at3.session_state["plat_card__gen"] = at3.session_state["plat_card__gen"] + 1 if "plat_card__gen" in at3.session_state else 1; at3.run()
    [b for b in at3.button if b.label == "Вернуть из архива"][0].click().run()
    check("возврат из архива", one("SELECT is_active FROM kabinet_data.platform_attributes WHERE platform_id=%s", (r[0],))[0] is True)
amz = one("SELECT id FROM kabinet_data.platforms WHERE short_name='AMZ'")[0]
at4 = new_at(); at4.session_state["plat_card"] = amz; at4.session_state["plat_card__gen"] = at4.session_state["plat_card__gen"] + 1 if "plat_card__gen" in at4.session_state else 1; at4.run()
[b for b in at4.button if b.label == "В архив"][0].click().run()
w = [x.value for x in at4.warning if "связано" in x.value]
check("AMZ: перед архивом видны связи площадки и её маркетплейсов", w, w[0][:400] if w else "")
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
check("Просмотр: нет архива и формы", "В архив" not in labels and "Создать" not in labels, labels[-5:])
sv = [b for b in at5.button if b.label.endswith("Сохранить изменения")]
check("Просмотр: «Сохранить» неактивна", sv and all(b.disabled for b in sv))
real.rollback(); real.close()
print("ИТОГ:", "ок" if all(ok) else "ПРОВАЛ", f"{sum(ok)}/{len(ok)}")
