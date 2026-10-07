# -*- coding: utf-8 -*-
"""«Справочники → Маркетплейсы» на живой базе: список, создание, дубль пары, ошибки формы, архив с
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
TABLES = ("marketplaces_new", "marketplace_attributes", "marketplace_change_log")
_c = real.cursor()
for t in TABLES:
    _c.execute(f"CREATE TEMP TABLE {t} (LIKE kabinet_data.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)")
    _c.execute(f"INSERT INTO pg_temp.{t} SELECT * FROM kabinet_data.{t}")
_c.execute("CREATE TEMP SEQUENCE mp_seq START 1000; ALTER TABLE pg_temp.marketplaces_new ALTER id SET DEFAULT nextval('mp_seq')")
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
    at.session_state["dict_section"] = "mp"; at.session_state["dict_section_last"] = "mp"
    at.run(); return at
at = new_at()
check("раздел открылся без ошибок", not at.exception and not [e for e in at.error], [str(e.value)[:150] for e in at.exception] + [e.value for e in at.error])
cap = [c.value for c in at.caption if c.value.startswith("Показано")]
check("сводка над списком", cap, cap)
check("форма создания на месте", any(b.label == "Добавить маркетплейс" for b in at.button))
# создание: свободная пара TikTok Shop + страна. Пару подбираем, а не зашиваем: 07.10.2026 в живой базе появился
# TTS-IT, и тест, заводивший именно его, падал на чужих данных
FREE = next(c for c in ("PT", "AT", "NL", "BE", "PL", "SE", "IE", "CZ")
            if not one("SELECT 1 FROM kabinet_data.marketplaces_new WHERE platform_short='TTS' AND country_alpha2=%s", (c,))
            and one("SELECT 1 FROM kabinet_data.countries WHERE alpha2=%s", (c,)))
CODE = f"TTS-{FREE}"
at.selectbox(key="mp_add_plat").set_value("TTS"); at.selectbox(key="mp_add_ctry").set_value(FREE)
at.selectbox(key="mp_add_curr").set_value("EUR"); at.text_input(key="mp_add_name").set_value("TikTok Shop Test")
at.text_input(key="mp_add_site").set_value("https://shop.tiktok.com/it")
[b for b in at.button if b.label == "Добавить маркетплейс"][0].click().run()
r = one("SELECT id, code, is_active, currency FROM kabinet_data.marketplaces_new WHERE code=%s", (CODE,))
check(f"маркетплейс создан ({CODE}), код собран, активен", r and r[1] == CODE and r[2], r)
if r:
    a = one("SELECT website_url FROM kabinet_data.marketplace_attributes WHERE marketplace_id=%s", (r[0],))
    lg = one("SELECT field, new_value, actor FROM kabinet_data.marketplace_change_log WHERE object_id=%s AND field='created'", (r[0],))
    check("реквизиты и журнал записаны", a and a[0] == "https://shop.tiktok.com/it" and lg, (a, lg))
    check("после создания открыта его карточка", at.session_state["mp_card"] == r[0] if "mp_card" in at.session_state else False,
          [s.value for s in at.success])
# дубль активной пары
at.selectbox(key="mp_add_plat").set_value("AMZ"); at.selectbox(key="mp_add_ctry").set_value("ES")
at.selectbox(key="mp_add_curr").set_value("EUR"); at.text_input(key="mp_add_name").set_value("Dup")
[b for b in at.button if b.label == "Добавить маркетплейс"][0].click().run()
check("дубль пары «площадка + страна» отклонён", any("уже есть" in e.value for e in at.error), [e.value for e in at.error])
# без валюты и ссылка без https
at2 = new_at()
at2.selectbox(key="mp_add_plat").set_value("TTS"); at2.selectbox(key="mp_add_ctry").set_value("DE")
at2.text_input(key="mp_add_name").set_value("X"); at2.text_input(key="mp_add_site").set_value("http://x.de")
[b for b in at2.button if b.label == "Добавить маркетплейс"][0].click().run()
errs = [e.value for e in at2.error]
check("без валюты и с http:// — две ошибки, ничего не создано",
      any("валюту" in e for e in errs) and any("https" in e for e in errs) and not one("SELECT 1 FROM kabinet_data.marketplaces_new WHERE code='TTS-DE'"), errs)
# архив и возврат на созданном
if r:
    at3 = new_at()
    at3.session_state["mp_card"] = r[0]; at3.session_state["mp_card__gen"] = at3.session_state["mp_card__gen"] + 1 if "mp_card__gen" in at3.session_state else 1; at3.run()
    [b for b in at3.button if b.label == "В архив"][0].click().run()
    check("первое нажатие «В архив» ничего не пишет", one("SELECT is_active FROM kabinet_data.marketplaces_new WHERE id=%s", (r[0],))[0] is True)
    check("второе нажатие спрашивает подтверждение", any(b.label == "Да, в архив" for b in at3.button))
    [b for b in at3.button if b.label == "Да, в архив"][0].click().run()
    check("после «Да» — в архиве", one("SELECT is_active FROM kabinet_data.marketplaces_new WHERE id=%s", (r[0],))[0] is False)
    at3.selectbox(key="mp_state_f").set_value("all").run()
    at3.session_state["mp_card"] = r[0]; at3.session_state["mp_card__gen"] = at3.session_state["mp_card__gen"] + 1 if "mp_card__gen" in at3.session_state else 1; at3.run()
    [b for b in at3.button if b.label == "Вернуть из архива"][0].click().run()
    check("возврат из архива", one("SELECT is_active FROM kabinet_data.marketplaces_new WHERE id=%s", (r[0],))[0] is True)
# зависимости перед архивом у живого маркетплейса
at4 = new_at()
at4.session_state["mp_card"] = 1; at4.session_state["mp_card__gen"] = at4.session_state["mp_card__gen"] + 1 if "mp_card__gen" in at4.session_state else 1; at4.run()
[b for b in at4.button if b.label == "В архив"][0].click().run()
w = [x.value for x in at4.warning if "связано" in x.value]
check("AMZ-ES: перед архивом показаны действующие связи", w, w[0][:300] if w else "")
check("AMZ-ES не тронут (ждёт подтверждения)", one("SELECT is_active FROM kabinet_data.marketplaces_new WHERE id=1")[0] is True)
# только просмотр
ROLE[0] = auth.VIEWER
at5 = new_at()
labels = [b.label for b in at5.button]
check("Просмотр: нет архива и формы создания", "В архив" not in labels and "Добавить маркетплейс" not in labels, labels[-6:])
sv = [b for b in at5.button if b.label.endswith("Сохранить изменения")]
check("Просмотр: «Сохранить» неактивна", sv and all(b.disabled for b in sv), [(b.label, b.disabled) for b in sv])
real.rollback(); real.close()
print("ИТОГ:", "ок" if all(ok) else "ПРОВАЛ", f"{sum(ok)}/{len(ok)}")
