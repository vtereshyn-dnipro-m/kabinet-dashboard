import streamlit as st
import psycopg2
import pandas as pd


@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["connections"]["lakebase"]["url"])


def run_query(query: str, params: tuple = None) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


def execute(query: str, params: tuple = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
