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
import os, subprocess, sys, json, psycopg2, warnings, logging, pandas as pd
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
# Код — из ТОЙ рабочей копии, где лежит этот файл (ветка в worktree, а не main). До 18.10.2026 путь был зашит на
# основной checkout, и прогон из worktree с веткой молча проверял код main: «0 провалов» значило «main исправен».
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)


def _dsn() -> str:
    """Подключение к Lakebase: LAKEBASE_DSN, иначе .mcp.json этой копии, иначе основного checkout (в git его нет,
    а в worktree его не копируют)."""
    if os.environ.get("LAKEBASE_DSN"):
        return os.environ["LAKEBASE_DSN"]
    common = subprocess.run(["git", "-C", R, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    for root in (R, os.path.dirname(common) if common else ""):
        f = os.path.join(root, ".mcp.json") if root else ""
        if f and os.path.exists(f):
            return json.load(open(f))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
    raise SystemExit("нет подключения: задайте LAKEBASE_DSN или положите .mcp.json в основной checkout")


import db.connection as dbc
DSN = _dsn()
dbc.get_connection = lambda: psycopg2.connect(DSN)
import streamlit as st
st.page_link = lambda *a, **k: None
from streamlit.testing.v1 import AppTest
_ветка = subprocess.run(['git', '-C', R, 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
_коммит = subprocess.run(['git', '-C', R, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
# при отделённой голове ветки нет — тогда хотя бы номер коммита, чтобы было видно, ЧТО проверено
print(f"проверяется код: {R} (ветка {_ветка or '—'}, коммит {_коммит or '—'})")
SQLISH = ("syntax", "column", "relation", "does not exist", "group by", "psycopg2",
          "operator", "не прочиталось", "undefined")
# Коды типов инцидентов на экране — признак того, что подпись взята мимо i18n.incident_type_label (своя копия
# словаря, color = код в plotly). Так «Площадки → Здоровье · Amazon» показывали listing_pair_blocked и ещё девять
# кодов (12.10.2026). Ищем во всём, что видит человек: тексты, метрики, таблицы, варианты фильтров, диаграммы.
КОДЫ = []


def видимый_текст(at):
    out = []
    for имя in ("title", "header", "subheader", "markdown", "caption", "info", "warning", "error", "success", "text"):
        for e in getattr(at, имя, []):
            out.append(str(getattr(e, "value", "")))
    for e in at.metric:
        out += [str(e.label), str(e.value)]
    for e in at.dataframe:
        try:
            v = e.value
            out += [str(c) for c in v.columns] + [v.to_string()]
        except Exception:
            pass
    for e in list(at.selectbox) + list(at.multiselect) + list(at.radio):
        try:
            out += [str(o) for o in e.options]
        except Exception:
            pass
    for e in at.get("plotly_chart"):
        try:
            out.append(e.proto.spec)
        except Exception:
            pass
    return "\n".join(x for x in out if x)


def сырые_коды(at):
    import re as _re
    txt = видимый_текст(at)
    return sorted({k for k in КОДЫ if _re.search(rf"(?<![A-Za-z0-9_]){_re.escape(k)}(?![A-Za-z0-9_])", txt)})


def прогнать(f, ss=None, коды_можно=False):
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
    if not коды_можно:
        _к = сырые_коды(at)
        if _к:
            errs.append("на экране коды типов инцидентов вместо названий: " + ", ".join(_к))
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

# ── у каждого типа инцидента есть подпись на трёх языках ─────────────────────
# Без строки в словаре подпись берётся из справочника incident_types — она русская, и в EN/UK
# на «Обзоре» висела «Дефицит наступит раньше поставки» (12.10.2026, ещё одиннадцать типов так же).
import i18n as _i18n
_типы = pd.read_sql("""SELECT incident_type FROM kabinet_data.incident_types
                        UNION SELECT DISTINCT incident_type FROM kabinet_data.incidents""", psycopg2.connect(DSN))["incident_type"]
КОДЫ[:] = sorted(set(_типы.dropna()))
_без_перевода = sorted(c for c in _типы if not all(_i18n.TRANSLATIONS.get(f"inc.type.{c}", {}).get(l) for l in ("ru", "uk", "en")))
print(("  ПРОВАЛ " if _без_перевода else "    ок  ") + "переводы типов инцидентов"
      + (f"\n          нет перевода: {', '.join(_без_перевода)}" if _без_перевода else ""))
беда += bool(_без_перевода)

for f in ("home.py", "pages/1_Stock.py", "pages/2_Incidents.py", "pages/3_Forecast.py",
          "pages/4_Reorder.py", "pages/5_Money.py", "pages/7_Reviews.py",
          "pages/8_CM_Dashboard.py", "pages/9_Ads.py", "pages/10_Access.py", "pages/11_TikTok.py"):
    _, плохо = прогнать(f)
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
for sec in ["wh", "ch", "ctry", "plat", "mp", "pool", "norm", "alerts", "sched", "api", "sku", "cat", "peid", "vg", "matrix"]:
    # в справочнике алертов код типа — это ключ записи (колонка «Код типа»), ему там место
    _, плохо = прогнать("pages/6_Dictionaries.py",
                        {"dict_section": sec, "dict_section_last": sec}, коды_можно=(sec == "alerts"))
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f"Справочники → {sec}"
          + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
# те же страницы с инцидентами — на английском: подпись типа не должна откатываться к коду и в другом языке
for f in ("home.py", "pages/2_Incidents.py", "pages/8_CM_Dashboard.py"):
    _, плохо = прогнать(f, {"lang": "en"})
    print(("  ПРОВАЛ " if плохо else "    ок  ") + f + " (EN)" + ("".join("\n          " + x for x in плохо)))
    беда += bool(плохо)
print(f"\nс бедой: {беда} из 29")
