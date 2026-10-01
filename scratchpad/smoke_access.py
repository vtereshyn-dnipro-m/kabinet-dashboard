# -*- coding: utf-8 -*-
"""«Доступ» глазами администратора, на живой базе.

smoke_full открывает эту страницу от невошедшего и видит один отказ — то есть новые
вкладки он не проверяет вовсе. Здесь подменяется только «кто смотрит»; данные, запросы
и виджеты настоящие.
"""
import sys, json, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import db.connection as dbc
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
dbc.get_connection = lambda: psycopg2.connect(DSN)
import streamlit as st
st.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest

SQLISH = ("syntax", "column", "relation", "does not exist", "group by", "psycopg2",
          "operator", "не прочиталось", "undefined")
R = "/Users/vitter/Documents/Code/kabinet-dashboard"

def прогнать(кто: str, роль: str):
    at = AppTest.from_file(f"{R}/pages/10_Access.py", default_timeout=300)
    at.session_state["_smoke_role"] = роль
    # подменяем только «кто смотрит»
    at.run()
    return at

# подмена делается импортом модуля до прогона страницы
import auth
auth.mode = lambda: auth.MODE_ON
_кто = auth.User(email="test@dniprom.com", role=auth.ADMIN, logged_in=True, known=True)
auth.current = lambda: _кто

беда = 0
at = AppTest.from_file(f"{R}/pages/10_Access.py", default_timeout=300)
at.run()
exc = [str(e.value).strip().splitlines()[-1][:160] for e in at.exception]
errs = [str(e.value)[:160] for e in at.error if any(w in str(e.value).lower() for w in SQLISH)]
отказ = [str(e.value)[:80] for e in at.error if "прав" in str(e.value).lower()]
плохо = exc + errs
if отказ:
    плохо.append("страница отказала администратору: " + отказ[0])
видно = sum(len(getattr(at, имя, [])) for имя in
            ("title", "markdown", "dataframe", "metric", "caption", "error", "info", "warning"))
if not видно:
    плохо.append("прогон пустой")

вкладки = [tab for tab in at.get("tab")] if hasattr(at, "get") else []
print(f"вкладок отрисовано: {len(вкладки)} (ждём 6)")
if len(вкладки) != 6:
    плохо.append(f"вкладок {len(вкладки)}, а не 6")

# AppTest не видит st.data_editor вовсе — это его ограничение, а не дефект страницы
# (записано в AGENTS.md). Признак того, что оба редактора отрисовались, — их кнопки
# сохранения: «Люди» и «Матрица прав», по одной на каждый.
print(f"таблиц (dataframe): {len(at.get('dataframe'))}")
print(f"кнопок сохранения: {len(at.button)}")
if len(at.button) < 2:
    плохо.append("кнопок сохранения меньше двух: редакторы людей и матрицы должны быть оба")
if len(at.get("dataframe")) < 3:
    плохо.append("таблиц меньше трёх: простой, входы и действия")

for x in плохо:
    print("  ПРОВАЛ:", x)
print("\nитог:", "ок" if not плохо else f"бед {len(плохо)}")
