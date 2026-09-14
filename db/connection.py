import streamlit as st
import psycopg2
import pandas as pd
from databricks.sdk import WorkspaceClient


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient(
        host=st.secrets["databricks"]["host"],
        client_id=st.secrets["databricks"]["client_id"],
        client_secret=st.secrets["databricks"]["client_secret"],
    )


def get_connection():
    w = get_workspace_client()
    cred = w.postgres.generate_database_credential(
        endpoint=st.secrets["databricks"]["endpoint_name"]
    )
    return psycopg2.connect(
        host=st.secrets["databricks"]["pg_host"],
        port=5432,
        dbname="databricks_postgres",
        user=st.secrets["databricks"]["client_id"],
        password=cred.token,
        sslmode="require"
    )


def run_query(query: str, params: tuple = None) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


def execute(query: str, params: tuple = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close() 


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
