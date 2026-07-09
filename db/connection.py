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
    cred = w.database.generate_database_credential(
        request_id="kabinet-dashboard",
        instance_names=["projects/kabinet-dashboard/branches/production/endpoints/primary"]
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
