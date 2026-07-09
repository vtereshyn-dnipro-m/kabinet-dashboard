from databricks.sdk import WorkspaceClient
import psycopg2
import streamlit as st

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
        instance_names=["kabinet-dashboard"]
    )
    return psycopg2.connect(
        host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
        port=5432,
        dbname="databricks_postgres",
        user=st.secrets["databricks"]["client_id"],
        password=cred.token,
        sslmode="require"
    )
