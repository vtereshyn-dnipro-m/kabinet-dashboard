"""Подключение к Lakebase.

Одно соединение стоит дорого: `generate_database_credential` — это REST-вызов в Databricks (~1 с),
плюс TLS-рукопожатие с Postgres в us-east-1 (~0,5–1 с). Раньше так открывалось соединение на КАЖДЫЙ
запрос: «Справочники» на первом показе делали 44 соединения — 40 секунд из 56, сами запросы — 16
(замер 21.09.2026). Поэтому здесь пул: токен кешируется (живёт час, держим 50 минут), соединения
переиспользуются, `close()` у выданного соединения возвращает его в пул, а не рвёт. Интерфейс для
страниц прежний: `conn = get_connection(); … ; conn.close()`.
"""
import time
import streamlit as st
import psycopg2
import psycopg2.extensions
import psycopg2.pool
import pandas as pd
from databricks.sdk import WorkspaceClient

_ENDPOINT_KEY = "endpoint_name"
_POOL_MAX = 8
_PROBE_AFTER_IDLE_S = 60      # соединение, пролежавшее дольше, проверяем «SELECT 1» перед выдачей


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient(
        host=st.secrets["databricks"]["host"],
        client_id=st.secrets["databricks"]["client_id"],
        client_secret=st.secrets["databricks"]["client_secret"],
    )


_TOKEN_TTL_S = 50 * 60


@st.cache_resource(show_spinner=False)
def _token_box() -> dict:
    # не cache_data: страницы после сохранения зовут st.cache_data.clear(), и токен вылетал бы вместе
    # с данными — лишний вызов в Databricks на каждое сохранение
    return {"token": None, "at": 0.0}


def _pg_token(force: bool = False) -> str:
    """Временный пароль Lakebase. Действует час; уже открытые соединения после его истечения
    живут дальше (Postgres проверяет пароль только при подключении), новым нужен свежий."""
    box = _token_box()
    if force or box["token"] is None or time.time() - box["at"] > _TOKEN_TTL_S:
        w = get_workspace_client()
        box["token"] = w.postgres.generate_database_credential(endpoint=st.secrets["databricks"][_ENDPOINT_KEY]).token
        box["at"] = time.time()
    return box["token"]


class _Pool(psycopg2.pool.ThreadedConnectionPool):
    def __init__(self, keep_idle: int, maxconn: int, **kwargs):
        # minconn у psycopg2 — это и «открыть при старте», и «сколько простаивающих держать»:
        # putconn закрывает всё сверх minconn. Открывать заранее не хотим (8 × 1 с на каждом старте),
        # держать — хотим, поэтому создаём с нулём и поднимаем порог после.
        super().__init__(0, maxconn, **kwargs)
        self.minconn = keep_idle
        self.last_used = {}          # id(conn) → когда вернули в пул

    def _connect(self, key=None):
        self._kwargs["password"] = _pg_token()   # каждое новое соединение — с актуальным токеном
        return super()._connect(key)


@st.cache_resource(show_spinner=False)
def _pool() -> _Pool:
    return _Pool(
        _POOL_MAX, _POOL_MAX,
        host=st.secrets["databricks"]["pg_host"],
        port=5432,
        dbname="databricks_postgres",
        user=st.secrets["databricks"]["client_id"],
        password="",
        sslmode="require",
    )


class PooledConnection:
    """Соединение из пула с интерфейсом psycopg2-соединения. `close()` возвращает в пул."""

    def __init__(self, pool, conn):
        self._pool, self._conn = pool, conn

    def cursor(self, *a, **k):
        return self._conn.cursor(*a, **k)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        conn, self._conn = self._conn, None
        if conn is None or self._pool is None:
            if conn is not None:
                conn.close()
            return
        try:
            if conn.closed:
                self._pool.putconn(conn, close=True)
            else:
                if conn.status != psycopg2.extensions.STATUS_READY:
                    conn.rollback()        # незавершённая транзакция не должна достаться следующему запросу
                self._pool.last_used[id(conn)] = time.time()
                self._pool.putconn(conn)
        except Exception:
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass

    # `with conn:` у psycopg2 — commit/rollback без закрытия; повторяем
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()

    def __getattr__(self, name):
        if name.startswith("_"):           # иначе обращение к ещё не заданному _conn зацикливается
            raise AttributeError(name)
        return getattr(self._conn, name)

    def __del__(self):
        try:
            self.close()   # забытое соединение возвращается в пул, а не теряется до конца процесса
        except Exception:
            pass


def _direct_connection():
    """Как было до пула — запасной путь, если пул исчерпан или недоступен."""
    return psycopg2.connect(
        host=st.secrets["databricks"]["pg_host"],
        port=5432,
        dbname="databricks_postgres",
        user=st.secrets["databricks"]["client_id"],
        password=_pg_token(),
        sslmode="require",
    )


def get_connection():
    try:
        pool = _pool()
    except Exception:
        return PooledConnection(None, _direct_connection())
    for attempt in range(3):
        try:
            conn = pool.getconn()
        except psycopg2.pool.PoolError:                  # все 8 заняты — не ждём, идём напрямую
            return PooledConnection(None, _direct_connection())
        except psycopg2.OperationalError as e:
            # протухший токен (кеш пережил срок) — сбросить и попробовать ещё раз
            if attempt == 0 and "password" in str(e).lower():
                _pg_token(force=True)
                continue
            raise
        # соединение из пула могло умереть, пока лежало (сервер закрыл простой). Проверять каждый раз —
        # лишний круг до базы на каждый запрос; проверяем только то, что простояло дольше минуты
        try:
            if conn.closed:
                raise psycopg2.InterfaceError("closed")
            if time.time() - pool.last_used.get(id(conn), 0) > _PROBE_AFTER_IDLE_S:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.rollback()
            return PooledConnection(pool, conn)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
    return PooledConnection(None, _direct_connection())


def run_query(query: str, params: tuple = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def execute(query: str, params: tuple = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        cur.close()
    finally:
        conn.close()


@st.cache_data(ttl=60)
def data_version(table: str, col: str) -> str:
    """Отметка последней записи в таблицу — ключ согласованности кешей.

    Страницы кешируют одни и те же запросы независимо, с разными TTL и в
    разные моменты. Загрузчик переписал последние семь дней в 08:50 —
    Обзор перечитал в 08:52, Деньги держат снимок с 08:45 ещё десять минут,
    и «Продажи по заказам» на двух страницах расходятся на 11 €. Обе правы,
    просто в разное время.

    Значение отсюда передаётся параметром в кеширующие загрузчики: оно
    входит в ключ, и когда загрузчик пишет, все страницы обновляются вместе,
    не дожидаясь чужого TTL. Само оно живёт минуту — это цена одного
    MAX() по индексу.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT MAX({col})::text FROM kabinet_data.{table}")
        row = cur.fetchone()
        cur.close()
        return (row[0] if row else "") or ""
    except Exception:
        return ""
    finally:
        conn.close()
