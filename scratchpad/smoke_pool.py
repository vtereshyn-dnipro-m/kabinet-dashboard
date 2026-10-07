# -*- coding: utf-8 -*-
"""«Справочники → Пулы» на живой базе (ТЗ 004): список, создание, проверки §2/§3/§5, добавление и правка связи,
завершение участия, прекращение действия пула, запрет удаления пула со связями, режим «Просмотр».
Таблицы пулов подменяются временными копиями — всё исчезает с откатом."""
import sys, json, psycopg2, warnings, logging
from datetime import date, timedelta
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
TABLES = ("pool_members", "pool_change_log", "pools")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
for t, start in (("pools", 1000), ("pool_members", 100000), ("pool_change_log", 1000000)):
    _c.execute(f"CREATE TEMP SEQUENCE {t}_s START {start}; ALTER TABLE pg_temp.{t} ALTER id SET DEFAULT nextval('{t}_s')")
def _rw(sql):
    if isinstance(sql, str):
        for t in TABLES:
            sql = sql.replace(f"kabinet_data.{t} ", f"pg_temp.{t} ").replace(f"kabinet_data.{t}\n", f"pg_temp.{t}\n") \
                     .replace(f"kabinet_data.{t}(", f"pg_temp.{t}(").replace(f"kabinet_data.{t},", f"pg_temp.{t},")
            if sql.rstrip().endswith(f"kabinet_data.{t}"):
                sql = sql.rstrip()[: -len(f"kabinet_data.{t}")] + f"pg_temp.{t}"
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
import pandas as pd
_orig_read_sql = pd.read_sql
pd.read_sql = lambda sql, con=None, *a, **k: _orig_read_sql(_rw(sql), real, *a, **k)
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
def mp(code):
    return one("SELECT id FROM kabinet_data.marketplaces_new WHERE code=%s", (code,))[0]
ok = []
def check(name, cond, extra=""):
    ok.append(bool(cond)); print(("  ок   " if cond else "  ПРОВАЛ ") + name + (f" — {extra}" if extra else ""))
def new_at(card=None):
    at = AppTest.from_file(f"{R}/pages/6_Dictionaries.py", default_timeout=300)
    at.session_state["dict_section"] = "pool"; at.session_state["dict_section_last"] = "pool"
    if card is not None:
        at.session_state["pool_card"] = card; at.session_state["pool_card__gen"] = 7
    at.run(); return at
def btn(at, label):
    return [b for b in at.button if b.label == label][0]
def create(at, name, codes, d_from=None, d_last=None):
    at.text_input(key="pool_add_name").set_value(name)
    at.multiselect(key="pool_add_mps").set_value([mp(c) for c in codes])
    if d_from: at.date_input(key="pool_add_from").set_value(d_from)
    if d_last: at.date_input(key="pool_add_last").set_value(d_last)
    btn(at, "➕ Создать пул").click().run()
    return at

at = new_at()
check("раздел открылся без ошибок", not at.exception and not at.error,
      [str(e.value)[:200] for e in at.exception] + [e.value for e in at.error])
check("сводка списка", [c.value for c in at.caption if c.value.startswith("Показано")])
check("форма создания на месте", any(b.label == "➕ Создать пул" for b in at.button))

at = create(new_at(), "Тест один", ["AMZ-ES"])
check("§2: пул из одного маркетплейса отклонён", any("минимум из двух" in e.value for e in at.error), [e.value for e in at.error])
at = create(new_at(), "Тест страны", ["AMZ-ES", "AMZ-FR"])
check("§2: разные страны отклонены текстом ТЗ", any("страна выбранного marketplace отличается" in e.value for e in at.error), [e.value for e in at.error])
at = create(new_at(), "Тест пересечение", ["AMZ-ES", "LM-ES"])
check("§5: маркетплейс уже в другом пуле — отказ с именем пула", any("Spain Marketplaces" in e.value for e in at.error), [e.value for e in at.error])
at = create(new_at(), "Spain Marketplaces", ["AMZ-ES", "TTS-ES"])
check("§3: дубль названия отклонён", any("уже есть" in e.value for e in at.error), [e.value for e in at.error])

at = create(new_at(), "Тест ES", ["AMZ-ES", "TTS-ES"])
r = one("SELECT id FROM kabinet_data.pools WHERE name='Тест ES'")
check("пул создан", r, [e.value for e in at.error])
pid = r[0] if r else None
if pid:
    n = one("SELECT count(*), min(valid_from), max(valid_to) FROM kabinet_data.pool_members WHERE pool_id=%s", (pid,))
    lg = one("SELECT action, after_state->>'name' FROM kabinet_data.pool_change_log WHERE pool_id=%s", (pid,))
    check("две связи с сегодняшней датой, без срока; журнал create", n[0] == 2 and n[1] == date.today() and n[2] is None
          and lg and lg[0] == "create", (n, lg))
    check("после создания открыта его карточка", at.session_state["pool_card"] == pid)

    at = new_at(pid)
    check("карточка открылась без ошибок", not at.exception and not at.error, [e.value for e in at.error])
    at.selectbox(key=f"pal_mp_{pid}").set_value(mp("LM-ES"))
    btn(at, "Добавить в пул").click().run()
    check("добавление маркетплейса из чужого пула отклонено", any("Spain Marketplaces" in e.value for e in at.error),
          [e.value for e in at.error])

    lid = one("SELECT id FROM kabinet_data.pool_members WHERE pool_id=%s AND marketplace_id=%s", (pid, mp("TTS-ES")))[0]
    at = new_at(pid)
    at.selectbox(key=f"pel_{pid}").set_value(lid).run()
    at.date_input(key=f"pel_l_{pid}_{lid}").set_value(date.today() - timedelta(days=3))
    btn(at, "💾 Сохранить даты").click().run()
    check("§4: последний день раньше начала отклонён", any("раньше даты начала" in e.value for e in at.error),
          [e.value for e in at.error])

    at = new_at(pid)
    at.selectbox(key=f"pel_{pid}").set_value(lid).run()
    btn(at, "⏹ Завершить сегодня").click().run()
    vt = one("SELECT valid_to FROM kabinet_data.pool_members WHERE id=%s", (lid,))[0]
    check("завершить сегодня: valid_to = завтра (последний день — сегодня)", vt == date.today() + timedelta(days=1), vt)
    at = new_at(pid)
    check("с одним участником пул всё ещё действует сегодня (последний день — сегодня)",
          not any("Пул не действует" in w.value for w in at.warning), [w.value for w in at.warning])

    at = new_at(pid)
    btn(at, "Прекратить действие пула…").click().run()
    btn(at, "Да, прекратить").click().run()
    left = one("SELECT count(*) FROM kabinet_data.pool_members WHERE pool_id=%s AND (valid_to IS NULL OR valid_to > CURRENT_DATE + 1)", (pid,))[0]
    acts = one("SELECT string_agg(action, ',' ORDER BY id) FROM kabinet_data.pool_change_log WHERE pool_id=%s", (pid,))[0]
    check("прекращение: ни одной связи без последнего дня, журнал полный", left == 0
          and acts == "create,link_close,pool_close", (left, acts))
    at = new_at(pid)
    check("удаление пула со связями запрещено, причина названа", any("Удалить пул нельзя" in c.value for c in at.caption)
          and not any(b.label.startswith("🗑") for b in at.button), [c.value[:80] for c in at.caption if "Удалить" in c.value])

ROLE[0] = auth.VIEWER
at = new_at()
check("«Просмотр»: формы создания нет, сказано почему", not any(b.label == "➕ Создать пул" for b in at.button)
      and any("на чтение" in c.value for c in at.caption))
real.rollback()
print(f"\nитог: {sum(ok)} из {len(ok)}")
sys.exit(0 if all(ok) else 1)
