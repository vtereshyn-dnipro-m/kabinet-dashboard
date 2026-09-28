# -*- coding: utf-8 -*-
"""Страницы, читающие пулы, на живой базе: распущенный Spain не должен их ронять."""
import sys, json, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
sys.path.insert(0, "/Users/vitter/Documents/Code/kabinet-dashboard")
import db.connection as dbc
DSN = json.load(open("/Users/vitter/Documents/Code/kabinet-dashboard/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
dbc.get_connection = lambda: psycopg2.connect(DSN)
import streamlit as st
st.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest
for f in ("home.py", "pages/3_Forecast.py", "pages/5_Money.py", "pages/1_Stock.py"):
    at = AppTest.from_file(f"/Users/vitter/Documents/Code/kabinet-dashboard/{f}", default_timeout=300)
    at.run()
    exc = [str(e.value).strip().splitlines()[-1][:160] for e in at.exception]
    txt = " ".join(str(m.value) for m in at.markdown)
    print(f"  {'ПАДЕНИЕ' if exc else '  ок   '}  {f:<22}"
          + (f" | {exc[0]}" if exc else "")
          + (" | «nan» в тексте!" if "nan" in txt.lower() else ""))
