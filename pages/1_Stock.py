# pages/1_Stock.py — Остатки: аналитический дашборд
import re
import pandas as pd
import numpy as np
import streamlit as st
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
from db.connection import get_connection
from i18n import init_lang, t
import catalog
import period as period_mod

init_lang()

# ---------- стили ----------
st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-size: 1.7rem; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; }
h1 { margin-bottom: 0.1rem; font-size: 2rem; }
[data-testid="stCaptionContainer"] { margin-top: -0.3rem; }
hr { margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

st.title(t("stock.title"))
st.caption(t("stock.caption"))


# ---------- данные ----------
@st.cache_data(ttl=600)
def load_stock() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT snapshot_date, sku, asin, product_name,
               warehouse_name, location, availability_status, quality_status,
               quantity, source, sync_status
        FROM kabinet_data.stock_local
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def table_exists(name: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'kabinet_data' AND table_name = %s
        """, (name,))
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


@st.cache_data(ttl=600)
def coverage_diag() -> dict:
    """Почему свод покрытия пуст.

    Три разных случая — таблицы нет в Lakebase, строк нет, запрос упал —
    раньше сводились к одному пустому DataFrame, и страница показывала
    одинаковую пустоту. Отличить «расчёт не доехал» от «запрос сломался»
    было нельзя ни с экрана, ни из логов: `except Exception` глотал текст
    ошибки целиком.

    Спрашиваем у базы напрямую: есть ли таблица, сколько в ней строк и
    какая дата расчёта последняя. Этого хватает, чтобы человек за минуту
    понял, на чьей стороне проблема."""
    out = {"table": False, "rows": None, "last_calc": None, "error": None}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'kabinet_data'
              AND table_name = 'coverage_summary'
        """)
        out["table"] = cur.fetchone() is not None
        if out["table"]:
            cur.execute("SELECT COUNT(*), MAX(calc_date) "
                        "FROM kabinet_data.coverage_summary")
            row = cur.fetchone()
            out["rows"] = int(row[0] or 0)
            out["last_calc"] = row[1]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()
    return out


INV_INBOUND = ["inb_working", "inb_shipped", "inb_receiving"]
INV_NUM = ["available", "reserved", "unsellable"] + INV_INBOUND
# Переброска между центрами: в журнале это отдельный тип события, а не
# совпадение даты и товара. Остальные типы — Shipments, Adjustments,
# VendorReturns, CustomerReturns, Receipts — перемещениями не являются
EVT_TRANSFER = "WhseTransfers"


@st.cache_data(ttl=600)
def load_fba_centers() -> pd.DataFrame:
    """Справочник центров FBA: код, город, страна, координаты."""
    if not table_exists("fba_fulfillment_centers"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT UPPER(TRIM(fc_code))     AS fc_code,
                   TRIM(city)               AS city,
                   TRIM(country_code)       AS country_code,
                   TRIM(country_name)       AS country_name,
                   fc_type,
                   latitude                 AS lat,
                   longitude                AS lon
            FROM kabinet_data.fba_fulfillment_centers
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    # В фильтре показываем название страны, а не код: «Испания» ищется
    # глазами, «ES» — нет. Код остаётся запасным именем для центров,
    # у которых название в справочнике не заполнено
    df["country"] = (df["country_name"].fillna("").astype(str).str.strip()
                     .replace("", pd.NA).fillna(df["country_code"]))
    return df.dropna(subset=["lat", "lon"]).drop_duplicates("fc_code")


@st.cache_data(ttl=600)
def load_fba_ledger(days: int, d_from: str = "",
                    d_to: str = "") -> pd.DataFrame:
    """Движения по центрам за период.

    Разрез по ЦЕНТРАМ, а не по маркетплейсам: при Pan-EU один и тот же
    запас виден в нескольких странах, и сумма по рынкам физический склад
    не описывает. Ledger отвечает на вопрос «где лежит», рынки — «где
    продаётся»."""
    if not table_exists("fba_ledger_detail"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            SELECT event_date                       AS day,
                   UPPER(TRIM(fulfillment_center))  AS fc_code,
                   asin, msku, title, event_type    AS event,
                   quantity                         AS qty
            FROM kabinet_data.fba_ledger_detail
            WHERE {"event_date BETWEEN DATE '%s' AND DATE '%s'" % (d_from, d_to)
                   if d_from else
                   "event_date >= CURRENT_DATE - INTERVAL '%d days'" % days}
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df
    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    return df.dropna(subset=["day"])


@st.cache_data(ttl=600)
def load_fba_center_stock() -> pd.DataFrame:
    """Остаток по каждому центру — сумма движений за ВСЮ историю ledger.

    Окно периода сюда не применяется: за семь дней получилось бы не
    «сколько лежит», а «на сколько изменилось». Агрегируем на стороне
    базы — три десятка строк вместо всего журнала."""
    if not table_exists("fba_ledger_detail"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT UPPER(TRIM(fulfillment_center)) AS fc_code,
                   SUM(quantity)                   AS qty
            FROM kabinet_data.fba_ledger_detail
            GROUP BY 1
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    return df[df["qty"] > 0]


@st.cache_data(ttl=600)
def load_fba_inventory() -> pd.DataFrame:
    """Остатки FBA: одна строка на товар в пуле.

    Два места, где число легко удвоить. Первое — snapshot_date: таблица
    хранит снимки за разные дни, и без отбора последнего складываются
    вчера и сегодня. Второе — source_marketplace: при Pan-EU один и тот же
    физический запас приходит строкой на каждый рынок, где товар виден.
    Строки зеркальные, поэтому по рынкам берём максимум, а не сумму —
    складывать их значит считать один поддон столько раз, на скольких
    витринах он выставлен.

    Британия после Brexit — отдельный пул: её запас в европейский не
    переливается, поэтому pool остаётся в разрезе."""
    if not table_exists("fba_inventory_deduped"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT pool, asin, sku, MAX(product_name) AS product_name,
                   MAX(afn_fulfillable_qty)        AS available,
                   MAX(afn_reserved_qty)           AS reserved,
                   MAX(afn_unsellable_qty)         AS unsellable,
                   MAX(afn_inbound_working_qty)    AS inb_working,
                   MAX(afn_inbound_shipped_qty)    AS inb_shipped,
                   MAX(afn_inbound_receiving_qty)  AS inb_receiving
            FROM kabinet_data.fba_inventory_deduped
            WHERE snapshot_date = (SELECT MAX(snapshot_date)
                                   FROM kabinet_data.fba_inventory_deduped)
            GROUP BY pool, asin, sku
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df
    for c in INV_NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["asin"] = df["asin"].astype(str).str.strip()
    return df


@st.cache_data(ttl=600)
def load_sales_by_asin(days: int = 30) -> pd.DataFrame:
    """Продажи в штуках по ASIN за период и рынки, где они шли.

    economics_summary хранит norm_sku, а не ASIN, поэтому связываем через
    sku_asin_map по числовой части артикула — тем же способом, что и
    «Деньги». Один ASIN общий на всю Европу, поэтому по рынкам суммируем:
    здесь нас интересует спрос на товар, а не по какой стране он прошёл.

    Рынки при этом сохраняем списком по убыванию продаж: он отвечает на
    вопрос «где именно кончилось» и даёт домен для ссылки на карточку."""
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            WITH m AS (
                SELECT s.asin           AS asin,
                       e.marketplace    AS mp,
                       SUM(e.units_ordered) AS units
                FROM kabinet_data.economics_summary e
                JOIN (
                    SELECT sku_group, MAX(asin) AS asin
                    FROM kabinet_data.sku_asin_map
                    WHERE asin IS NOT NULL
                    GROUP BY sku_group
                ) s ON s.sku_group = SUBSTRING(e.norm_sku FROM '([0-9]{{5,}})')
                WHERE e.sales_date >= CURRENT_DATE - INTERVAL '{days} days'
                  AND e.units_ordered > 0
                GROUP BY 1, 2
            )
            SELECT asin,
                   SUM(units)                                AS units,
                   STRING_AGG(mp, ', ' ORDER BY units DESC)  AS markets
            FROM m GROUP BY asin
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_zero_since() -> pd.DataFrame:
    """С какого дня по товару нет запаса.

    Прямого поля «сколько дней ноль» нигде нет: остатки — снимок на
    сейчас. Восстанавливаем по журналу: складываем движения по ASIN
    нарастающим итогом и ищем последний день, когда баланс был больше
    нуля. Агрегируем по дням на стороне базы — построчный журнал сюда
    тащить незачем."""
    if not table_exists("fba_ledger_detail"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT asin, event_date::date AS day, SUM(quantity) AS qty
            FROM kabinet_data.fba_ledger_detail
            GROUP BY 1, 2 ORDER BY 1, 2
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if df.empty:
        return df
    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
    df = df.dropna(subset=["day"]).sort_values(["asin", "day"])
    df["balance"] = df.groupby("asin")["qty"].cumsum()
    pos = df[df["balance"] > 0]
    if pos.empty:
        return pd.DataFrame(columns=["asin", "zero_since"])
    return (pos.groupby("asin", as_index=False)["day"].max()
               .rename(columns={"day": "zero_since"}))


@st.cache_data(ttl=600)
def load_coverage() -> pd.DataFrame:
    """Свод покрытия на последнюю дату расчёта.

    Фильтр по дате самореферентный: сравниваем с MAX(calc_date) из этой же
    таблицы, а не с CURRENT_DATE. Часовой пояс на него не влияет — какой бы
    ни была метка, максимум берётся из тех же строк. Пустой результат здесь
    означает, что строк нет вовсе или запрос упал, а не что дата разошлась."""
    if not table_exists("coverage_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT s.*, l.product_name AS fallback_name
            FROM kabinet_data.coverage_summary s
            LEFT JOIN (
                SELECT SUBSTRING(sku FROM '([0-9]{5,})') AS base_sku,
                       MAX(product_name) AS product_name
                FROM kabinet_data.stock_local
                WHERE product_name IS NOT NULL
                GROUP BY 1
            ) l ON l.base_sku = s.sku
            WHERE s.calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_summary)
        """, conn)
        # имя приходит из расчёта, но у части позиций его нет —
        # подстраховываемся остатками, иначе в списке выбора будут прочерки
        if "product_name" not in df.columns:
            df["product_name"] = None
        df["product_name"] = (df["product_name"]
                              .fillna(df.get("fallback_name"))
                              .fillna("—").replace({"None": "—", "": "—"}))
        return df.drop(columns=["fallback_name"], errors="ignore")
    except Exception as e:
        # текст ошибки нужен на экране: без него «пусто» и «сломалось»
        # выглядят одинаково, и разбор начинается с чтения кода
        st.session_state["_cov_error"] = f"{type(e).__name__}: {e}"
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_projection(sku: str, marketplace: str) -> pd.DataFrame:
    """Понедельная проекция по одному товару."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT week_start, week_num, stock_begin, incoming,
                   forecast, stock_end, unmet_demand, is_covered
            FROM kabinet_data.coverage_projection
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_projection)
              AND sku = %(sku)s AND marketplace = %(mp)s
            ORDER BY week_num
        """, conn, params={"sku": sku, "mp": marketplace})
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def get_category_map():
    return {
        "amoladora": t("stock.cat.amoladora"),
        "martillo": t("stock.cat.martillo"),
        "taladro": t("stock.cat.taladro"),
        "destornillador": t("stock.cat.destornillador"),
        "motosierra": t("stock.cat.motosierra"),
        "sierra": t("stock.cat.sierra"),
        "soldador": t("stock.cat.soldador"),
        "compresor": t("stock.cat.compresor"),
        "bateria": t("stock.cat.bateria"),
        "cargador": t("stock.cat.bateria"),
    }


def detect_category(name: str) -> str:
    n = (name or "").lower()
    for key, cat in get_category_map().items():
        if key in n:
            return cat
    return t("stock.other")


# ---------- очистка SKU и фильтр дефектов/возвратов ----------
def clean_sku(sku: str) -> str:
    """Убирает -FBA суффикс для отображения."""
    return str(sku or "").replace("-FBA", "").strip()


def is_defect_sku(sku: str) -> bool:
    """Дефектные/возвратные SKU (Amazon removal/grade): amzn.gr.16873000-1-eyYX..."""
    return str(sku or "").lower().startswith("amzn.gr.")


df = load_stock()

if df.empty:
    st.warning(t("stock.no_data_warning"))
    st.stop()

df["category"] = df["product_name"].apply(detect_category)
df["power_w"] = df["product_name"].str.extract(r"(\d{3,4})\s*W", flags=re.I)[0].astype(float)

if "location" not in df.columns:
    df["location"] = None
df["location"] = df["location"].fillna("—")

# очищенный SKU для отображения + отделение дефектов
df["sku_display"] = df["sku"].apply(clean_sku)
df["is_defect"] = df["sku"].apply(is_defect_sku)

defects_df = df[df["is_defect"]].copy()      # дефекты/возвраты — отдельно
df = df[~df["is_defect"]].copy()             # основной сток — без дефектов

# ---------- физический остаток vs квота канала ----------
# availability_status='reserve' — это НЕ отдельный физический товар, а квота,
# выделенная на канал продаж из уже учтённого складского остатка
# (например, офферы Leroy Merlin — часть мадридского стока).
# Смешивать их с физическим остатком нельзя: получится двойной счёт.
RESERVE_STATUS = "reserve"
_status_norm = df["availability_status"].astype(str).str.strip().str.lower()
reserve_df = df[_status_norm == RESERVE_STATUS].copy()
df = df[_status_norm != RESERVE_STATUS].copy()

# страховка: если физических строк не осталось (например, в снапшот попали
# только квоты каналов) — показываем то, что есть, но честно предупреждаем
if df.empty and not reserve_df.empty:
    st.info(t("stock.only_channels"))
    df = reserve_df.copy()
    reserve_df = reserve_df.iloc[0:0]

# ---------- фильтры ----------
c1, c2, c3, c4 = st.columns(4)
with c1:
    wh_filter = st.text_input(t("stock.filter.warehouse"))
with c2:
    sku_filter = st.text_input(t("stock.filter.sku"))
with c3:
    status_filter = st.selectbox(
        t("stock.filter.avail_status"),
        [t("stock.filter.all")] + sorted(df["availability_status"].dropna().unique().tolist()),
    )
with c4:
    country_filter = st.multiselect(
        t("stock.filter.country"),
        sorted(df["location"].unique().tolist()),
        placeholder=t("stock.filter.country_placeholder"),
    )

f = df.copy()
if wh_filter:
    f = f[f["warehouse_name"].str.contains(wh_filter, case=False, na=False)]
if sku_filter:
    f = f[f["sku_display"].str.contains(sku_filter, case=False, na=False)
          | f["sku"].str.contains(sku_filter, case=False, na=False)]
if status_filter != t("stock.filter.all"):
    f = f[f["availability_status"] == status_filter]
if country_filter:
    f = f[f["location"].isin(country_filter)]

# ---------- KPI ----------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("stock.kpi.total_sku"), f["sku"].nunique())
k2.metric(t("stock.kpi.countries"), f["location"].nunique(),
          help=t("stock.kpi.countries_help"))
k3.metric(t("stock.kpi.total_qty"), int(f["quantity"].sum()),
          help=t("stock.kpi.total_qty_help"))
k4.metric(t("stock.kpi.median"),
          int(f.groupby("sku")["quantity"].sum().median()) if len(f) else 0)
low_stock = (f.groupby("sku")["quantity"].sum() <= 3).sum()
k5.metric(t("stock.kpi.low_stock"), int(low_stock),
          delta=None, help=t("stock.kpi.low_stock_help"))

# ---------- квоты, выделенные на каналы продаж ----------
if not reserve_df.empty:
    with st.expander(t("stock.channels.title").format(
            n=int(reserve_df["quantity"].sum()))):
        st.caption(t("stock.channels.caption"))
        ch = (reserve_df.groupby("warehouse_name", as_index=False)
                        .agg(quantity=("quantity", "sum"), skus=("sku", "nunique")))
        ch_cols = st.columns(min(len(ch), 4) or 1)
        unit_ = t("stock.ov.unit_short")
        for i, (_, row) in enumerate(ch.iterrows()):
            with ch_cols[i % len(ch_cols)]:
                st.metric(row["warehouse_name"], f"{int(row['quantity'])} {unit_}",
                          help=t("stock.ctr.metric_help").format(n=int(row["skus"])))

        ch_tbl = (reserve_df.groupby(["warehouse_name", "sku_display", "product_name"],
                                     as_index=False)["quantity"].sum()
                            .sort_values("quantity", ascending=False))
        st.dataframe(
            ch_tbl, use_container_width=True, height=320, hide_index=True,
            column_config={
                "warehouse_name": st.column_config.TextColumn(
                    t("stock.channels.col_channel"), width="medium"),
                "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "quantity": st.column_config.NumberColumn(
                    t("stock.channels.col_qty"), width="small"),
            },
        )
        st.download_button(
            t("stock.channels.download"),
            ch_tbl.to_csv(index=False).encode("utf-8-sig"),
            file_name="stock_channel_quotas.csv", mime="text/csv",
        )

st.divider()

# ---------- 🔥 Минимальные остатки ----------
burn = (f.groupby(["sku_display", "asin", "product_name"], as_index=False)["quantity"].sum()
          .sort_values("quantity").head(5))

if not burn.empty and burn["quantity"].min() <= 3:
    st.markdown(f"#### {t('stock.burn_title')}")
    bcols = st.columns(len(burn))
    unit = t("stock.ov.unit_short")
    for col, (_, row) in zip(bcols, burn.iterrows()):
        by_country = (f[f["sku_display"] == row["sku_display"]]
                        .groupby("location")["quantity"].sum())
        by_country = by_country[by_country > 0].sort_values(ascending=False)
        country_str = " · ".join(f"{c}: {int(q)}" for c, q in by_country.items())
        with col:
            st.metric(
                label=str(row["sku_display"])[:18],
                value=f"{int(row['quantity'])} {unit}",
                help=f"{row['product_name'][:80]}",
            )
            st.caption(f"📍 {country_str}" if country_str else t("stock.burn_none"))
    st.divider()

# Период — один на страницу и общий для всего Кабинета. Стоит над
# вкладками, а не внутри карты: три вкладки читают одни и те же остатки,
# и разные окна на одной странице путали бы сильнее, чем помогали
_pc1, _pc2 = st.columns([2, 2])
PERIOD = period_mod.control(columns=(_pc1, _pc2))

# Обзор, ABC, По странам и Таблица скрыты до доработки: показывать
# полупустые вкладки хуже, чем не показывать их вовсе
SHOW_DRAFT_TABS = False

if SHOW_DRAFT_TABS:
    (tab_cov, tab_cat, tab_map, tab_overview,
     tab_abc, tab_countries, tab_table) = st.tabs(
        [t("stock.tab.coverage"), t("stock.tab.categories"),
         t("stock.tab.map"), t("stock.tab.overview"), t("stock.tab.abc"),
         t("stock.tab.countries"), t("stock.tab.table")])
else:
    tab_cov, tab_cat, tab_map = st.tabs(
        [t("stock.tab.coverage"), t("stock.tab.categories"),
         t("stock.tab.map")])
    tab_overview = tab_abc = tab_countries = tab_table = None

BLUE = "#1f77b4"
ACCENT = "#e8484d"  # фирменный красный Dnipro-M

if SHOW_DRAFT_TABS:
    # ---------- Обзор ----------
    with tab_overview:
        left, right = st.columns([3, 2])

        with left:
            top = (f.groupby(["sku_display", "product_name"], as_index=False)["quantity"]
                     .sum().nlargest(15, "quantity"))
            top["label"] = top["product_name"].str.slice(0, 45) + "…"
            fig = px.bar(
                top.sort_values("quantity"),
                x="quantity", y="label", orientation="h",
                text="quantity", title=t("stock.ov.top15_title"),
                color_discrete_sequence=[BLUE],
                hover_data={"sku_display": True, "label": False},
            )
            fig.update_layout(height=520, yaxis_title=None, xaxis_title=t("stock.ov.unit_short"),
                              margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with right:
            by_status = f.groupby("availability_status", as_index=False)["quantity"].sum()
            fig = px.pie(by_status, names="availability_status", values="quantity",
                         hole=0.55, title=t("stock.ov.by_status_title"),
                         color_discrete_sequence=[BLUE, ACCENT, "#9aa4b2", "#f2b134"])
            fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

            hist = px.histogram(
                f.groupby("sku", as_index=False)["quantity"].sum(),
                x="quantity", nbins=20,
                title=t("stock.ov.dist_title"),
                color_discrete_sequence=[BLUE],
            )
            hist.update_layout(height=250, xaxis_title=t("stock.ov.dist_xaxis"),
                               yaxis_title=t("stock.cat.sku_word"), margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(hist, use_container_width=True)

# ---------- Покрытие: на сколько недель хватит ----------
with tab_cov:
    cov = load_coverage()
    if cov.empty:
        d = coverage_diag()
        err = d["error"] or st.session_state.get("_cov_error")
        if err:
            st.error(t("cov.err.query").format(e=err))
        elif not d["table"]:
            st.error(t("cov.err.no_table"))
        elif not d["rows"]:
            st.warning(t("cov.err.no_rows"))
        else:
            # строки есть, а выборка пуста — значит разошлись calc_date
            # в запросе и в таблице. Показываем обе стороны, чтобы не
            # гадать: расчёт не доехал или сматчился не с тем днём
            st.warning(t("cov.err.no_match").format(
                n=d["rows"],
                d=("—" if pd.isna(pd.Timestamp(d["last_calc"]))
                   else pd.Timestamp(d["last_calc"]).strftime("%d.%m.%Y %H:%M"))))
        st.caption(t("stock.cov.no_data"))
    else:
        for c in ("available_now", "coverage_weeks", "fbm_fallback_qty",
                  "total_coverage_weeks", "realistic_coverage_weeks",
                  "pool_exhaustion_weeks", "competing_marketplaces",
                  "pool_total_weekly_demand", "gaps_count", "gaps_total_qty",
                  "overstock_qty", "overstock_weeks", "odoo_incoming_qty",
                  "weeks_until_first_gap"):
            if c in cov.columns:
                cov[c] = pd.to_numeric(cov[c], errors="coerce")
        cov["coverage_status"] = cov["coverage_status"].fillna("ok")

        calc_d = pd.to_datetime(cov["calc_date"].iloc[0]).strftime("%d.%m.%Y")
        # Период страницы сюда не приходит: покрытие считается на дату
        # расчёта. Молча игнорировать выбор нельзя — человек выберет
        # «7 дней» и решит, что цифры за неделю
        st.caption(t("period.snapshot").format(d=calc_d))
        hc1, hc2 = st.columns([3, 1])
        hc1.markdown(f"##### {t('stock.cov.header').format(d=calc_d)}")
        with hc2.popover(t("stock.cov.how"), use_container_width=True):
            st.markdown(t("stock.cov.intro"))
            st.markdown("---")
            st.markdown(t("stock.cov.horizon_note"))

        CST = {"critical": t("stock.cov.st_critical"),
               "warning": t("stock.cov.st_warning"),
               "ok": t("stock.cov.st_ok")}

        cf1, cf2 = st.columns([1.3, 2])
        with cf1:
            cov_mps = sorted(cov["marketplace"].dropna().unique().tolist())
            cov_mp = st.multiselect(t("stock.cov.filter_mp"), cov_mps,
                                    default=cov_mps, key="cov_mp")
        with cf2:
            cov_st = st.multiselect(
                t("stock.cov.filter_status"), list(CST.values()),
                default=[CST["critical"], CST["warning"]], key="cov_st")

        cv = cov[cov["marketplace"].isin(cov_mp)].copy()

        n_crit = int((cv["coverage_status"] == "critical").sum())
        n_warn = int((cv["coverage_status"] == "warning").sum())
        n_switch = int(cv["channel_switch_week"].notna().sum())
        n_pool = int((cv["pool_exhaustion_weeks"]
                      < cv["total_coverage_weeks"]).sum())
        n_over = int((cv["overstock_qty"].fillna(0) > 0).sum())
        n_multi = int((cv["gaps_count"].fillna(0) > 1).sum())

        # карточки работают как фильтр: нажал — таблица отфильтровалась
        if "cov_quick" not in st.session_state:
            st.session_state.cov_quick = None

        def _toggle(key: str):
            st.session_state.cov_quick = (
                None if st.session_state.cov_quick == key else key)

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric(t("stock.cov.kpi_critical"), f"{n_crit:,}",
                      help=t("stock.cov.kpi_critical_help"))
            st.button(t("stock.cov.show"), key="btn_crit",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "critical"
                            else "secondary"),
                      on_click=_toggle, args=("critical",))
        with m2:
            st.metric(t("stock.cov.kpi_warning"), f"{n_warn:,}",
                      help=t("stock.cov.kpi_warning_help"))
            st.button(t("stock.cov.show"), key="btn_warn",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "warning"
                            else "secondary"),
                      on_click=_toggle, args=("warning",))
        with m3:
            st.metric(t("stock.cov.kpi_switch"), f"{n_switch:,}",
                      help=t("stock.cov.kpi_switch_help"))
            st.button(t("stock.cov.show"), key="btn_switch",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "switch"
                            else "secondary"),
                      on_click=_toggle, args=("switch",))
        with m4:
            st.metric(t("stock.cov.kpi_pool"), f"{n_pool:,}",
                      help=t("stock.cov.kpi_pool_help"))
            st.button(t("stock.cov.show"), key="btn_pool",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "pool"
                            else "secondary"),
                      on_click=_toggle, args=("pool",))
        with m5:
            st.metric(t("stock.cov.kpi_overstock"), f"{n_over:,}",
                      help=t("stock.cov.kpi_overstock_help"))
            st.button(t("stock.cov.show"), key="btn_over",
                      use_container_width=True,
                      type=("primary" if st.session_state.cov_quick == "over"
                            else "secondary"),
                      on_click=_toggle, args=("over",))

        quick = st.session_state.cov_quick
        if quick == "critical":
            cv = cv[cv["coverage_status"] == "critical"]
        elif quick == "warning":
            cv = cv[cv["coverage_status"] == "warning"]
        elif quick == "switch":
            cv = cv[cv["channel_switch_week"].notna()]
        elif quick == "pool":
            cv = cv[cv["pool_exhaustion_weeks"] < cv["total_coverage_weeks"]]
        elif quick == "over":
            cv = cv[cv["overstock_qty"].fillna(0) > 0]
        elif cov_st:
            keys = [k for k, v in CST.items() if v in cov_st]
            cv = cv[cv["coverage_status"].isin(keys)]

        st.markdown("")
        if cv.empty:
            st.info(t("common.no_data"))
        else:
            cview = cv.sort_values(["realistic_coverage_weeks", "sku"]).copy()
            cview["status_label"] = cview["coverage_status"].map(CST)
            cview["first_deficit_week"] = pd.to_datetime(
                cview["first_deficit_week"], errors="coerce").dt.strftime("%d.%m.%Y")
            cview["shared_note"] = np.where(
                (cview["pool_exhaustion_weeks"] < cview["total_coverage_weeks"])
                & (cview["competing_marketplaces"] > 1),
                cview["competing_marketplaces"].fillna(0).astype(int).astype(str)
                + " " + t("stock.cov.col_shared_suffix"),
                "—")

            # ASIN в coverage_summary нет — добираем по артикулу из общего
            # справочника, чтобы из таблицы можно было открыть карточку
            cview["asin_url"] = catalog.url_series(
                skus=cview["sku"], markets=cview["marketplace"])
            cview["photo"] = catalog.image_series(
                skus=cview["sku"], markets=cview["marketplace"])
            st.dataframe(
                cview[["photo", "sku", "asin_url", "product_name",
                       "marketplace",
                       "available_now",
                       "weeks_until_first_gap", "coverage_weeks",
                       "fbm_fallback_qty", "total_coverage_weeks",
                       "shared_note", "realistic_coverage_weeks",
                       "first_deficit_week", "gaps_count", "gaps_total_qty",
                       "odoo_incoming_qty", "overstock_qty", "status_label"]],
                use_container_width=True, height=460, hide_index=True,
                column_config={
                    "photo": catalog.image_column(),
                    "sku": st.column_config.TextColumn("SKU", width="small"),
                    "asin_url": catalog.asin_column(),
                    "product_name": st.column_config.TextColumn(
                        t("stock.ctr.col_product"), width="medium"),
                    "marketplace": st.column_config.TextColumn(
                        t("stock.cov.col_mp"), width="small"),
                    "available_now": st.column_config.NumberColumn(
                        t("stock.cov.col_stock"), width="small"),
                    "weeks_until_first_gap": st.column_config.NumberColumn(
                        t("stock.cov.col_until_gap"), width="small",
                        help=t("stock.cov.col_until_gap_help")),
                    "coverage_weeks": st.column_config.NumberColumn(
                        t("stock.cov.col_weeks_fba"), width="small",
                        help=t("stock.cov.col_weeks_fba_help")),
                    "fbm_fallback_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_madrid"), width="small",
                        help=t("stock.cov.col_madrid_help")),
                    "total_coverage_weeks": st.column_config.NumberColumn(
                        t("stock.cov.col_weeks_total"), width="small",
                        help=t("stock.cov.col_weeks_total_help")),
                    "shared_note": st.column_config.TextColumn(
                        t("stock.cov.col_shared"), width="small",
                        help=t("stock.cov.col_shared_help")),
                    "realistic_coverage_weeks": st.column_config.ProgressColumn(
                        t("stock.cov.col_weeks_real"), format="%d",
                        min_value=0, max_value=26,
                        help=t("stock.cov.col_weeks_real_help")),
                    "first_deficit_week": st.column_config.TextColumn(
                        t("stock.cov.col_first_deficit"), width="small"),
                    "gaps_count": st.column_config.NumberColumn(
                        t("stock.cov.col_gaps"), width="small",
                        help=t("stock.cov.col_gaps_help")),
                    "gaps_total_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_gaps_qty"), format="%.0f", width="small",
                        help=t("stock.cov.col_gaps_qty_help")),
                    "odoo_incoming_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_odoo"), format="%.0f", width="small",
                        help=t("stock.cov.col_odoo_help")),
                    "overstock_qty": st.column_config.NumberColumn(
                        t("stock.cov.col_overstock"), format="%.0f", width="small",
                        help=t("stock.cov.col_overstock_help")),
                    "status_label": st.column_config.TextColumn(
                        t("stock.cov.col_status"), width="small"),
                },
            )
            st.caption(t("stock.cov.note"))

            # ---- проекция по неделям для выбранного товара ----
            st.divider()
            st.markdown(f"##### {t('stock.cov.weekly_title')}")
            opts = (cv.sort_values(["realistic_coverage_weeks", "sku"])
                      .assign(label=lambda d: d["sku"] + " · " + d["marketplace"]
                              + " · " + d["product_name"].str.slice(0, 40)))
            pick = st.selectbox(t("stock.cov.pick"), opts["label"].tolist(),
                                key="cov_pick")
            prow = opts[opts["label"] == pick].iloc[0]

            pw_ = prow.get("pool_exhaustion_weeks")
            tw_ = prow.get("total_coverage_weeks")
            shared = (pd.notna(pw_) and pd.notna(tw_) and pw_ < tw_
                      and int(prow.get("competing_marketplaces") or 0) > 1)
            if shared:
                st.warning(t("stock.cov.pool_warn").format(
                    n=int(prow["competing_marketplaces"]),
                    qty=int(prow["fbm_fallback_qty"] or 0),
                    demand=float(prow["pool_total_weekly_demand"] or 0),
                    pool_weeks=int(pw_), promised=int(tw_)))

            # разрывы: где именно товар кончается и на сколько
            gaps = prow.get("gaps_detail")
            if isinstance(gaps, str):
                import json
                try:
                    gaps = json.loads(gaps)
                except Exception:
                    gaps = None
            if gaps:
                gl_, gr_ = st.columns([1, 1])
                gl_.metric(t("stock.cov.gaps_found"), f"{len(gaps)}")
                gr_.metric(t("stock.cov.gaps_qty"),
                           f"{float(prow.get('gaps_total_qty') or 0):,.0f}",
                           help=t("stock.cov.gaps_qty_help"))
                gdf = pd.DataFrame(gaps)
                gdf["start"] = pd.to_datetime(gdf["start"]).dt.strftime("%d.%m.%Y")
                gdf["end"] = pd.to_datetime(gdf["end"]).dt.strftime("%d.%m.%Y")
                st.dataframe(
                    gdf[["start", "end", "qty"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "start": st.column_config.TextColumn(
                            t("stock.cov.gap_from"), width="small"),
                        "end": st.column_config.TextColumn(
                            t("stock.cov.gap_to"), width="small"),
                        "qty": st.column_config.NumberColumn(
                            t("stock.cov.gap_qty"), format="%.0f"),
                    },
                )

            odoo_q = float(prow.get("odoo_incoming_qty") or 0)
            if odoo_q > 0:
                st.caption(t("stock.cov.odoo_note").format(qty=int(odoo_q)))

            over_q = float(prow.get("overstock_qty") or 0)
            if over_q > 0:
                st.info(t("stock.cov.overstock_note").format(
                    qty=int(over_q),
                    weeks=int(float(prow.get("overstock_weeks") or 0))))

            proj = load_projection(prow["sku"], prow["marketplace"])
            if proj.empty:
                st.info(t("stock.cov.no_projection"))
            else:
                proj["week_start"] = pd.to_datetime(proj["week_start"])
                proj["label"] = (proj["week_num"].astype(str) + ". "
                                 + proj["week_start"].dt.strftime("%d.%m"))

                pfig = go.Figure()
                pfig.add_bar(name=t("stock.cov.p_begin"), x=proj["label"],
                             y=proj["stock_begin"], marker_color=BLUE, opacity=0.55)
                pfig.add_bar(name=t("stock.cov.p_incoming"), x=proj["label"],
                             y=proj["incoming"], marker_color="#2e9e5b")
                pfig.add_scatter(name=t("stock.cov.p_forecast"), x=proj["label"],
                                 y=proj["forecast"], mode="lines+markers",
                                 line=dict(color=ACCENT, width=2))
                pfig.add_bar(name=t("stock.cov.p_unmet"), x=proj["label"],
                             y=proj["unmet_demand"], marker_color=ACCENT, opacity=0.4)

                if shared:
                    i = int(pw_)
                    if 0 <= i < len(proj):
                        pfig.add_shape(type="line", xref="x", yref="paper",
                                       x0=i, x1=i, y0=0, y1=1,
                                       line=dict(color=ACCENT, width=2, dash="dash"),
                                       opacity=0.8)
                        pfig.add_annotation(xref="x", yref="paper", x=i, y=1.02,
                                            text=t("stock.cov.p_pool_line"),
                                            showarrow=False, xanchor="left",
                                            font=dict(color=ACCENT, size=11))

                pfig.update_layout(
                    barmode="group", height=340,
                    margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                    legend=dict(orientation="h", y=1.16),
                    xaxis=dict(type="category", categoryorder="array",
                               categoryarray=proj["label"].tolist()))
                st.plotly_chart(pfig, use_container_width=True,
                                config={"displayModeBar": False})

                ptbl = proj.copy()
                ptbl["week_start"] = ptbl["week_start"].dt.strftime("%d.%m.%Y")
                ptbl["covered"] = np.where(ptbl["is_covered"],
                                           t("stock.cov.p_covered"),
                                           t("stock.cov.p_deficit"))
                st.dataframe(
                    ptbl[["week_num", "week_start", "stock_begin", "incoming",
                          "forecast", "stock_end", "unmet_demand", "covered"]],
                    use_container_width=True, height=360, hide_index=True,
                    column_config={
                        "week_num": st.column_config.NumberColumn(
                            t("stock.cov.p_week"), width="small"),
                        "week_start": st.column_config.TextColumn(
                            t("stock.cov.p_from"), width="small"),
                        "stock_begin": st.column_config.NumberColumn(
                            t("stock.cov.p_begin"), format="%.0f"),
                        "incoming": st.column_config.NumberColumn(
                            t("stock.cov.p_incoming"), format="%.0f"),
                        "forecast": st.column_config.NumberColumn(
                            t("stock.cov.p_forecast"), format="%.1f"),
                        "stock_end": st.column_config.NumberColumn(
                            t("stock.cov.p_end"), format="%.0f"),
                        "unmet_demand": st.column_config.NumberColumn(
                            t("stock.cov.p_unmet"), format="%.1f"),
                        "covered": st.column_config.TextColumn(
                            t("stock.cov.p_result"), width="small"),
                    },
                )
                st.caption(t("stock.cov.weekly_note"))

            cd1, cd2 = st.columns([1, 1])
            with cd1:
                st.download_button(
                    t("stock.cov.download"),
                    cview.to_csv(index=False).encode("utf-8-sig"),
                    file_name="coverage.csv", mime="text/csv",
                    use_container_width=True)
            with cd2:
                st.page_link("pages/4_Reorder.py", label=t("stock.cov.go_reorder"),
                             icon=":material/shopping_cart:",
                             use_container_width=True)


if SHOW_DRAFT_TABS:
    # ---------- ABC ----------
    with tab_abc:
        # группируем только по SKU: если добавить asin в ключ, строки с пустым
        # asin молча выпадут — pandas отбрасывает записи с NaN в группировке
        abc = (f.groupby("sku_display", as_index=False)
                 .agg(quantity=("quantity", "sum"),
                      asin=("asin", "first"),
                      product_name=("product_name", "first"))
                 .sort_values("quantity", ascending=False)
                 .reset_index(drop=True))

        if abc.empty or abc["quantity"].sum() <= 0:
            st.info(t("stock.abc.no_data"))
            st.stop()

        total = abc["quantity"].sum()
        abc["cum_pct"] = abc["quantity"].cumsum() / total * 100
        abc["class"] = np.where(abc["cum_pct"] <= 80, "A",
                        np.where(abc["cum_pct"] <= 95, "B", "C"))

        a1, a2, a3 = st.columns(3)
        for col, cls in zip((a1, a2, a3), ("A", "B", "C")):
            sub = abc[abc["class"] == cls]
            col.metric(t("stock.abc.class_label").format(cls=cls),
                       t("stock.abc.sku_count").format(n=len(sub)),
                       t("stock.abc.pct_of_stock").format(pct=sub['quantity'].sum() / total * 100))

        fig = go.Figure()
        colors = abc["class"].map({"A": ACCENT, "B": "#f2b134", "C": "#9aa4b2"})
        fig.add_bar(x=abc.index, y=abc["quantity"], marker_color=colors,
                    name=t("stock.abc.qty_legend"),
                    customdata=abc[["sku_display", "product_name", "class"]],
                    hovertemplate="<b>%{customdata[0]}</b> (" + t("stock.abc.class_word") + " %{customdata[2]})"
                                  "<br>%{customdata[1]}<br>" + t("stock.abc.stock_word") + ": %{y}"
                                  "<br><i>" + t("stock.abc.hover_click_hint") + "</i><extra></extra>")
        fig.add_scatter(x=abc.index, y=abc["cum_pct"], yaxis="y2",
                        name=t("stock.abc.cum_pct_legend"), line=dict(color=BLUE, width=2),
                        hoverinfo="skip")
        fig.add_hline(y=80, yref="y2", line_dash="dot", line_color="#666",
                      annotation_text="80%")
        fig.update_layout(
            title=t("stock.abc.pareto_title"),
            height=480,
            yaxis=dict(title=t("stock.ov.unit_short")),
            yaxis2=dict(title=t("stock.abc.yaxis_pct"), overlaying="y", side="right",
                        range=[0, 105]),
            xaxis=dict(title=t("stock.abc.xaxis"), showticklabels=False),
            legend=dict(orientation="h", y=1.1),
            margin=dict(l=10, r=10, t=80, b=10),
        )
        event = st.plotly_chart(fig, use_container_width=True,
                                on_select="rerun", selection_mode="points",
                                key="abc_chart")

        pts = event.selection.points if event and event.selection else []
        if pts:
            idx = pts[0].get("point_index")
            if idx is not None and idx < len(abc):
                row = abc.iloc[idx]
                by_country = (f[f["sku_display"] == row["sku_display"]]
                                .groupby("location", as_index=False)["quantity"].sum()
                                .sort_values("quantity", ascending=False))
                cc1, cc2, cc3, cc4 = st.columns([2.5, 1, 1, 1.2])
                cc1.markdown(f"**{row['product_name']}**")
                cc2.metric(t("stock.abc.total_stock"), f"{int(row['quantity'])} {t('stock.ov.unit_short')}")
                cc3.metric(t("stock.abc.class_word"), row["class"])
                if pd.notna(row["asin"]) and str(row["asin"]) not in ("None", ""):
                    cc4.link_button(
                        t("stock.abc.open_amazon"),
                        catalog.url_series(asins=[row["asin"]])[0],
                        use_container_width=True)
                if len(by_country) > 1:
                    st.caption(f"{t('stock.abc.by_country_prefix')} " + " · ".join(
                        f"{r['location']}: {int(r['quantity'])}" for _, r in by_country.iterrows()
                    ))
        else:
            st.caption(t("stock.abc.click_hint"))

        st.caption(t("stock.abc.footer_note"))

# ---------- Категории ----------
with tab_cat:
    _snap = pd.to_datetime(df["snapshot_date"], errors="coerce").max()
    st.caption(t("period.snapshot").format(
        d=_snap.strftime("%d.%m.%Y") if pd.notna(_snap) else "—")
        if pd.notna(_snap) else t("period.snapshot_now"))
    by_cat = (f.groupby("category", as_index=False)
                .agg(quantity=("quantity", "sum"), skus=("sku", "nunique")))
    fig = px.treemap(by_cat, path=["category"], values="quantity",
                     title=t("stock.cat.treemap_title"),
                     color="quantity", color_continuous_scale="Blues",
                     custom_data=["skus"])
    fig.update_traces(hovertemplate="<b>%{label}</b><br>" + t("stock.abc.stock_word") + ": %{value} " + t("stock.ov.unit_short")
                                    + "<br>" + t("stock.cat.sku_word") + ": %{customdata[0]}<extra></extra>")
    fig.update_layout(height=450, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    pw = f.dropna(subset=["power_w"])
    if not pw.empty:
        fig = px.scatter(pw, x="power_w", y="quantity", color="category",
                         hover_data=["sku_display", "product_name"],
                         title=t("stock.cat.power_scatter_title"))
        fig.update_layout(height=400, xaxis_title=t("stock.cat.power_xaxis"),
                          yaxis_title=t("stock.cat.qty_yaxis"),
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

if SHOW_DRAFT_TABS:
    # ---------- По странам ----------
    with tab_countries:
        st.markdown(f"##### {t('stock.ctr.by_country_title')}")
        by_country = (f.groupby("location", as_index=False)
                        .agg(quantity=("quantity", "sum"), skus=("sku", "nunique"))
                        .sort_values("quantity", ascending=False))

        cc = st.columns(min(len(by_country), 6) or 1)
        unit = t("stock.ov.unit_short")
        for i, (_, row) in enumerate(by_country.iterrows()):
            with cc[i % len(cc)]:
                st.metric(row["location"], f"{int(row['quantity'])} {unit}",
                         help=t("stock.ctr.metric_help").format(n=int(row['skus'])))

        fig = px.bar(by_country, x="location", y="quantity", text="quantity",
                     title=t("stock.ctr.bar_title"), color_discrete_sequence=[BLUE])
        fig.update_layout(height=380, xaxis_title=t("stock.ctr.country_axis"), yaxis_title=t("stock.cat.qty_yaxis"),
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"##### {t('stock.ctr.matrix_title')}")
        top_skus_df = (f.groupby(["sku_display", "product_name"], as_index=False)["quantity"]
                         .sum().nlargest(20, "quantity"))
        top_skus = top_skus_df["sku_display"].tolist()
        name_map = dict(zip(top_skus_df["sku_display"], top_skus_df["product_name"]))
        matrix_src = f[f["sku_display"].isin(top_skus)]
        pivot = (matrix_src.pivot_table(index="sku_display", columns="location",
                                        values="quantity", aggfunc="sum", fill_value=0)
                            .reindex(top_skus))

        y_labels = [f"{sku} · {name_map.get(sku, '')[:28]}" for sku in pivot.index]

        fig = px.imshow(
            pivot.values,
            x=pivot.columns.tolist(),
            y=y_labels,
            color_continuous_scale="Blues",
            aspect="auto",
            labels=dict(x=t("stock.ctr.country_axis"), y="", color=t("stock.abc.stock_word")),
        )
        fig.update_traces(
            hovertemplate="<b>%{y}</b><br>" + t("stock.ctr.country_axis") + ": %{x}<br>" + t("stock.abc.stock_word") + ": %{z} " + t("stock.ov.unit_short") + "<extra></extra>"
        )
        fig.update_layout(
            height=44 * len(pivot) + 100,
            margin=dict(l=10, r=10, t=20, b=10),
            coloraxis_showscale=False,
        )
        event = st.plotly_chart(fig, use_container_width=True,
                                on_select="rerun", key="stock_matrix")

        pts = event.selection.points if event and event.selection else []
        if pts:
            y_clicked = pts[0].get("y")
            sku_clicked = None
            for sku, lbl in zip(pivot.index, y_labels):
                if lbl == y_clicked:
                    sku_clicked = sku
                    break
            if sku_clicked:
                row_info = f[f["sku_display"] == sku_clicked].iloc[0]
                by_country = (f[f["sku_display"] == sku_clicked]
                                .groupby("location", as_index=False)["quantity"].sum()
                                .sort_values("quantity", ascending=False))
                total_qty = int(by_country["quantity"].sum())

                cc1, cc2, cc3 = st.columns([2.5, 1, 1.2])
                cc1.markdown(f"**{row_info['product_name']}**  \n`{sku_clicked}`")
                cc2.metric(t("stock.abc.total_stock"), f"{total_qty} {unit}")
                cc3.link_button(
                    t("stock.abc.open_amazon"),
                    catalog.url_series(asins=[row_info["asin"]],
                                       skus=[sku_clicked])[0],
                    use_container_width=True)

                bc = st.columns(min(len(by_country), 6) or 1)
                for i, (_, r) in enumerate(by_country.iterrows()):
                    with bc[i % len(bc)]:
                        st.metric(r["location"], f"{int(r['quantity'])} {unit}")
        else:
            st.caption(t("stock.ctr.click_hint"))

        st.caption(t("stock.ctr.map_note"))

        st.divider()

        # ---------- полная таблица по ВСЕМ SKU ----------
        st.markdown(f"##### {t('stock.ctr.full_table_title')}")

        full_pivot = (f.pivot_table(index="sku_display", columns="location",
                                    values="quantity", aggfunc="sum", fill_value=0))
        total_col = t("stock.ctr.col_total")
        full_pivot[total_col] = full_pivot.sum(axis=1)
        full_pivot = full_pivot.sort_values(total_col, ascending=False)

        full_name_map = f.drop_duplicates("sku_display").set_index("sku_display")["product_name"]
        full_asin_map = f.drop_duplicates("sku_display").set_index("sku_display")["asin"]

        table_view = full_pivot.reset_index()
        table_view.insert(1, t("stock.ctr.col_product"), table_view["sku_display"].map(full_name_map))
        table_view.insert(0, "photo", catalog.image_series(
            asins=table_view["sku_display"].map(full_asin_map),
            skus=table_view["sku_display"]))
        table_view.insert(3, "asin_url", catalog.url_series(
            asins=table_view["sku_display"].map(full_asin_map),
            skus=table_view["sku_display"]))

        country_cols = [c for c in full_pivot.columns if c != total_col]
        st.dataframe(
            table_view, use_container_width=True, height=520, hide_index=True,
            column_config={
                "photo": catalog.image_column(),
                "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                t("stock.ctr.col_product"): st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                "asin_url": catalog.asin_column(),
                total_col: st.column_config.NumberColumn(total_col, width="small"),
                **{col: st.column_config.NumberColumn(col, width="small")
                   for col in country_cols},
            },
        )

        # ---------- строка ИТОГО ----------
        totals = {c: int(full_pivot[c].sum()) for c in full_pivot.columns}
        tcols = st.columns(len(totals) + 1)
        tcols[0].markdown(f"**{t('stock.ctr.total_row')}**")
        for i, (country, val) in enumerate(totals.items(), start=1):
            tcols[i].metric(country, f"{val}")

        st.download_button(
            t("stock.ctr.download_matrix"),
            table_view.to_csv(index=False).encode("utf-8-sig"),
            file_name="stock_by_country_full.csv",
            mime="text/csv",
        )

        # ---------- дефекты / возвраты ----------
        if not defects_df.empty:
            st.divider()
            st.markdown(f"##### {t('stock.ctr.defects_title')}")
            st.caption(t("stock.ctr.defects_caption"))
            dfx = (defects_df.groupby(["sku", "product_name"], as_index=False)
                             .agg(quantity=("quantity", "sum"),
                                  countries=("location", "nunique")))
            dfx = dfx.sort_values("quantity", ascending=False)
            dfx["asin_url"] = catalog.url_series(skus=dfx["sku"])
            dfx["photo"] = catalog.image_series(skus=dfx["sku"])
            st.dataframe(
                dfx[["photo", "sku", "asin_url", "product_name", "quantity",
                     "countries"]],
                use_container_width=True, height=280, hide_index=True,
                column_config={
                    "photo": catalog.image_column(),
                    "sku": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="medium"),
                    "asin_url": catalog.asin_column(),
                    "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                    "quantity": st.column_config.NumberColumn(t("stock.abc.stock_word"), width="small"),
                    "countries": st.column_config.NumberColumn(t("stock.tbl.col_countries"), width="small"),
                },
            )
            st.download_button(
                t("stock.ctr.defects_download"),
                defects_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="stock_defects.csv", mime="text/csv",
            )

if SHOW_DRAFT_TABS:
    # ---------- Таблица ----------
    with tab_table:
        view_by_product = t("stock.tbl.view_by_product")
        view_by_product_country = t("stock.tbl.view_by_product_country")
        view_mode = st.radio(
            t("stock.tbl.view_mode"),
            [view_by_product, view_by_product_country],
            horizontal=True,
        )

        if view_mode == view_by_product:
            tbl = (f.groupby("sku_display", as_index=False)
                     .agg(quantity=("quantity", "sum"),
                          countries=("location", "nunique"),
                          asin=("asin", "first"),
                          product_name=("product_name", "first"),
                          category=("category", "first")))
            # Домен по стране, а не всегда испанский: у товара, который
            # продаётся только в Германии, испанская ссылка вела на чужую
            # витрину. Страна берётся из строки, ASIN — готовый
            tbl["amazon_url"] = catalog.url_series(
                asins=tbl["asin"], skus=tbl["sku_display"])
            tbl = tbl.sort_values("quantity", ascending=False)
            tbl["photo"] = catalog.image_series(asins=tbl["asin"],
                                               skus=tbl["sku_display"])
            st.dataframe(
                tbl[["photo", "sku_display", "product_name", "quantity",
                     "countries", "category", "amazon_url"]],
                use_container_width=True, height=560, hide_index=True,
                column_config={
                    "photo": catalog.image_column(),
                    "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                    "quantity": st.column_config.ProgressColumn(
                        t("stock.tbl.col_total_stock"), format="%d",
                        min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                    ),
                    "countries": st.column_config.NumberColumn(
                        t("stock.tbl.col_countries"), width="small",
                        help=t("stock.tbl.col_countries_help")),
                    "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                    "amazon_url": st.column_config.LinkColumn(
                        t("stock.tbl.col_listing"), display_text=t("stock.tbl.col_listing_text")),
                    "category": st.column_config.TextColumn(t("stock.tbl.col_category")),
                },
            )
        else:
            tbl = f.sort_values(["sku_display", "quantity"], ascending=[True, False]).copy()
            tbl["amazon_url"] = catalog.url_series(
                asins=tbl["asin"], skus=tbl["sku_display"],
                markets=tbl["location"])
            tbl["photo"] = catalog.image_series(
                asins=tbl["asin"], skus=tbl["sku_display"],
                markets=tbl["location"])
            st.dataframe(
                tbl[["photo", "sku_display", "product_name", "location",
                     "quantity", "availability_status", "category",
                     "amazon_url", "snapshot_date"]],
                use_container_width=True, height=560, hide_index=True,
                column_config={
                    "photo": catalog.image_column(),
                    "sku_display": st.column_config.TextColumn(t("stock.ctr.col_sku"), width="small"),
                    "quantity": st.column_config.ProgressColumn(
                        t("stock.tbl.col_stock"), format="%d",
                        min_value=0, max_value=int(tbl["quantity"].max()) if len(tbl) else 1,
                    ),
                    "location": st.column_config.TextColumn(t("stock.tbl.col_country"), width="small"),
                    "product_name": st.column_config.TextColumn(t("stock.ctr.col_product"), width="large"),
                    "amazon_url": st.column_config.LinkColumn(
                        t("stock.tbl.col_listing"), display_text=t("stock.tbl.col_listing_text")),
                    "availability_status": st.column_config.TextColumn(t("stock.tbl.col_status")),
                    "category": st.column_config.TextColumn(t("stock.tbl.col_category")),
                    "snapshot_date": st.column_config.TextColumn(t("stock.tbl.col_snapshot"), width="small"),
                },
            )

        st.download_button(
            t("stock.tbl.download_detail"),
            f.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"stock_{f['snapshot_date'].max()}.csv",
            mime="text/csv",
        ) 


# ═══════════════════════════════════════════════════════════════════
# ЗАПАСЫ AMAZON: КАРТА ЦЕНТРОВ FBA
# ═══════════════════════════════════════════════════════════════════

with tab_map:
    _centers = load_fba_centers()
    _stock = load_fba_center_stock()
    if _centers.empty or _stock.empty:
        st.info(t("stock.map.no_data"))
    else:
        # ---- кончился на складе ----
        # Товар с нулём и живым спросом теряет деньги каждый день, поэтому
        # блок стоит выше карточек и карты.
        #
        # Раньше здесь было два блока: красная строка с обрезанными
        # названиями через запятую и таблица под ней. Строка ничего не
        # добавляла — те же товары стояли в таблице целиком, — но
        # выглядела как отдельная находка и читалась хуже всего: по
        # «Перфоратор SDS-plus 1500 Вт с…» нельзя ни найти товар, ни
        # понять, сколько их. Осталась одна таблица, а красным — только
        # итог, ради которого блок и заметен
        _inv = load_fba_inventory()
        _sales = load_sales_by_asin(PERIOD.days)
        if not _inv.empty and not _sales.empty:
            # Ноль по пулам — максимум, а не сумма: EU и UK физически
            # разные склады, и запас в Британии не спасает европейский
            # листинг. Максимум читается как «нет нигде»
            _z = (_inv.assign(inbound=_inv[INV_INBOUND].sum(axis=1))
                      .groupby("asin", as_index=False)
                      .agg(avail=("available", "max"),
                           inb_working=("inb_working", "sum"),
                           inb_shipped=("inb_shipped", "sum"),
                           inb_receiving=("inb_receiving", "sum"),
                           inbound=("inbound", "sum"),
                           product=("product_name", "max"),
                           sku=("sku", lambda x: ", ".join(
                               sorted(set(map(str, x))))[:60])))
            _z = _z[_z["avail"] <= 0].merge(_sales, on="asin", how="inner")
        else:
            _z = pd.DataFrame()
        if not _z.empty:
            _today = pd.Timestamp.today().normalize()
            _start = _today - pd.Timedelta(days=PERIOD.days)
            _zero = load_zero_since()
            if _zero.empty:
                _z["zero_since"] = pd.NaT
            else:
                _z = _z.merge(_zero, on="asin", how="left")
            _z["zero_since"] = pd.to_datetime(_z["zero_since"], errors="coerce")
            _z["days_zero"] = (_today - _z["zero_since"]).dt.days
            # Скорость считаем по дням, когда запас ещё был: делить продажи
            # на весь период у товара, кончившегося три недели назад, —
            # занизить спрос втрое и увезти самую срочную строку вниз
            _live = ((_z["zero_since"] - _start).dt.days
                     .clip(lower=1, upper=PERIOD.days).fillna(PERIOD.days))
            _z["per_day"] = (pd.to_numeric(_z["units"], errors="coerce")
                             .fillna(0) / _live).round(2)
            _z["product"] = _z["product"].fillna(_z["asin"])
            _z["url"] = catalog.url_series(asins=_z["asin"], skus=_z["sku"],
                                           markets=_z["markets"])
            _z["photo"] = catalog.image_series(
                asins=_z["asin"], skus=_z["sku"], markets=_z["markets"])
            # Даты прибытия в данных нет вообще — только корзины inbound.
            # Пустые корзины гасим в прочерк: ноль во всех трёх читался бы
            # как «поставка на ноль штук», а её просто нет
            _blind = _z[INV_INBOUND].sum(axis=1) <= 0
            _z.loc[_blind, INV_INBOUND] = pd.NA
            # Сортировка двойная: сначала те, по кому ничего не едет, —
            # их простой сам не кончится, — внутри по скорости продаж
            _z["_urgent"] = _blind.astype(int)
            _z = _z.sort_values(["_urgent", "per_day"], ascending=[False, False])

            _n_blind = int(_blind.sum())
            _only_blind = False
            if _n_blind:
                st.error(t("stock.map.out_blind").format(
                    n=_n_blind, per=f"{_z.loc[_blind, 'per_day'].sum():.1f}"))
                # Из плашки должен быть путь к тем самым строкам. Названия
                # обратно в неё не возвращаем — их оттуда убирали как
                # нечитаемые; вместо этого один тумблер оставляет в
                # таблице ровно те товары, о которых плашка говорит
                _only_blind = st.toggle(
                    t("stock.map.out_only_blind").format(n=_n_blind),
                    value=False, key="map_only_blind")
            _view = _z[_z["_urgent"] == 1] if _only_blind else _z
            st.markdown(f"**{t('stock.map.out_title')}**")
            st.caption(t("stock.map.out_caption").format(
                n=len(_view), p=PERIOD.title))
            st.dataframe(
                _view[["photo", "sku", "url", "product", "per_day",
                       "days_zero", "markets"] + INV_INBOUND],
                use_container_width=True, hide_index=True,
                column_config={
                    "photo": catalog.image_column(),
                    "sku": st.column_config.TextColumn("SKU", width="small"),
                    # ASIN и ссылка — одна колонка: display_text вырезает
                    # ASIN из адреса, так что кода видно ровно столько же,
                    # а отдельный столбец со стрелкой не занимает ширину
                    "url": st.column_config.LinkColumn(
                        "ASIN", display_text=r"/dp/([A-Z0-9]{10})",
                        width="small", help=t("stock.map.out_asin_help")),
                    "product": st.column_config.TextColumn(
                        t("stock.map.out_product"), width="large"),
                    "per_day": st.column_config.NumberColumn(
                        t("stock.map.out_rate"), format="%.2f",
                        help=t("stock.map.out_rate_help")),
                    "days_zero": st.column_config.NumberColumn(
                        t("stock.map.out_days"),
                        help=t("stock.map.out_days_help")),
                    "markets": st.column_config.TextColumn(
                        t("stock.map.out_markets"), width="small",
                        help=t("stock.map.out_markets_help")),
                    "inb_working": st.column_config.NumberColumn(
                        t("stock.map.inb_working"),
                        help=t("stock.map.inb_working_help")),
                    "inb_shipped": st.column_config.NumberColumn(
                        t("stock.map.inb_shipped"),
                        help=t("stock.map.inb_shipped_help")),
                    "inb_receiving": st.column_config.NumberColumn(
                        t("stock.map.inb_receiving"),
                        help=t("stock.map.inb_receiving_help")),
                },
            )
            st.caption(t("stock.map.out_shown").format(
                n=len(_view), total=len(_z)))
            st.divider()

        # ---- карточки пулов ----
        if not _inv.empty:
            pools = st.columns(2)
            for i, (pool, key) in enumerate((("eu", "stock.map.pool_eu"),
                                             ("uk", "stock.map.pool_uk"))):
                part = _inv[_inv["pool"].astype(str).str.lower() == pool]
                if part.empty:
                    continue
                n_sku = int(part["asin"].nunique())
                n_fc = int(_centers.merge(
                    _stock, on="fc_code")["fc_code"].nunique()) if pool == "eu" else 0
                n_net = int(_centers["fc_code"].nunique())
                vals = [
                    (t("stock.map.available"), int(part["available"].sum())),
                    (t("stock.map.reserved"), int(part["reserved"].sum())),
                    (t("stock.map.inbound"),
                     int(part[INV_INBOUND].sum().sum())),
                    (t("stock.map.dead"), int(part["unsellable"].sum())),
                ]
                # Четыре st.metric в половинной колонке резали подписи до
                # «Доступ…» и «Нелик…». Верстаем строкой: занимает меньше
                # места и не обрезается ни на одном языке
                cells = "".join(
                    f'<div style="min-width:96px"><div style="font-size:0.78rem;'
                    f'color:var(--text-secondary)">{lbl}</div>'
                    f'<div style="font-size:1.35rem;font-weight:600">'
                    f'{v:,}</div></div>' for lbl, v in vals)
                with pools[i]:
                    st.markdown(
                        f'<div style="border:1px solid var(--border);'
                        f'border-radius:12px;padding:12px 16px;">'
                        f'<div style="font-size:0.85rem;'
                        f'color:var(--text-secondary);margin-bottom:8px">'
                        f'{t(key).format(n=n_sku, c=n_fc, total=n_net)}</div>'
                        f'<div style="display:flex;gap:18px;flex-wrap:wrap">'
                        f'{cells}</div></div>',
                        unsafe_allow_html=True)

        # ---- товар, страна, поиск ----
        # Период берём страничный: свой набор 7/30 на этой вкладке
        # означал, что цифры карты и цифры соседних вкладок посчитаны за
        # разные окна, а на экране это ничем не отличалось
        _days = PERIOD.days
        _moves = load_fba_ledger(_days, PERIOD.from_str, PERIOD.to_str)
        f1, f2, f3 = st.columns([2, 2, 2])
        with f1:
            _skus = (sorted(_moves["msku"].dropna().unique().tolist())
                     if not _moves.empty else [])
            _sku_pick = st.multiselect(
                t("stock.map.product"), options=_skus,
                placeholder=t("stock.map.all_products"), key="map_sku")
        if _sku_pick and not _moves.empty:
            _moves = _moves[_moves["msku"].isin(_sku_pick)]
        with f2:
            _countries = sorted(c for c in _centers["country"].dropna().unique()
                                if str(c).strip())
            _country_pick = st.multiselect(
                t("stock.map.country"), options=_countries,
                placeholder=t("stock.map.all_countries"), key="map_country")
        with f3:
            _q = st.text_input(t("stock.map.search"),
                               placeholder=t("stock.map.search_ph"),
                               key="map_search").strip()
        if _country_pick:
            # страна режет и точки, и движения: показывать дуги в центры,
            # которых на карте нет, — значит рисовать линии в никуда
            _centers = _centers[_centers["country"].isin(_country_pick)]
            if not _moves.empty:
                _moves = _moves[_moves["fc_code"].isin(_centers["fc_code"])]
        if _q and not _moves.empty:
            # одно поле на ASIN и SKU: человек не знает заранее, что у
            # него в буфере, и выбирать вид кода перед вводом — лишний шаг
            _m = (_moves["asin"].astype(str).str.contains(_q, case=False, na=False)
                  | _moves["msku"].astype(str).str.contains(_q, case=False, na=False))
            _moves = _moves[_m]
            if _moves.empty:
                st.info(t("stock.map.search_none").format(q=_q))

        if not _moves.empty:
            period_mod.show_note(PERIOD, _moves["day"].min(), _moves["day"].max())

        # ---- перемещения между центрами ----
        # Переброска — это отдельный тип события WhseTransfers, две строки
        # на одну дату и товар: минус в отдающем центре, плюс в
        # принимающем. Пара всегда совпадает по asin, msku и дате, поэтому
        # ищем её строго внутри этой тройки, а не по совпадению дня и SKU:
        # раньше в пару могли попасть отгрузка клиенту и приёмка поставки
        arcs = []
        if not _moves.empty:
            _tr = _moves[_moves["event"].astype(str).str.strip()
                         == EVT_TRANSFER]
            for _, grp in _tr.groupby(["day", "asin", "msku"], sort=False):
                src = grp[grp["qty"] < 0].copy()
                dst = grp[grp["qty"] > 0].copy()
                if src.empty or dst.empty:
                    continue
                src["left"] = src["qty"].abs()
                dst["left"] = dst["qty"]
                for si in src.index:
                    for di in dst.index:
                        take = min(src.at[si, "left"], dst.at[di, "left"])
                        if take <= 0:
                            continue
                        arcs.append({"from": src.at[si, "fc_code"],
                                     "to": dst.at[di, "fc_code"],
                                     "qty": float(take),
                                     "sku": grp["msku"].iloc[0]})
                        src.at[si, "left"] -= take
                        dst.at[di, "left"] -= take
                        if src.at[si, "left"] <= 0:
                            break
        arcs = pd.DataFrame(arcs, columns=["from", "to", "qty", "sku"])
        if not arcs.empty:
            arcs = arcs[arcs["from"] != arcs["to"]]

        # ---- карта ----
        pts = _centers.merge(_stock, on="fc_code", how="inner")
        _mx = float(pts["qty"].max()) or 1.0
        # Радиус в МЕТРАХ, а не в пикселях: pydeck сериализует строковое
        # radius_units как выражение (@@=pixels), deck.gl его не понимает и
        # молча берёт метры — точки накрывали пол-Европы. Числовые
        # ограничители в пикселях проходят как есть и держат размер
        # читаемым на любом зуме
        pts["radius"] = 15000 + 65000 * (pts["qty"] / _mx) ** 0.5
        pts["color"] = pts["qty"].apply(
            lambda q: [232, 72, 77, 200] if q > 200
            else ([49, 102, 145, 200] if q >= 80 else [150, 170, 190, 200]))
        pts["label"] = pts["fc_code"] + " · " + pts["qty"].astype(int).astype(str)

        layers = []
        if not arcs.empty:
            _c = _centers.set_index("fc_code")[["lat", "lon"]]
            a = arcs.merge(_c.rename(columns={"lat": "f_lat", "lon": "f_lon"}),
                           left_on="from", right_index=True, how="inner") \
                    .merge(_c.rename(columns={"lat": "t_lat", "lon": "t_lon"}),
                           left_on="to", right_index=True, how="inner")
            if not a.empty:
                a = (a.groupby(["from", "to", "f_lat", "f_lon", "t_lat", "t_lon"],
                               as_index=False)["qty"].sum())
                a["width"] = 1 + 5 * (a["qty"] / max(a["qty"].max(), 1))
                layers.append(pdk.Layer(
                    "ArcLayer", data=a,
                    get_source_position="[f_lon, f_lat]",
                    get_target_position="[t_lon, t_lat]",
                    get_source_color=[232, 72, 77, 120],
                    get_target_color=[232, 72, 77, 120],
                    get_width="width", pickable=False))
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=pts, get_position="[lon, lat]",
            get_radius="radius", radius_min_pixels=5, radius_max_pixels=30,
            get_fill_color="color", pickable=True, opacity=0.8))
        layers.append(pdk.Layer(
            "TextLayer", data=pts, get_position="[lon, lat]",
            get_text="label", get_size=11, get_color=[70, 80, 95],
            get_pixel_offset=[0, 18]))

        st.pydeck_chart(pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(
                latitude=float(pts["lat"].mean()),
                longitude=float(pts["lon"].mean()), zoom=3.4),
            # carto вместо mapbox: не требует токена, подложка та же OSM
            map_provider="carto", map_style="light",
            tooltip={"text": "{fc_code} · {city}\n{qty}"}))
        st.caption(t("stock.map.legend"))

        # ---- строка-итог ----
        if not arcs.empty:
            _tot = int(arcs["qty"].sum())
            _pairs = (arcs.groupby(["from", "to"], as_index=False)["qty"].sum()
                          .sort_values("qty", ascending=False))
            _city = dict(zip(_centers["fc_code"], _centers["city"]))
            _route = "; ".join(
                f"{_city.get(r['from'], r['from'])} → {_city.get(r['to'], r['to'])}"
                f" ({int(r['qty'])})" for _, r in _pairs.head(3).iterrows())
            _goods = ", ".join(sorted(arcs["sku"].dropna().unique())[:3])
            st.info(t("stock.map.summary").format(
                n=_tot, d=_days, routes=_route, goods=_goods or "—"))
        else:
            st.caption(t("stock.map.no_moves").format(d=_days))

        # ---- движения за период ----
        if not _moves.empty:
            st.markdown(f"**{t('stock.map.moves_title')}**")
            tbl = (_moves.groupby("fc_code", as_index=False)
                         .agg(shipped=("qty", lambda x: int(-x[x < 0].sum())),
                              net=("qty", "sum"),
                              goods=("msku", "nunique")))
            tbl["net"] = tbl["net"].astype(int)
            tbl = tbl.merge(_centers[["fc_code", "city"]], on="fc_code",
                            how="left").sort_values("shipped", ascending=False)
            st.dataframe(
                tbl[["fc_code", "city", "shipped", "net", "goods"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "fc_code": st.column_config.TextColumn(
                        t("stock.map.col_fc"), width="small"),
                    "city": st.column_config.TextColumn(t("stock.map.col_city")),
                    "shipped": st.column_config.NumberColumn(
                        t("stock.map.col_shipped"), width="medium"),
                    "net": st.column_config.NumberColumn(
                        t("stock.map.col_net"), format="%+d", width="medium",
                        help=t("stock.map.col_net_help")),
                    "goods": st.column_config.NumberColumn(
                        t("stock.map.col_goods"), width="medium"),
                },
            )

