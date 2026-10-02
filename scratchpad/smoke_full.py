# -*- coding: utf-8 -*-
"""Все страницы и все двенадцать разделов «Справочников» на живой базе.

Провалом считается три разных вещи, и каждая добавлена после того, как прошла мимо:

1. исключение в прогоне — было с самого начала;
2. SQL-ошибка, ПОКАЗАННАЯ на экране: страница ловит её в st.error и «открывается», а
   данных нет — так прошла мимо ошибка «Прогноза» (28.09.2026);
3. страница, которая НЕ КОМПИЛИРУЕТСЯ. AppTest на такой не даёт ни исключения, ни
   ошибки на экране: Streamlit печатает SyntaxError в свой лог и возвращает пустой
   прогон, а харнесс писал «ок» — ровно там, где страница мертва совсем. Так PR #195
   уехал в прод с повторным help= в «Остатках» (30.09.2026). Поэтому компиляцию
   проверяем САМИ, до запуска, и пустой прогон тоже считаем провалом.
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
    путь = f"{R}/{f}"
    # компиляция — до запуска: см. пункт 3 в описании модуля
    try:
        compile(open(путь, encoding="utf-8").read(), путь, "exec")
    except SyntaxError as e:
        return None, [f"не компилируется: {e.msg} (строка {e.lineno})"]
    at = AppTest.from_file(путь, default_timeout=300)
    for k, v in (ss or {}).items(): at.session_state[k] = v
    at.run()
    exc = [str(e.value).strip().splitlines()[-1][:130] for e in at.exception]
    errs = [str(e.value)[:130] for e in at.error if any(w in str(e.value).lower() for w in SQLISH)]
    # прогон, не нарисовавший ни одного элемента, — это не «пустая страница», а
    # скрипт, который не доехал: у любой нашей страницы есть хотя бы заголовок
    # Список полный намеренно: в первой версии не было ни title, ни error, и страница
    # «Доступ», честно отказавшая невошедшему заголовком и красной плашкой, объявлялась
    # пустым прогоном. Проверка, которая ругается на правильное поведение, хуже
    # отсутствующей — её начинают игнорировать.
    видно = sum(len(getattr(at, имя, [])) for имя in
                ("title", "markdown", "dataframe", "metric", "header", "subheader",
                 "caption", "table", "error", "warning", "info", "success"))
    if not видно:
        errs.append("прогон пустой: ни одного элемента на экране")
    return at, exc + errs
беда = 0

# ── общий экран «Доступ»: копия обязана совпадать с источником ────────────────
# Стоит ПЕРВЫМ и считается провалом наравне со сломанной страницей: «Доступ» в двух
# приложениях — один файл, и расхождение означает две версии одной админки над общими
# таблицами. Предупреждением тут не отделаться — его прочитают после деплоя.
sys.path.insert(0, f"{R}/scratchpad")
import sync_access_screen as _синк
_копия_плохо = _синк.проверить()
print(("  ПРОВАЛ " if _копия_плохо else "    ок  ") + "выкладка access_screen.py"
      + ("".join("\n          " + x for x in _копия_плохо)))
беда += bool(_копия_плохо)

for f in ("home.py", "pages/1_Stock.py", "pages/2_Incidents.py", "pages/3_Forecast.py",
          "pages/4_Reorder.py", "pages/5_Money.py", "pages/7_Reviews.py",
          "pages/8_CM_Dashboard.py", "pages/9_Ads.py", "pages/10_Access.py"):
    _, плохо = прогнать(f)
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
for sec in ["wh", "ch", "ctry", "plat", "mp", "pool", "norm", "alerts", "sku", "cat", "peid", "vg", "matrix"]:
    _, плохо = прогнать("pages/6_Dictionaries.py",
                        {"dict_section": sec, "dict_section_last": sec})
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f"Справочники → {sec}"
          + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
print(f"\nс бедой: {беда} из 24")
