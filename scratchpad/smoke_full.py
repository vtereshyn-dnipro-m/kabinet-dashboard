# -*- coding: utf-8 -*-
"""Все страницы и все двенадцать разделов «Справочников» на живой базе.

Считаем провалом не только исключение, но и SQL-ошибку, ПОКАЗАННУЮ на экране: страница
ловит её в st.error и «открывается», а данных нет — ровно так прошла мимо ошибка «Прогноза».
"""
import sys, json, psycopg2, warnings, logging, pandas as pd
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import db.connection as dbc
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
dbc.get_connection = lambda: psycopg2.connect(DSN)
import streamlit as st
st.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest
R = "/Users/vitter/Documents/Code/kabinet-dashboard"
SQLISH = ("syntax", "column", "relation", "does not exist", "group by", "psycopg2",
          "operator", "не прочиталось", "undefined")
def прогнать(f, ss=None):
    at = AppTest.from_file(f"{R}/{f}", default_timeout=300)
    for k, v in (ss or {}).items(): at.session_state[k] = v
    at.run()
    exc = [str(e.value).strip().splitlines()[-1][:130] for e in at.exception]
    errs = [str(e.value)[:130] for e in at.error if any(w in str(e.value).lower() for w in SQLISH)]
    return at, exc + errs
беда = 0
for f in ("home.py", "pages/1_Stock.py", "pages/2_Incidents.py", "pages/3_Forecast.py",
          "pages/4_Reorder.py", "pages/5_Money.py", "pages/7_Reviews.py",
          "pages/8_CM_Dashboard.py", "pages/9_Ads.py"):
    _, плохо = прогнать(f)
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
for sec in ["wh", "ch", "ctry", "plat", "mp", "pool", "norm", "alerts", "sku", "peid", "vg", "matrix"]:
    _, плохо = прогнать("pages/6_Dictionaries.py",
                        {"dict_section": sec, "dict_section_last": sec})
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f"Справочники → {sec}"
          + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
print(f"\nс бедой: {беда} из 21")
