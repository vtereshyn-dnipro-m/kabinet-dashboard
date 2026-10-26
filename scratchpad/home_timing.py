"""Замер «Обзора» (home.py) с пустым и тёплым кешем — T-32 (27.10.2026). Только чтение: сессия readonly.

Запуск из корня рабочей копии (код — из ТОЙ копии, где лежит этот файл, как у smoke_full.py):
    uv run --quiet --with-requirements requirements.txt python scratchpad/home_timing.py
Выводит: общее время рендера под admin, число запросов к Lakebase, время в базе и двенадцать самых тяжёлых запросов.
Время pd.read_sql учитывается один раз (без вложенного cursor.execute).
"""
import collections
import json
import os
import subprocess
import sys
import time
import warnings
import logging

import pandas as pd
import psycopg2

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)


def _dsn() -> str:
    if os.environ.get("LAKEBASE_DSN"):
        return os.environ["LAKEBASE_DSN"]
    common = subprocess.run(["git", "-C", R, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True).stdout.strip()
    for root in (R, os.path.dirname(common) if common else ""):
        f = os.path.join(root, ".mcp.json") if root else ""
        if f and os.path.exists(f):
            return json.load(open(f))["mcpServers"]["lakebase-kabinet"]["env"]["LAKEBASE_DSN"]
    raise SystemExit("нет подключения: задайте LAKEBASE_DSN или положите .mcp.json в основной checkout")


DSN = _dsn()
T = []                     # (секунды, текст запроса)
_in_read_sql = [False]


class Cur(psycopg2.extensions.cursor):
    def execute(self, q, vars=None):
        t0 = time.time()
        try:
            return super().execute(q, vars)
        finally:
            if not _in_read_sql[0]:
                T.append((time.time() - t0, " ".join(str(q).split())[:150]))


def conn():
    c = psycopg2.connect(DSN, cursor_factory=Cur)
    c.set_session(readonly=True)
    return c


import db.connection as dbc  # noqa: E402
dbc.get_connection = conn
_orig = pd.read_sql


def timed_read_sql(sql, con, *a, **k):
    t0 = time.time()
    _in_read_sql[0] = True
    try:
        return _orig(sql, con, *a, **k)
    finally:
        _in_read_sql[0] = False
        T.append((time.time() - t0, " ".join(str(sql).split())[:150]))


pd.read_sql = timed_read_sql
from streamlit.testing.v1 import AppTest  # noqa: E402

SRC = f'''
import sys, os
sys.path.insert(0, {R!r}); os.chdir({R!r})
import streamlit as st
st.page_link = lambda *a, **k: None
import auth
auth.current = lambda: auth.User(email="t@x", role="admin", logged_in=True)
exec(compile(open("home.py", encoding="utf-8").read(), "home.py", "exec"))
'''
for run in ("холодный", "тёплый"):
    T.clear()
    at = AppTest.from_string(SRC, default_timeout=600)
    t0 = time.time()
    at.run()
    total = time.time() - t0
    print(f"=== {run}: всего {total:.1f} с, исключений {len(at.exception)}, запросов {len(T)}, "
          f"в базе {sum(x[0] for x in T):.1f} с")
    agg = collections.defaultdict(lambda: [0, 0.0])
    for sec, q in T:
        agg[q][0] += 1
        agg[q][1] += sec
    for q, (n, s) in sorted(agg.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"  {s:6.2f} с  ×{n}  {q}")
