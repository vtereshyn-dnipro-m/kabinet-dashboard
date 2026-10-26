"""Замер «Обзора» (home.py) с пустым и тёплым кешем — T-32 (27.10.2026). Только чтение: сессия readonly.

Запуск из корня рабочей копии (код — из ТОЙ копии, где лежит этот файл, как у smoke_full.py):
    uv run --quiet --with-requirements requirements.txt python scratchpad/home_timing.py
Выводит: общее время рендера под admin, число запросов к Lakebase, время в базе, сколько новых подключений открыто и
сколько времени на это ушло, и двенадцать самых тяжёлых запросов. Время pd.read_sql учитывается один раз (без
вложенного cursor.execute). Подключения — как в приложении: пул до 8 (db/connection.py, с #128), close() возвращает
подключение в пул; без пула (каждый запрос — новое подключение) первый замер 27.10 завысил время вдвое (34 с против ~16 с).
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


CONNECTS = []             # секунды на каждое новое подключение


class Pool:
    """Как пул приложения: до 8 подключений, выданное и закрытое возвращается и выдаётся снова."""

    def __init__(self, size=8):
        self.free, self.size, self.open = [], size, 0

    def get(self):
        if self.free:
            return self.free.pop()
        t0 = time.time()
        c = psycopg2.connect(DSN, cursor_factory=Cur)
        c.set_session(readonly=True)
        CONNECTS.append(time.time() - t0)
        self.open += 1
        return c

    def put(self, c):
        c.rollback()
        self.free.append(c)


class Pooled:
    def __init__(self, pool):
        self._pool, self._conn = pool, pool.get()

    def close(self):
        if self._conn is not None:
            self._pool.put(self._conn)
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._conn, name)


POOL = Pool()
import db.connection as dbc  # noqa: E402
dbc.get_connection = lambda: Pooled(POOL)
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
    CONNECTS.clear()
    at = AppTest.from_string(SRC, default_timeout=600)
    t0 = time.time()
    at.run()
    total = time.time() - t0
    print(f"=== {run}: всего {total:.1f} с, исключений {len(at.exception)}, запросов {len(T)}, "
          f"в базе {sum(x[0] for x in T):.1f} с, новых подключений {len(CONNECTS)} ({sum(CONNECTS):.1f} с)")
    agg = collections.defaultdict(lambda: [0, 0.0])
    for sec, q in T:
        agg[q][0] += 1
        agg[q][1] += sec
    for q, (n, s) in sorted(agg.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"  {s:6.2f} с  ×{n}  {q}")
