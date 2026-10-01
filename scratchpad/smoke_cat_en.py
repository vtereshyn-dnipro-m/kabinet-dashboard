# -*- coding: utf-8 -*-
"""Раздел «Категории» на ЖИВОЙ базе в русском и английском интерфейсе.

Английская ветка там не косметика: запрос связей собирается другими колонками
(`level1_en` вместо `level1`, `name_en` вместо `name`), и опечатка в ней видна только
при lang='en'. Прогон в одном языке такую страницу объявил бы здоровой.
"""
import sys, json, psycopg2, warnings, logging
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
R = "/Users/vitter/Documents/Code/kabinet-dashboard"
sys.path.insert(0, R)
import db.connection as dbc
DSN = json.load(open(R + "/.mcp.json"))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
dbc.get_connection = lambda: psycopg2.connect(DSN)
import streamlit as st
st.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest

SQLISH = ("syntax", "column", "relation", "does not exist", "group by", "psycopg2",
          "operator", "не прочиталось", "undefined")
беда = 0
for lang in ("ru", "uk", "en"):
    путь = R + "/pages/6_Dictionaries.py"
    at = AppTest.from_file(путь, default_timeout=300)
    at.session_state["dict_section"] = "cat"
    at.session_state["dict_section_last"] = "cat"
    at.session_state["lang"] = lang
    at.run()
    плохо = [str(e.value).strip().splitlines()[-1][:160] for e in at.exception]
    плохо += [str(e.value)[:160] for e in at.error
              if any(w in str(e.value).lower() for w in SQLISH)]
    видно = sum(len(getattr(at, n, [])) for n in
                ("title", "markdown", "dataframe", "metric", "caption", "error"))
    if not видно:
        плохо.append("прогон пустой")
    # что реально показалось в подписях — видно, что подписи категорий на нужном языке
    подписи = [c.value for c in at.caption][:4]
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f"lang={lang}" +
          "".join("\n          " + x for x in плохо))
    for p in подписи:
        print("          · " + str(p)[:150])
    беда += bool(плохо)
print("\nпровалов:", беда)
sys.exit(1 if беда else 0)
