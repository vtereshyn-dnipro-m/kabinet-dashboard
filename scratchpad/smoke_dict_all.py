# -*- coding: utf-8 -*-
"""Все разделы «Справочников» кодом из рабочей копии на ЖИВОЙ базе.

AppTest с подменённым read_sql такие падения не ловит: пустой пул есть только в живой базе.
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
SECTIONS = ["wh", "ch", "ctry", "plat", "mp", "pool", "norm", "alerts", "sku", "peid", "vg", "matrix"]
плохо = 0
for sec in SECTIONS:
    at = AppTest.from_file("/Users/vitter/Documents/Code/kabinet-dashboard/pages/6_Dictionaries.py", default_timeout=300)
    at.session_state["dict_section"] = sec
    at.session_state["dict_section_last"] = sec
    at.run()
    exc = [str(e.value).strip().splitlines()[0][:150] for e in at.exception]
    err = [str(e.value)[:120] for e in at.error]
    нан = [t.value for t in at.markdown if "nan" in str(t.value).lower()][:1]
    нан += [str(d.value.head(3).to_dict()) [:120] for d in at.dataframe
            if "nan" in str(d.value.head(30).to_dict()).lower()][:1]
    if exc: плохо += 1
    print(f"  {'ПАДЕНИЕ' if exc else '  ок   '}  {sec:<7}"
          + (f" | {exc[0]}" if exc else "")
          + (f" | ошибки на экране: {err}" if err else "")
          + (f" | «nan» в тексте: {нан}" if нан else ""))
print(f"\nразделов с падением: {плохо} из {len(SECTIONS)}")
