# -*- coding: utf-8 -*-
"""«Справочники → Категории» на живой базе: три части (связи SKU, дерево, жизненный цикл), карточки по клику,
ручная категория и её снятие, своя подпись узла, отложенное решение по статусу и его отмена, «Просмотр».
Таблицы, в которые пишет раздел, подменяются временными копиями — данные не меняются, всё исчезает с откатом."""
import sys, json, re, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
TABLES = ("sku_category_links", "category_names", "sku_lifecycle_manual")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_RX = re.compile(r"kabinet_data\.(sku_category_links|category_names|sku_lifecycle_manual)\b")
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
    at.session_state["dict_section"] = "cat"; at.session_state["dict_section_last"] = "cat"
    at.run(); return at
def open_card(at, key, cid):
    at.session_state[key] = cid
    at.session_state[key + "__gen"] = (at.session_state[key + "__gen"] + 1) if key + "__gen" in at.session_state else 1
    at.run()
def part(at, p):
    at.session_state["cat_part"] = p; at.run()
def btn(at, label):
    return [b for b in at.button if b.label == label][0]
errs = lambda at: [e.value for e in at.error]

from datetime import date, timedelta
at = new_at()
check("раздел открылся без ошибок", not at.exception and not errs(at), [str(e.value)[:200] for e in at.exception] + errs(at))
check("инструкция наверху", any("Категории товаров" in m.value for m in at.markdown))
check("по умолчанию — связи SKU, карточка SKU на месте", any(m.value == "#### Карточка SKU" for m in at.markdown))
# связи: ручная категория и её снятие
sku = one("SELECT l.sku FROM kabinet_data.sku_category_links l WHERE l.key_source = 'erp' ORDER BY 1 LIMIT 1")[0]
key2 = one("SELECT category_key FROM kabinet_data.sku_category_tree WHERE depth = 3 AND category_key <> (SELECT category_key FROM kabinet_data.sku_category_links WHERE sku = %s) ORDER BY 1 LIMIT 1", (sku,))[0]
open_card(at, "cat_link_card", sku)
at.selectbox(key=f"cat_link_sel_{sku}").set_value(key2)
[b for b in at.button if b.key == f"cat_link_save_{sku}"][0].click().run()
r = one("SELECT category_key, key_source, updated_by FROM kabinet_data.sku_category_links WHERE sku = %s", (sku,))
check("ручная категория поставлена, автор — пользователь", r == (key2, "manual", "test@dniprom.com"), r)
open_card(at, "cat_link_card", sku)
[b for b in at.button if b.key == f"ask_catlink_{sku}"][0].click().run()
check("первое нажатие «снять» ничего не снимает", one("SELECT key_source FROM kabinet_data.sku_category_links WHERE sku = %s", (sku,)) == ("manual",))
[b for b in at.button if b.key == f"yes_catlink_{sku}"][0].click().run()
check("второе — ручная связь снята", one("SELECT 1 FROM kabinet_data.sku_category_links WHERE sku = %s", (sku,)) is None)
# дерево: своя подпись узла
at2 = new_at(); part(at2, "tree")
check("дерево открылось без ошибок", not at2.exception and not errs(at2), errs(at2))
node = one("SELECT category_key FROM kabinet_data.sku_category_tree WHERE depth = 2 ORDER BY 1 LIMIT 1")[0]
open_card(at2, "cat_node_card", node)
at2.text_input(key=f"cat_n_ru_{node}").set_value("Тестовая подпись")
[b for b in at2.button if b.key == f"cat_n_save_{node}"][0].click().run()
check("своя подпись узла сохранена", one("SELECT name_ru FROM kabinet_data.category_names WHERE category_key = %s", (node,)) == ("Тестовая подпись",))
# жизненный цикл: отложенное решение и его отмена
at3 = new_at(); part(at3, "life")
check("жизненный цикл открылся без ошибок", not at3.exception and not errs(at3), errs(at3))
pair = one("SELECT sku, marketplace FROM kabinet_data.v_sku_lifecycle_current ORDER BY 1, 2 LIMIT 1")
k = f"{pair[0]}|{pair[1]}"
open_card(at3, "cat_life_card", k)
fut = date.today() + timedelta(days=25)
at3.selectbox(key=f"cat_life_c_{k}_st").set_value("phasing_out")
at3.date_input(key=f"cat_life_c_{k}_from").set_value(fut)
at3.text_input(key=f"cat_life_c_{k}_why").set_value("тест")
[b for b in at3.button if b.key == f"cat_life_c_{k}_btn"][0].click().run()
check("отложенное решение записано", one("SELECT status, effective_from FROM kabinet_data.sku_lifecycle_manual WHERE sku=%s AND marketplace=%s", pair) == ("phasing_out", fut))
open_card(at3, "cat_life_card", k)
ck = f"catlife_{pair[0]}_{pair[1]}_{fut}"
[b for b in at3.button if b.key == f"ask_{ck}"][0].click().run()
[b for b in at3.button if b.key == f"yes_{ck}"][0].click().run()
check("ненаступившее решение отменено", one("SELECT 1 FROM kabinet_data.sku_lifecycle_manual WHERE sku=%s AND marketplace=%s", pair) is None)
# только просмотр
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
dis = [b.disabled for b in at5.button if b.label == "Связать"]
check("Просмотр: «Связать» неактивна", dis and all(dis), (labels[-6:], dis))
real.rollback(); real.close()
print("итог:", f"{sum(ok)} из {len(ok)}")
