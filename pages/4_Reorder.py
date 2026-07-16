# pages/4_Reorder.py — Автозаказ: рекомендации по пополнению
import re
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("ro.title"))
st.caption(t("ro.caption"))

def clean_sku(sku: str) -> str:
    """Чистый базовый SKU: режет amzn.gr., -FBA/-FBM, хвост-хеш, вариант -A/-B."""
    s = str(sku or "").strip()
    s = re.sub(r"^amzn\.gr\.", "", s)
    s = s.replace("-FBA", "").replace("-FBM", "")
    s = re.sub(r"-[A-Za-z0-9]{8,}$", "", s)
    s = re.sub(r"-[A-Za-z]$", "", s)
    return s.strip(" -")

def is_defect_sku(sku: str) -> bool:
    return str(sku or "").lower().startswith("amzn.gr.")

# ---------- автозаказ ----------
@st.cache_data(ttl=300)
def load_reorder(has_status: bool):
    conn = get_connection()
    status_col = "COALESCE(order_status,'new') AS order_status" if has_status \
                 else "'new' AS order_status"
    df = pd.read_sql(f"""
        SELECT sku, product_name, current_stock, daily_velocity,
               days_of_cover, reorder_point, suggested_qty, urgency,
               {status_col}
        FROM kabinet_data.reorder_recommendations
        WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.reorder_recommendations)
    """, conn)
    conn.close()
    return df

def mark_ordered(skus, qtys):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT MAX(calc_date) FROM kabinet_data.reorder_recommendations")
    d = cur.fetchone()[0]
    for sku, qty in zip(skus, qtys):
        cur.execute("""
            UPDATE kabinet_data.reorder_recommendations
            SET order_status='ordered', suggested_qty=%s
            WHERE calc_date=%s AND sku=%s
        """, (int(qty), d, sku))
    conn.commit(); cur.close(); conn.close()

@st.cache_data(ttl=600)
def has_order_status() -> bool:
    """Проверка наличия колонки без DDL (дашборд не владеет таблицей)."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='kabinet_data'
              AND table_name='reorder_recommendations'
              AND column_name='order_status'
        """)
        ok = cur.fetchone() is not None
        cur.close(); conn.close()
        return ok
    except Exception:
        return False

HAS_ORDER_STATUS = has_order_status()
df = load_reorder(HAS_ORDER_STATUS)
# дефекты/возвраты (amzn.gr.) не заказываем — убираем из рекомендаций
df = df[~df["sku"].apply(is_defect_sku)].copy()
if df.empty:
    st.info(t("ro.empty"))
    st.stop()

df["sku_display"] = df["sku"].apply(clean_sku)
URG_ORDER = {"critical": 0, "warning": 1, "ok": 2}
URG_ICON = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}
def urg_label(u): return t(f"ro.urg.{u}")
df["urg_rank"] = df["urgency"].map(URG_ORDER)

active = df[df["order_status"] != "ordered"]
ordered = df[df["order_status"] == "ordered"]

# ---------- KPI ----------
c1, c2, c3, c4 = st.columns(4)
crit = active[active["urgency"] == "critical"]
warn = active[active["urgency"] == "warning"]
c1.metric(t("ro.kpi.critical"), len(crit), help=t("ro.kpi.critical_help"))
c2.metric(t("ro.kpi.warning"), len(warn))
c3.metric(t("ro.kpi.total_qty"),
          int(active.loc[active["urgency"] != "ok", "suggested_qty"].sum()))
c4.metric(t("ro.kpi.sku_controlled"), len(df))

st.divider()

# ═════════════════════════════════════════════════════════════
# ПЕРЕБРОСКА: свои склады (ERP) + между странами FBA
# ═════════════════════════════════════════════════════════════
@st.cache_data(ttl=120)
def load_transfers():
    conn = get_connection()
    tdf = pd.read_sql("""
        SELECT sku, product_name, from_location, to_location, transfer_qty,
               from_stock, from_cover_days, to_stock, to_cover_days,
               COALESCE(from_type,'fba') AS from_type,
               COALESCE(status,'new') AS status
        FROM kabinet_data.transfer_recommendations
        WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.transfer_recommendations)
    """, conn)
    conn.close()
    return tdf

def set_transfer_status(keys, new_status):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT MAX(calc_date) FROM kabinet_data.transfer_recommendations")
    d = cur.fetchone()[0]
    for sku, fl, tl in keys:
        cur.execute("""
            UPDATE kabinet_data.transfer_recommendations
            SET status=%s
            WHERE calc_date=%s AND sku=%s AND from_location=%s AND to_location=%s
        """, (new_status, d, sku, fl, tl))
    conn.commit(); cur.close(); conn.close()

transfers = load_transfers()
active_tr = transfers[transfers["status"] == "new"]

if not active_tr.empty:
    n_erp = int((active_tr["from_type"] == "erp").sum())
    n_fba = int((active_tr["from_type"] == "fba").sum())
    st.markdown(f"#### {t('ro.tr.title')}")
    st.caption(t("ro.tr.caption"))

    # мини-сводка по типу источника
    s1, s2, s3 = st.columns(3)
    s1.metric(t("ro.tr.from_own"), n_erp, help=t("ro.tr.from_own_help"))
    s2.metric(t("ro.tr.from_fba"), n_fba)
    s3.metric(t("ro.tr.total_qty"), int(active_tr["transfer_qty"].sum()))

    tr = active_tr.copy()
    tr["sku_display"] = tr["sku"].apply(clean_sku)
    # фолбэк если пайплайн не подтянул имя
    tr["product_name"] = tr["product_name"].fillna("").astype(str).replace("None", "")
    tr.loc[tr["product_name"] == "", "product_name"] = "— " + tr["sku_display"]
    tr.insert(0, "✓", True)
    # источник с иконкой
    tr["Источник"] = tr.apply(
        lambda r: ("📦 " if r["from_type"] == "erp" else "✈️ ") + str(r["from_location"]),
        axis=1)
    tr["Куда"] = tr["to_location"]
    tr["Хватит(получатель)"] = tr["to_cover_days"].round(0).astype(int)

    tr_sorted = tr.sort_values(["from_type", "to_cover_days"])  # erp сверху
    tr_edited = st.data_editor(
        tr_sorted[["✓", "sku_display", "product_name", "Источник", "Куда",
                   "transfer_qty", "Хватит(получатель)"]],
        use_container_width=True, hide_index=True, height=400,
        column_config={
            "✓": st.column_config.CheckboxColumn(t("ro.tr.col_do"), width="small"),
            "sku_display": st.column_config.TextColumn("SKU", width="small", disabled=True),
            "product_name": st.column_config.TextColumn(t("ro.tr.col_product"), width="large", disabled=True),
            "Источник": st.column_config.TextColumn(t("ro.tr.col_source"), width="medium", disabled=True),
            "Куда": st.column_config.TextColumn(t("ro.tr.col_to"), width="small", disabled=True),
            "transfer_qty": st.column_config.NumberColumn(t("ro.tr.col_qty"), width="small", min_value=0, step=1),
            "Хватит(получатель)": st.column_config.NumberColumn(t("ro.tr.col_cover"), width="small", disabled=True),
        },
        key="transfer_editor",
    )

    chosen_tr = tr_edited[tr_edited["✓"]]
    tc1, tc2 = st.columns([1, 1])
    with tc1:
        if st.button(t("ro.tr.confirm").format(n=len(chosen_tr)),
                     use_container_width=True, disabled=chosen_tr.empty):
            # восстановим ключи (from_location из "Источник" без иконки)
            keys = []
            for _, r in chosen_tr.iterrows():
                src = r["Источник"].replace("📦 ", "").replace("✈️ ", "")
                # найдём оригинальный sku по sku_display
                orig = active_tr[active_tr["sku"].apply(clean_sku) == r["sku_display"]]
                orig = orig[(orig["from_location"] == src) & (orig["to_location"] == r["Куда"])]
                if not orig.empty:
                    keys.append((orig.iloc[0]["sku"], src, r["Куда"]))
            set_transfer_status(keys, "confirmed")
            st.cache_data.clear()
            st.success(t("ro.tr.confirmed").format(n=len(keys)))
            st.rerun()
    with tc2:
        st.download_button(
            t("ro.tr.export").format(n=len(chosen_tr)),
            chosen_tr.to_csv(index=False).encode("utf-8-sig") if not chosen_tr.empty else b"",
            file_name="transfers.csv", mime="text/csv",
            use_container_width=True, disabled=chosen_tr.empty,
        )
    st.divider()

# ═════════════════════════════════════════════════════════════
# ЗАКАЗ У ПОСТАВЩИКА (если переброска не покрывает)
# ═════════════════════════════════════════════════════════════
st.markdown(f"#### {t('ro.order.title')}")

f1, f2 = st.columns([1, 2])
with f1:
    urg_filter = st.multiselect(
        t("ro.filter.urgency"), ["critical", "warning", "ok"],
        default=["critical", "warning"],
        format_func=lambda x: f"{URG_ICON[x]} {urg_label(x)}",
    )
with f2:
    search = st.text_input(t("ro.filter.search"), placeholder=t("ro.filter.search_ph"))

fdf = active[active["urgency"].isin(urg_filter)].copy()
if search:
    m = (fdf["sku_display"].str.contains(search, case=False, na=False)
         | fdf["product_name"].str.contains(search, case=False, na=False))
    fdf = fdf[m]
fdf = fdf.sort_values(["urg_rank", "days_of_cover"])

edit = fdf[["sku_display", "product_name", "current_stock", "daily_velocity",
            "days_of_cover", "suggested_qty", "urgency"]].copy()
edit.insert(0, "✓", edit["urgency"] == "critical")
edit["Срочность"] = edit["urgency"].map(lambda u: f"{URG_ICON[u]} {urg_label(u)}")
edit["daily_velocity"] = edit["daily_velocity"].round(1)
edit["days_of_cover"] = edit["days_of_cover"].round(0)

edited = st.data_editor(
    edit[["✓", "Срочность", "sku_display", "product_name", "current_stock",
          "daily_velocity", "days_of_cover", "suggested_qty"]],
    use_container_width=True, height=440, hide_index=True,
    column_config={
        "✓": st.column_config.CheckboxColumn(t("ro.order.col_do"), width="small"),
        "Срочность": st.column_config.TextColumn(t("ro.order.col_urgency"), width="small", disabled=True),
        "sku_display": st.column_config.TextColumn("SKU", width="small", disabled=True),
        "product_name": st.column_config.TextColumn(t("ro.tr.col_product"), width="large", disabled=True),
        "current_stock": st.column_config.NumberColumn(t("ro.order.col_stock"), width="small", disabled=True),
        "daily_velocity": st.column_config.NumberColumn(t("ro.order.col_velocity"), width="small", disabled=True),
        "days_of_cover": st.column_config.ProgressColumn(
            t("ro.order.col_cover"), width="small", min_value=0, max_value=60, format="%d"),
        "suggested_qty": st.column_config.NumberColumn(
            t("ro.order.col_qty"), width="small", min_value=0, step=1),
    },
    key="reorder_editor",
)

chosen = edited[edited["✓"]]
t1, t2, t3 = st.columns(3)
t1.metric(t("ro.order.chosen"), len(chosen))
t2.metric(t("ro.order.total"), int(chosen["suggested_qty"].sum()))
t3.metric(t("ro.order.avg_velocity"),
          f"{chosen['daily_velocity'].mean():.1f}" if len(chosen) else "—")

a1, a2 = st.columns([1, 1])
with a1:
    if st.button(t("ro.order.form").format(n=len(chosen)),
                 type="primary", use_container_width=True,
                 disabled=chosen.empty or not HAS_ORDER_STATUS):
        skus_orig = [active[active["sku"].apply(clean_sku) == sd].iloc[0]["sku"]
                     for sd in chosen["sku_display"]]
        mark_ordered(skus_orig, chosen["suggested_qty"].tolist())
        st.cache_data.clear()
        st.success(t("ro.order.formed").format(
            n=len(chosen), qty=int(chosen["suggested_qty"].sum())))
        st.rerun()
with a2:
    exp = chosen if not chosen.empty else fdf[fdf["urgency"] != "ok"]
    st.download_button(
        t("ro.order.export").format(n=len(exp)),
        exp.to_csv(index=False).encode("utf-8-sig"),
        file_name="reorder.csv", mime="text/csv",
        use_container_width=True, disabled=exp.empty,
    )

if not ordered.empty:
    st.divider()
    with st.expander(t("ro.ordered.title").format(
            n=len(ordered), qty=int(ordered["suggested_qty"].sum()))):
        od = ordered.copy()
        od["sku_display"] = od["sku"].apply(clean_sku)
        st.dataframe(
            od[["sku_display", "product_name", "current_stock", "suggested_qty"]],
            use_container_width=True, hide_index=True,
            column_config={
                "sku_display": "SKU",
                "product_name": t("ro.tr.col_product"),
                "current_stock": t("ro.order.col_stock"),
                "suggested_qty": t("ro.ordered.col_qty"),
            },
        )

with st.expander(t("ro.how.title")):
    st.markdown(t("ro.how.body"))
