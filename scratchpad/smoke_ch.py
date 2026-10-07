# -*- coding: utf-8 -*-
"""«Справочники → Подпитка» на живой базе: список и поиск, создание с проверками, карточка, правка срока с журналом,
архив ключевого плеча с предупреждением, удаление только из архива, «Просмотр». Таблицы подпитки подменяются
временными копиями — данные не меняются, всё исчезает с откатом."""
import sys, json, re, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"; sys.path.insert(0, R)
DSN = json.load(open(f"{R}/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
real = psycopg2.connect(DSN)
TABLES = ("supply_chains", "supply_chain_change_log")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_c.execute("CREATE TEMP SEQUENCE sc_s START 100000; ALTER TABLE pg_temp.supply_chains ALTER id SET DEFAULT nextval('sc_s')")
_c.execute("CREATE TEMP SEQUENCE scl_s START 1000000; ALTER TABLE pg_temp.supply_chain_change_log ALTER id SET DEFAULT nextval('scl_s')")
_RX = re.compile(r"kabinet_data\.(supply_chains|supply_chain_change_log)\b")
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
    at.session_state["dict_section"] = "ch"; at.session_state["dict_section_last"] = "ch"
    at.run(); return at
def open_card(at, cid):
    at.session_state["ch_card"] = cid
    at.session_state["ch_card__gen"] = (at.session_state["ch_card__gen"] + 1) if "ch_card__gen" in at.session_state else 1
    at.run()
def btn(at, label):
    return [b for b in at.button if b.label == label][0]
errs = lambda at: [e.value for e in at.error]

at = new_at()
check("раздел открылся без ошибок", not at.exception and not errs(at), [str(e.value)[:200] for e in at.exception] + errs(at))
check("инструкция наверху", any("Подпитка" in m.value for m in at.markdown))
cap = [c.value for c in at.caption if c.value.startswith("Показано")]
check("сводка списка", cap, cap)
at.text_input(key="ch_search").set_value("Piasecznie").run()
cap2 = [c.value for c in at.caption if c.value.startswith("Показано")]
check("поиск по складу сужает список", cap2 and cap2 != cap, cap2)
at.text_input(key="ch_search").set_value("").run()
# пустая форма
btn(at, "Добавить связь").click().run()
e = errs(at)
check("пустая форма: нет складов и срока", any("источник" in x for x in e) and any("срок" in x for x in e), e)
# существующая пара Piasecznie → Мадрид
at.selectbox(key="ch_add_src").set_value(32); at.selectbox(key="ch_add_rec").set_value(43)
at.number_input(key="ch_add_days").set_value(5)
btn(at, "Добавить связь").click().run()
check("дубль пары отклонён", any("уже есть" in x for x in errs(at)), errs(at))
at.selectbox(key="ch_add_rec").set_value(32)
btn(at, "Добавить связь").click().run()
check("источник = получатель отклонён", any("не могут совпадать" in x for x in errs(at)), errs(at))
# свободная пара активных складов
pair = one("""SELECT a.id, b.id FROM kabinet_data.warehouses a, kabinet_data.warehouses b
              WHERE a.id <> b.id AND a.is_active IS NOT FALSE AND b.is_active IS NOT FALSE
                AND NOT EXISTS (SELECT 1 FROM kabinet_data.supply_chains c
                                WHERE c.from_warehouse_id = a.id AND c.to_warehouse_id = b.id)
              ORDER BY a.id, b.id LIMIT 1""")
at.selectbox(key="ch_add_src").set_value(pair[0]); at.selectbox(key="ch_add_rec").set_value(pair[1])
at.selectbox(key="ch_add_type").set_value("internal"); at.number_input(key="ch_add_days").set_value(9)
btn(at, "Добавить связь").click().run()
r = one("SELECT id, median_days, lead_source, is_active FROM kabinet_data.supply_chains WHERE from_warehouse_id=%s AND to_warehouse_id=%s", pair)
check("связь создана: срок 9, основание вручную, активна", r and r[1] == 9 and r[2] == "expert" and r[3], r)
lg = one("SELECT actor FROM kabinet_data.supply_chain_change_log WHERE chain_id=%s AND field='created'", (r[0],)) if r else None
check("журнал создания с автором", lg and lg[0] == "test@dniprom.com", lg)
check("после создания открыта её карточка", "ch_card" in at.session_state and r and at.session_state["ch_card"] == r[0])
new_id = r[0]
# правка срока у связи с основанием «по накладным»
ttn = one("SELECT id, median_days FROM kabinet_data.supply_chains WHERE lead_source='ttn_planned' AND is_active ORDER BY id LIMIT 1")
at2 = new_at(); open_card(at2, ttn[0])
at2.number_input(key=f"ch_days_{ttn[0]}").set_value(int(ttn[1]) + 1)
[b for b in at2.button if b.key == f"ch_save_{ttn[0]}"][0].click().run()
r2 = one("SELECT median_days, lead_source FROM kabinet_data.supply_chains WHERE id=%s", (ttn[0],))
lg2 = one("SELECT old_value, new_value FROM kabinet_data.supply_chain_change_log WHERE chain_id=%s AND field='median_days'", (ttn[0],))
check("срок сохранён, основание стало «вручную», в журнале было → стало", r2 == (int(ttn[1]) + 1, "expert")
      and lg2 == (str(int(ttn[1])), str(int(ttn[1]) + 1)), (r2, lg2))
# архив ключевого плеча — предупреждение про автозаказ
leg = one("SELECT id FROM kabinet_data.supply_chains WHERE from_warehouse_id=32 AND to_warehouse_id=43")
at3 = new_at(); open_card(at3, leg[0])
btn(at3, "В архив").click().run()
w = [x.value for x in at3.warning if "автозаказ" in x.value]
check("ключевое плечо: предупреждение, что автозаказ возьмёт оценку", w, w)
check("первое нажатие ничего не пишет", one("SELECT is_active FROM kabinet_data.supply_chains WHERE id=%s", leg)[0] is True)
btn(at3, "Да, в архив").click().run()
check("после «Да» — в архиве, в журнале активность",
      one("SELECT is_active FROM kabinet_data.supply_chains WHERE id=%s", leg)[0] is False
      and one("SELECT 1 FROM kabinet_data.supply_chain_change_log WHERE chain_id=%s AND field='is_active'", leg))
# удаление: только из архива, в два шага
at4 = new_at(); open_card(at4, new_id)
check("у активной связи кнопки удаления нет", not any("Удалить" in b.label for b in at4.button))
btn(at4, "В архив").click().run(); btn(at4, "Да, в архив").click().run()
at4.selectbox(key="ch_state_f").set_value("all").run(); open_card(at4, new_id)
[b for b in at4.button if b.key == f"ask_ch_{new_id}"][0].click().run()
check("первое нажатие «Удалить» ничего не удаляет", one("SELECT 1 FROM kabinet_data.supply_chains WHERE id=%s", (new_id,)))
[b for b in at4.button if b.key == f"yes_ch_{new_id}"][0].click().run()
check("второе — удалено, в журнале «deleted»", not one("SELECT 1 FROM kabinet_data.supply_chains WHERE id=%s", (new_id,))
      and one("SELECT 1 FROM kabinet_data.supply_chain_change_log WHERE chain_id=%s AND field='deleted'", (new_id,)))
# только просмотр
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
check("Просмотр: нет формы и архива", "Добавить связь" not in labels and "В архив" not in labels, labels[-6:])
real.rollback(); real.close()
print("итог:", f"{sum(ok)} из {len(ok)}")
