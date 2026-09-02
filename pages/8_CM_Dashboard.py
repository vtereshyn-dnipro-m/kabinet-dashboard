# pages/8_CM_Dashboard.py — CM Dashboard: сводка по площадкам и здоровье каналов
from datetime import datetime, timedelta
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t
import period as period_mod
import catalog

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.7rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("cm.title"))
st.caption(t("cm.caption"))

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"
AMBER = "#f2b134"
GREY = "#9aa4b2"
PLOTLY_CFG = {"displayModeBar": False}

# площадки: Amazon по странам + Leroy Merlin (Испания, через Mirakl)
LM_CODE = "LM"
# Физический склад есть только у FBA, у площадок Mirakl остаток — квота
# на канал. Это свойство данных, а не список каналов: канал, под которым
# лежит склад, один, а витрин над ним сколько угодно
FBA_CHANNEL = "Amazon"
DEFAULT_CHANNEL = "Amazon"
MIRAKL_SRC = "mirakl"
LM_COUNTRY = "ES"

# пороги здоровья канала Leroy Merlin: (ok при >=, warn при >=) либо обратные
# совпадают с порогами загрузчика LM Health — иначе цвет на странице
# расходился бы с алертами
LM_THRESHOLDS = {
    "acceptance_rate_pct": {"ok": 95, "warn": 90, "higher_better": True},
    "tracking_rate_pct": {"ok": 95, "warn": 85, "higher_better": True},
    "on_time_ship_pct": {"ok": 95, "warn": 85, "higher_better": True},
    "avg_acceptance_h": {"ok": 24, "warn": 48, "higher_better": False},
    "p90_acceptance_h": {"ok": 48, "warn": 72, "higher_better": False},
    "incident_rate_pct": {"ok": 0, "warn": 3, "higher_better": False},
    "waiting_acceptance": {"ok": 0, "warn": 3, "higher_better": False},
}


def health_level(metric: str, value) -> str:
    """ok / warn / crit по порогам канала."""
    rule = LM_THRESHOLDS.get(metric)
    if rule is None or value is None or pd.isna(value):
        return "none"
    v = float(value)
    if rule["higher_better"]:
        return "ok" if v >= rule["ok"] else ("warn" if v >= rule["warn"] else "crit")
    return "ok" if v <= rule["ok"] else ("warn" if v <= rule["warn"] else "crit")


LEVEL_COLOR = {"ok": GREEN, "warn": AMBER, "crit": ACCENT, "none": GREY}


# ═══════════════════════════════════════════════════════════════════
# ДАННЫЕ
# ═══════════════════════════════════════════════════════════════════

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
def load_market_map() -> pd.DataFrame:
    """Код рынка → канал и страна, из справочника.

    Раньше страна выводилась из самого кода: у Amazon код и есть страна,
    а всё, что не равно "LM", считалось Amazon. С появлением ManoMano и
    Carrefour это ломается дважды — селектор начинает предлагать MM_ES как
    страну, а выбор Испании не подтягивает испанские продажи этих площадок.

    Берём через v_marketplaces: код там уже приведён к верхнему регистру,
    иначе джойн со витриной не сматчился бы. SELECT * потому, что состав
    колонок вью может отличаться, и жёсткий список сломал бы загрузку
    целиком из-за одного отсутствующего поля."""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM kabinet_data.v_marketplaces", conn)
    except Exception:
        return pd.DataFrame(columns=["marketplace_code", "channel", "country"])
    finally:
        conn.close()
    if df.empty or not {"marketplace_code", "channel"} <= set(df.columns):
        return pd.DataFrame(columns=["marketplace_code", "channel", "country"])
    out = pd.DataFrame({
        "marketplace_code": df["marketplace_code"].astype(str).str.strip().str.upper(),
        "channel": df["channel"].astype(str).str.strip(),
        "country": (df["country"].astype(str).str.strip().str.upper()
                    if "country" in df.columns else ""),
    })
    return out[out["channel"].ne("") & out["channel"].ne("None")].drop_duplicates()


@st.cache_data(ttl=600)
def load_marketplaces() -> list:
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT DISTINCT marketplace
            FROM kabinet_data.economics_summary
            WHERE marketplace IS NOT NULL
            ORDER BY 1
        """, conn)
    finally:
        conn.close()
    return df["marketplace"].tolist()


@st.cache_data(ttl=600)
def load_sales(days: int, d_from: str = "", d_to: str = "") -> pd.DataFrame:
    """Продажи по площадкам за период, SKU нормализован до базового кода.
    Даты передаются строками — так результат кешируется корректно."""
    where = (f"sales_date BETWEEN '{d_from}' AND '{d_to}'" if d_from
             else f"sales_date >= CURRENT_DATE - INTERVAL '{days} days'")
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT SUBSTRING(norm_sku FROM '([0-9]{{5,}})') AS base_sku,
                   marketplace,
                   MAX(product_name)                    AS product_name,
                   SUM(units_ordered)                   AS units,
                   SUM(ordered_product_sales)           AS revenue,
                   SUM(net_proceeds_total)              AS net_proceeds,
                   SUM(total_fees)                      AS fees,
                   SUM(COALESCE(cogs, 0) * units_ordered) AS cogs_total
            FROM kabinet_data.economics_summary
            WHERE {where}
              AND SUBSTRING(norm_sku FROM '([0-9]{{5,}})') IS NOT NULL
            GROUP BY 1, 2
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_stock() -> pd.DataFrame:
    """Остатки: физический товар и квоты каналов раздельно."""
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT SUBSTRING(sku FROM '([0-9]{5,})') AS base_sku,
                   source,
                   availability_status,
                   location,
                   warehouse_name,
                   SUM(quantity) AS qty
            FROM kabinet_data.stock_local
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM kabinet_data.stock_local)
              AND SUBSTRING(sku FROM '([0-9]{5,})') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        """, conn)
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_lm_health(days: int, d_from: str = "", d_to: str = "") -> pd.DataFrame:
    """Показатели канала. Берём все колонки — состав таблицы может меняться."""
    conn = get_connection()
    try:
        where = (f"calc_date BETWEEN '{d_from}' AND '{d_to}'" if d_from
                 else f"calc_date >= CURRENT_DATE - INTERVAL '{days} days'")
        df = pd.read_sql(f"""
            SELECT *
            FROM kabinet_data.lm_health_daily
            WHERE {where}
            ORDER BY calc_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    # недостающие показатели добавляем пустыми, чтобы страница не падала
    for col in ("orders_total", "acceptance_rate_pct", "avg_acceptance_h",
                "p90_acceptance_h", "tracking_rate_pct", "on_time_ship_pct",
                "incident_rate_pct", "open_incidents", "waiting_acceptance"):
        if col not in df.columns:
            df[col] = np.nan
    return df


@st.cache_data(ttl=600)
def load_lm_open_orders() -> pd.DataFrame:
    """Заказы Leroy Merlin, ожидающие акцепта. Может отсутствовать — проверяем."""
    if not table_exists("raw_lm_orders"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT order_id,
                   created_date,
                   order_state,
                   total_price,
                   ROUND(EXTRACT(EPOCH FROM (NOW() - created_date)) / 3600.0, 1) AS hours_open
            FROM kabinet_data.raw_lm_orders
            WHERE order_state IN ('WAITING_ACCEPTANCE', 'WAITING_DEBIT')
            ORDER BY created_date
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT incident_type, severity, sku, warehouse_name,
                   message, source, created_at,
                   DATE_PART('day', NOW() - created_at)::int AS days_open
            FROM kabinet_data.incidents
            WHERE status = 'open'
            ORDER BY created_at
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_returns(days: int, d_from: str = "", d_to: str = "") -> pd.DataFrame:
    """Возвраты за период. SKU нормализуем до базового кода, как везде."""
    if not table_exists("raw_amazon_returns"):
        return pd.DataFrame()
    where = (f"return_date BETWEEN '{d_from}' AND '{d_to}'" if d_from
             else f"return_date >= CURRENT_DATE - INTERVAL '{days} days'")
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT SUBSTRING(sku FROM '([0-9]{{5,}})') AS base_sku,
                   marketplace,
                   return_date,
                   COALESCE(NULLIF(return_reason, ''), '—') AS reason,
                   fulfillment_type,
                   MAX(product_name)      AS product_name,
                   SUM(quantity)          AS qty,
                   SUM(refunded_amount)   AS refunded
            FROM kabinet_data.raw_amazon_returns
            WHERE {where}
              AND SUBSTRING(sku FROM '([0-9]{{5,}})') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def _norm(x) -> str:
    """Строка без пробелов и знаков, в нижнем регистре — чтобы «Leroy
    Merlin» и «leroy-merlin» опознавались как одно и то же."""
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def fmt_money(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €"


# ═══════════════════════════════════════════════════════════════════
# ФИЛЬТРЫ
# ═══════════════════════════════════════════════════════════════════

all_mp = load_marketplaces()

# страну берём из справочника, а не из кода рынка: код MM_ES — это не
# страна, и в списке стран ему делать нечего
_mkt = load_market_map()
_code2country = {}
_code2channel = {}
if not _mkt.empty:
    _code2channel = dict(zip(_mkt["marketplace_code"], _mkt["channel"]))
    _code2country = {c: v for c, v in zip(_mkt["marketplace_code"], _mkt["country"])
                     if v}

if _code2country:
    countries = sorted({_code2country.get(str(m).upper(), "")
                        for m in all_mp} - {""})
else:
    # справочник недоступен — прежнее поведение, а не пустой список
    countries = sorted({m for m in all_mp if m != LM_CODE})

f1, f2 = st.columns([2, 3])
with f1:
    country = st.selectbox(
        t("cm.filter.country"),
        [t("cm.filter.all_countries")] + countries,
        index=(countries.index(LM_COUNTRY) + 1 if LM_COUNTRY in countries else 0),
    )
# набор периодов и память о выборе — общие для Кабинета, см. period.py
PERIOD = period_mod.control(columns=(f2, f2))
period = PERIOD.choice
DAYS = PERIOD.days
date_from, date_to = PERIOD.d_from, PERIOD.d_to

# для произвольного диапазона грузим от его начала, а не за последние N дней
D_FROM = date_from.strftime("%Y-%m-%d") if date_from is not None else ""
D_TO = date_to.strftime("%Y-%m-%d") if date_to is not None else ""
D_FROM_H = date_from.strftime("%d.%m") if date_from is not None else ""
D_TO_H = date_to.strftime("%d.%m.%Y") if date_to is not None else ""

is_all = country == t("cm.filter.all_countries")
# выбранная страна тянет за собой все площадки, работающие в ней: Испания
# это и Amazon.es, и Leroy Merlin, и ManoMano, и Carrefour. Раньше список
# был жёстким и знал только про LM, поэтому испанские продажи новых
# площадок в выборку не попадали
if is_all:
    mp_scope = all_mp
elif _code2country:
    mp_scope = [m for m in all_mp
                if _code2country.get(str(m).upper(), "") == country]
else:
    mp_scope = [country, LM_CODE] if country == LM_COUNTRY else [country]

sales = load_sales(DAYS, D_FROM, D_TO)
stock = load_stock()

st.markdown(f"""
<div style="border:1px solid rgba(128,128,128,0.22); border-left:3px solid {BLUE};
            border-radius:10px; padding:12px 18px; margin:14px 0 4px 0;
            background:rgba(31,119,180,0.045);">
  <div style="font-size:0.72rem; font-weight:700; letter-spacing:.06em;
              text-transform:uppercase; color:{BLUE}; margin-bottom:4px;">
    {t("cm.intro.title")}</div>
  <div style="font-size:0.93rem; line-height:1.55;">{t("cm.intro.body")}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

tab_sum, tab_par, tab_lm, tab_amz, tab_all = st.tabs(
    [t("cm.tab.summary"), t("cm.tab.parity"), t("cm.tab.lm_health"),
     t("cm.tab.amazon_health"), t("cm.tab.all_countries")]
)


# Каналы в евро, в порядке убывания значимости рынка. Список явный:
# в таблице рядом лежат min_price, max_price и прочие числовые поля,
# и «всё числовое, кроме служебного» однажды прихватило бы их
PARITY_EUR = ("amz_es", "amz_fr", "amz_de", "amz_it",
              "mm_es", "mm_fr", "lm_es", "cf_es")
# Британия в фунтах: в сравнение не идёт, но и прятать цену незачем —
# показываем последней колонкой и с другим знаком валюты
PARITY_GBP = "amz_gb"
PARITY_ALERT = 20.0     # с какого разброса подсвечиваем
PARITY_BAD = 50.0       # и с какого он перестаёт быть недосмотром

PARITY_NEED = ("norm_sku", "product_name", "max_deviation_pct",
               "channels_count", "outlier_channels")


@st.cache_data(ttl=600)
def load_price_parity() -> tuple:
    """Цены по каналам и рынкам. Возвращает данные и текст ошибки.

    Ошибку отдаём наружу, а не глотаем: пустой ответ на экране
    неотличим от «загрузчик не отработал», и мы этот урок уже проходили
    на таблицах AMC."""
    conn = get_connection()
    try:
        return pd.read_sql(
            "SELECT * FROM kabinet_data.price_parity", conn), ""
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}".strip()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# СВОД ПО ТОВАРАМ: AMAZON ПРОТИВ LEROY MERLIN
# ═══════════════════════════════════════════════════════════════════

with tab_sum:
    scoped = sales[sales["marketplace"].isin(mp_scope)].copy()

    if scoped.empty:
        st.info(t("common.no_data"))
    else:
        # Канал строки берём из справочника, а не сравнением кода с
        # литералом: у одного канала бывает несколько стран, а список
        # каналов меняется без нас
        scoped["channel"] = scoped["marketplace"].map(
            lambda m: _code2channel.get(str(m).upper(), DEFAULT_CHANNEL))
        # Колонки идут по убыванию выручки: крупный канал слева, где на
        # него смотрят. Порядок считается по данным, а не задан списком
        chans = (scoped.groupby("channel")["revenue"].sum()
                       .sort_values(ascending=False).index.tolist())
        # Внутренние имена колонок — по номеру канала: в названии канала
        # бывают пробелы и точки, а pivot из них делает ключи
        slug = {ch: f"c{i}" for i, ch in enumerate(chans)}

        agg = (scoped.groupby(["base_sku", "channel"], as_index=False)
                     .agg(product_name=("product_name", "first"),
                          units=("units", "sum"), revenue=("revenue", "sum"),
                          net=("net_proceeds", "sum"), cogs=("cogs_total", "sum")))
        agg["avg_price"] = np.round(safe_div(agg["revenue"], agg["units"]), 2)

        wide = agg.pivot(index="base_sku", columns="channel",
                         values=["units", "revenue", "avg_price", "net"])
        wide.columns = [f"{a}_{slug.get(b, b)}" for a, b in wide.columns]
        wide = wide.reset_index()
        # Ноль ставим только там, где он означает «не продавалось».
        # Цену не заполняем: неизвестная цена и цена ноль — разные вещи,
        # и от этого зависит расхождение ниже
        for ch in chans:
            for pref in ("units", "revenue", "net"):
                col = f"{pref}_{slug[ch]}"
                if col in wide.columns:
                    wide[col] = wide[col].fillna(0)

        names = (agg.sort_values("revenue", ascending=False)
                    .drop_duplicates("base_sku").set_index("base_sku")["product_name"])
        wide["product_name"] = wide["base_sku"].map(names).fillna("—")

        # ---- остатки ----
        # Физический склад есть только у FBA. У площадок Mirakl остаток —
        # это квота, выставленная на канал из того же местного склада:
        # складывать её с амазоновской нельзя и между каналами тоже,
        # один и тот же товар выставлен на каждую витрину целиком
        stock_k = stock.copy()
        stock_k["base_sku"] = stock_k["base_sku"].astype(str).str.strip()
        wide["base_sku"] = wide["base_sku"].astype(str).str.strip()

        phys = (stock_k[stock_k["availability_status"] == "available"]
                .groupby("base_sku", as_index=False)["qty"].sum())
        quota_rows = stock_k[stock_k["source"].astype(str).str.lower()
                             .str.startswith(MIRAKL_SRC)]
        # В stock_local нет колонки канала — есть source, location и
        # warehouse_name. Пробуем узнать канал по ним; если хоть одна
        # строка квоты не опознана, раскладывать по каналам наугад не
        # станем — покажем одну общую колонку и скажем об этом подписью
        quota_ch, quota_split = {}, False
        if not quota_rows.empty:
            _tag = (quota_rows["source"].astype(str) + " "
                    + quota_rows["location"].astype(str) + " "
                    + quota_rows["warehouse_name"].astype(str)).map(_norm)
            _hit = pd.Series(pd.NA, index=quota_rows.index, dtype="object")
            # FBA в опознание не берём: строка квоты, чей склад назвали
            # словом «amazon», ушла бы в канал, у которого остаток и так
            # берётся из физического склада, — и просто исчезла бы
            for ch in (c for c in chans if c != FBA_CHANNEL):
                _n = _norm(ch)
                if _n:
                    _hit = _hit.mask(_tag.str.contains(_n, na=False), ch)
            quota_split = _hit.notna().all()
            if quota_split:
                for ch, grp in quota_rows.assign(ch=_hit).groupby("ch"):
                    quota_ch[ch] = (grp.groupby("base_sku", as_index=False)["qty"]
                                       .sum().rename(columns={"qty": "v"}))
            else:
                quota_ch[None] = (quota_rows.groupby("base_sku", as_index=False)["qty"]
                                            .sum().rename(columns={"qty": "v"}))

        stock_cols, quota_cols = [], []
        for ch in chans:
            col = f"stock_{slug[ch]}"
            src = (phys.rename(columns={"qty": "v"}) if ch == FBA_CHANNEL
                   else (quota_ch.get(ch) if quota_split else None))
            if src is None:
                continue
            wide = wide.merge(src.rename(columns={"v": col}), on="base_sku",
                              how="left")
            wide[col] = wide[col].fillna(0)
            stock_cols.append(col)
            if ch != FBA_CHANNEL:
                quota_cols.append(col)
        # Квота, которую по каналам не разложить, показывается ОДНОЙ
        # колонкой в конце. Скопировать её в колонку каждого канала было
        # бы хуже прочерка: одинаковые числа под ManoMano и Carrefour
        # читаются как «на обеих витринах свой запас», а это одна и та же
        # строка склада
        shared_quota = None
        if quota_ch.get(None) is not None:
            shared_quota = "stock_shared"
            wide = wide.merge(
                quota_ch[None].rename(columns={"v": shared_quota}),
                on="base_sku", how="left")
            wide[shared_quota] = wide[shared_quota].fillna(0)

        # ---- возвраты ----
        rets_all = load_returns(DAYS, D_FROM, D_TO)
        if not rets_all.empty:
            rq = (rets_all[rets_all["marketplace"].isin(mp_scope)]
                  .groupby("base_sku", as_index=False)["qty"].sum()
                  .rename(columns={"qty": "returns_qty"}))
            wide = wide.merge(rq, on="base_sku", how="left")
        if "returns_qty" not in wide.columns:
            wide["returns_qty"] = 0
        wide["returns_qty"] = wide["returns_qty"].fillna(0)

        unit_cols = [f"units_{slug[ch]}" for ch in chans]
        rev_cols = [f"revenue_{slug[ch]}" for ch in chans]
        price_cols = [f"avg_price_{slug[ch]}" for ch in chans]
        sold_total = wide[unit_cols].sum(axis=1)
        wide["returns_pct"] = np.where(
            sold_total > 0,
            np.round(wide["returns_qty"] / sold_total * 100, 1), np.nan)
        wide["returns_alert"] = wide["returns_pct"] > 15

        # ---- расхождение цен ----
        # Считаем размах между каналами, где цена известна: с четырьмя
        # каналами «выше или ниже Amazon» больше не отвечает на вопрос,
        # а разброс отвечает. Цена известна на одном канале — сравнивать
        # не с чем, и там прочерк: ноль читался бы как «цены сошлись»
        _pr = wide[price_cols].where(wide[price_cols] > 0)
        _known = _pr.notna().sum(axis=1)
        _lo, _hi = _pr.min(axis=1), _pr.max(axis=1)
        wide["price_gap_pct"] = np.where(
            _known >= 2, np.round((_hi - _lo) / _lo.replace(0, np.nan) * 100, 1),
            np.nan)
        wide["price_gap_pct"] = pd.to_numeric(wide["price_gap_pct"],
                                              errors="coerce")
        wide["price_alert"] = wide["price_gap_pct"] > 10

        wide["revenue_total"] = wide[rev_cols].sum(axis=1)
        wide = wide.sort_values("revenue_total", ascending=False)

        # ---- сводка ----
        st.markdown(f"**{t('cm.kpi.revenue_by_channel')}**")
        kc = st.columns(max(len(chans), 1))
        for i, ch in enumerate(chans):
            kc[i].metric(ch, fmt_money(wide[f"revenue_{slug[ch]}"].sum()),
                         help=t("cm.kpi.revenue_ch_help"))
        k1, k2, k3 = st.columns(3)
        k1.metric(t("cm.kpi.skus"), f"{len(wide):,}")
        k2.metric(t("cm.kpi.price_alerts"), f"{int(wide['price_alert'].sum()):,}",
                  help=t("cm.kpi.price_alerts_help"))
        k3.metric(t("cm.kpi.return_alerts"), f"{int(wide['returns_alert'].sum()):,}",
                  help=t("cm.kpi.return_alerts_help"))

        fl1, fl2, fl3 = st.columns([1, 1, 2])
        with fl1:
            only_alerts = st.toggle(t("cm.summary.only_alerts"), value=False)
        with fl2:
            only_returns = st.toggle(t("cm.summary.only_returns"), value=False)
        with fl3:
            _q = st.text_input(t("cm.summary.search"),
                               placeholder=t("cm.summary.search_ph"),
                               key="cm_search").strip()

        _total_all = len(wide)
        view = wide
        # Поиск идёт по артикулу и по ASIN сразу: человек не знает заранее,
        # что у него в буфере, и выбирать вид кода перед вводом — лишний шаг
        if _q:
            _amap = catalog.asin_by_sku()
            _sk = view["base_sku"].astype(str)
            view = view[_sk.str.contains(_q, case=False, na=False)
                        | _sk.map(_amap).fillna("")
                            .str.contains(_q, case=False, na=False)]
        _found = len(view)
        if only_alerts:
            view = view[view["price_alert"]]
        if only_returns:
            view = view[view["returns_alert"]]

        if view.empty:
            # Пустой поиск и пустой список тревог — разные вещи. «Тревог
            # нет» на несуществующий артикул читается как «с товаром всё
            # хорошо», хотя товара просто не нашли
            if _q and _found == 0:
                st.info(t("cm.summary.search_none", q=_q))
            else:
                st.success(t("cm.summary.no_alerts"))
        else:
            # ASIN в economics_summary нет — добираем по артикулу.
            # Рынок для домена берём тот, где выручка канала больше, а из
            # него первый амазоновский: Mirakl-канал домена не имеет
            view = view.copy()
            _mk = (scoped.sort_values("revenue", ascending=False)
                         .drop_duplicates("base_sku")
                         .set_index("base_sku")["marketplace"])
            view["asin_url"] = catalog.url_series(
                skus=view["base_sku"], markets=view["base_sku"].map(_mk))
            view["photo"] = catalog.image_series(
                skus=view["base_sku"], markets=view["base_sku"].map(_mk))
            show, conf = ["photo", "base_sku", "asin_url", "product_name"], {
                "photo": catalog.image_column(),
                "base_sku": st.column_config.TextColumn("SKU", width="small"),
                "asin_url": catalog.asin_column(),
                "product_name": st.column_config.TextColumn(
                    t("cm.col.product"), width="medium"),
            }
            for ch in chans:
                u, r = f"units_{slug[ch]}", f"revenue_{slug[ch]}"
                p, k = f"avg_price_{slug[ch]}", f"stock_{slug[ch]}"
                show += [u, r, p]
                conf[u] = st.column_config.NumberColumn(
                    t("cm.col.ch_units", ch=ch), width="small")
                conf[r] = st.column_config.NumberColumn(
                    t("cm.col.ch_revenue", ch=ch), format="%.0f €")
                conf[p] = st.column_config.NumberColumn(
                    t("cm.col.ch_price", ch=ch), format="%.2f €",
                    help=t("cm.col.ch_price_help"))
                if k in stock_cols:
                    show.append(k)
                    _quota = k in quota_cols
                    conf[k] = st.column_config.NumberColumn(
                        t("cm.col.ch_quota" if _quota
                          else "cm.col.ch_stock").format(ch=ch), width="small",
                        help=t("cm.col.ch_quota_help" if _quota
                               else "cm.col.ch_stock_help"))
            if shared_quota:
                show.append(shared_quota)
                conf[shared_quota] = st.column_config.NumberColumn(
                    t("cm.col.quota_shared"), width="small",
                    help=t("cm.col.quota_shared_help"))
            show += ["price_gap_pct", "returns_pct"]
            conf["price_gap_pct"] = st.column_config.NumberColumn(
                t("cm.col.price_gap"), format="%.1f%%",
                help=t("cm.col.price_gap_help"))
            conf["returns_pct"] = st.column_config.NumberColumn(
                t("cm.col.returns_pct"), format="%.0f%%",
                help=t("cm.col.returns_pct_help"))

            st.dataframe(view[show], use_container_width=True, height=560,
                         hide_index=True, column_config=conf)
            st.caption(t("cm.summary.shown", 
                n=len(view), total=_total_all))
            st.caption(t("cm.summary.note"))
            if quota_rows.empty:
                st.caption(t("cm.summary.quota_none"))
            elif not quota_split:
                st.caption(t("cm.summary.quota_merged"))

            st.download_button(
                t("cm.download"),
                view[show].to_csv(index=False).encode("utf-8-sig"),
                file_name="cm_summary.csv", mime="text/csv", key="dl_cm_sum")


# ═══════════════════════════════════════════════════════════════════
# ПАРИТЕТ ЦЕН
# ═══════════════════════════════════════════════════════════════════

with tab_par:
    par, par_err = load_price_parity()
    _miss = [c for c in PARITY_NEED if c not in par.columns] if not par.empty else []
    if par.empty:
        st.error(t("cm.par.no_data", e=par_err or "—"))
    elif _miss:
        st.error(t("cm.par.no_columns", miss=", ".join(_miss),
                   have=", ".join(map(str, par.columns)) or "—"))
    else:
        P = par.copy()
        _eur = [c for c in PARITY_EUR if c in P.columns]
        for c in _eur + [PARITY_GBP, "max_deviation_pct", "channels_count"]:
            if c in P.columns:
                P[c] = pd.to_numeric(P[c], errors="coerce")
        # Отклонение считает загрузчик — берём готовое, а не пересчитываем.
        # Свой расчёт рядом с чужим однажды разойдётся, и разбираться,
        # какое из двух чисел верное, придётся в самый неподходящий момент
        P["spread"] = P["max_deviation_pct"]
        # Цена на одном канале — не паритет ноль, а отсутствие ответа
        P = P[P["channels_count"].fillna(0) >= 2]
        P = P.sort_values("spread", ascending=False)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(t("cm.par.kpi_alert", n=int(PARITY_ALERT)),
                  f"{int((P['spread'] > PARITY_ALERT).sum()):,}",
                  help=t("cm.par.kpi_alert_help"))
        k2.metric(t("cm.par.kpi_bad", n=int(PARITY_BAD)),
                  f"{int((P['spread'] > PARITY_BAD).sum()):,}")
        k3.metric(t("cm.par.kpi_double"),
                  f"{int((P['spread'] > 100).sum()):,}",
                  help=t("cm.par.kpi_double_help"))
        k4.metric(t("cm.par.kpi_avg"),
                  "—" if P["spread"].isna().all()
                  else f"{P['spread'].mean():.0f} %")

        _q = st.text_input(t("cm.summary.search"),
                           placeholder=t("cm.summary.search_ph"),
                           key="par_search").strip()
        _total = len(P)
        if _q:
            _amap = catalog.asin_by_sku()
            _sk = P["norm_sku"].astype(str)
            P = P[_sk.str.contains(_q, case=False, na=False)
                  | _sk.map(_amap).fillna("")
                      .str.contains(_q, case=False, na=False)
                  | P["product_name"].astype(str)
                      .str.contains(_q, case=False, na=False)]
        if P.empty:
            st.info(t("cm.summary.search_none", q=_q))
        else:
            # Подсветку делаем значком, а не фоном ячейки: Styler в
            # st.dataframe не уживается с колонками фото и ссылки, а
            # они на этой странице уже везде
            P["flag"] = np.where(P["spread"] > PARITY_BAD, "🔴",
                                 np.where(P["spread"] > PARITY_ALERT,
                                          "🟡", "·"))
            P["photo"] = catalog.image_series(skus=P["norm_sku"])
            P["asin_url"] = catalog.url_series(skus=P["norm_sku"])
            show = (["flag", "photo", "norm_sku", "asin_url", "product_name"]
                    + _eur + ["spread", "outlier_channels"])
            if PARITY_GBP in P.columns:
                show.append(PARITY_GBP)
            conf = {
                "flag": st.column_config.TextColumn("", width="small"),
                "photo": catalog.image_column(),
                "norm_sku": st.column_config.TextColumn("SKU", width="small"),
                "asin_url": catalog.asin_column(),
                "product_name": st.column_config.TextColumn(
                    t("cm.col.product"), width="medium"),
                "spread": st.column_config.NumberColumn(
                    t("cm.par.col_spread"), format="%.0f%%",
                    help=t("cm.par.col_spread_help")),
                "outlier_channels": st.column_config.TextColumn(
                    t("cm.par.col_outliers"), width="large",
                    help=t("cm.par.col_outliers_help")),
                PARITY_GBP: st.column_config.NumberColumn(
                    "AMZ · GB", format="%.2f £",
                    help=t("cm.par.col_gbp_help")),
            }
            for c in _eur:
                conf[c] = st.column_config.NumberColumn(
                    str(c).upper().replace("_", " · "), format="%.2f €")
            st.dataframe(P[show], use_container_width=True, height=560,
                         hide_index=True, column_config=conf)
            st.caption(t("cm.summary.shown", n=len(P), total=_total))
            st.caption(t("cm.par.note"))
            st.download_button(
                t("cm.download"),
                P[show].to_csv(index=False).encode("utf-8-sig"),
                file_name="price_parity.csv", mime="text/csv",
                key="dl_parity")



# ═══════════════════════════════════════════════════════════════════
# ЗДОРОВЬЕ КАНАЛА LEROY MERLIN
# ═══════════════════════════════════════════════════════════════════

with tab_lm:
    # Вкладка называется каналом, и в строке вкладок это читалось как
    # фильтр по каналу, которому не хватает ManoMano и Carrefour. Это не
    # фильтр: здесь операционное здоровье канала, и выгрузка с приёмкой
    # заказов приходит только по Leroy Merlin
    st.caption(t("cm.lm.scope"))
    if not table_exists("lm_health_daily"):
        st.info(t("cm.lm.no_table"))
    else:
        lm = load_lm_health(DAYS, D_FROM, D_TO)
        if lm.empty:
            st.info(t("common.no_data"))
        else:
            last = lm.iloc[-1]
            st.caption(t("cm.lm.as_of", 
                d=pd.to_datetime(last["calc_date"]).strftime("%d.%m.%Y")))

            # в метриках значение вчерашнее — список заказов актуальнее,
            # поэтому счётчик берём из него
            waiting_now = load_lm_open_orders()
            if not waiting_now.empty:
                last = last.copy()
                last["waiting_acceptance"] = len(waiting_now)

            cards = [
                ("acceptance_rate_pct", t("cm.lm.acceptance"), "{:.0f}%"),
                ("avg_acceptance_h", t("cm.lm.avg_time"), "{:.1f} ч"),
                ("p90_acceptance_h", t("cm.lm.p90_time"), "{:.0f} ч"),
                ("tracking_rate_pct", t("cm.lm.tracking"), "{:.0f}%"),
                ("incident_rate_pct", t("cm.lm.incidents"), "{:.1f}%"),
                ("waiting_acceptance", t("cm.lm.waiting"), "{:.0f}"),
            ]
            cc = st.columns(len(cards))
            for col, (field, label, fmt) in zip(cc, cards):
                val = last.get(field)
                lvl = health_level(field, val)
                shown = "—" if val is None or pd.isna(val) else fmt.format(float(val))
                with col:
                    st.markdown(
                        f'<div style="border:1px solid rgba(128,128,128,0.35);'
                        f'border-left:3px solid {LEVEL_COLOR[lvl]};border-radius:12px;'
                        f'padding:12px 14px;">'
                        f'<div style="font-size:0.72rem;color:var(--text-secondary);'
                        f'margin-bottom:4px;">{label}</div>'
                        f'<div style="font-size:1.5rem;font-weight:500;">{shown}</div>'
                        f'</div>', unsafe_allow_html=True)

            st.markdown("")
            o1, o2, o3 = st.columns(3)
            o1.metric(t("cm.lm.orders"), f"{int(last.get('orders_total') or 0):,}")
            o2.metric(t("cm.lm.on_time"),
                      f"{float(last.get('on_time_ship_pct') or 0):.0f}%")
            o3.metric(t("cm.lm.open_incidents"),
                      f"{int(last.get('open_incidents') or 0):,}")

            st.divider()

            # ---- тренд по дням ----
            st.markdown(f"**{t('cm.lm.trend')}**")
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(name=t("cm.lm.orders"), x=lm["calc_date"],
                                 y=lm["orders_total"], marker_color=BLUE),
                          secondary_y=False)
            fig.add_trace(go.Scatter(name=t("cm.lm.acceptance"), x=lm["calc_date"],
                                     y=lm["acceptance_rate_pct"], mode="lines+markers",
                                     line=dict(color=GREEN, width=2)), secondary_y=True)
            fig.add_trace(go.Scatter(name=t("cm.lm.tracking"), x=lm["calc_date"],
                                     y=lm["tracking_rate_pct"], mode="lines+markers",
                                     line=dict(color=AMBER, width=2, dash="dot")),
                          secondary_y=True)
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                              hovermode="x unified",
                              legend=dict(orientation="h", y=1.14))
            fig.update_yaxes(title_text=t("cm.lm.orders"), secondary_y=False)
            fig.update_yaxes(range=[0, 105], ticksuffix="%", showgrid=False,
                             secondary_y=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

            # ---- заказы, ждущие акцепта ----
            waiting = load_lm_open_orders()
            st.markdown(f"**{t('cm.lm.waiting_title')}**")
            if waiting.empty:
                st.success(t("cm.lm.waiting_none"))
            else:
                waiting["created_date"] = pd.to_datetime(
                    waiting["created_date"]).dt.strftime("%d.%m %H:%M")
                STATE_LABEL = {"WAITING_ACCEPTANCE": t("cm.state.waiting_acceptance"),
                               "WAITING_DEBIT": t("cm.state.waiting_debit")}
                waiting["order_state"] = waiting["order_state"].map(
                    lambda v: STATE_LABEL.get(v, v))
                st.dataframe(
                    waiting[["order_id", "created_date", "order_state",
                             "total_price", "hours_open"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "order_id": st.column_config.TextColumn(
                            t("cm.col.order"), width="medium"),
                        "created_date": st.column_config.TextColumn(
                            t("cm.col.created"), width="small"),
                        "order_state": st.column_config.TextColumn(
                            t("cm.col.state"), width="small"),
                        "total_price": st.column_config.NumberColumn(
                            t("cm.col.amount"), format="%.2f €"),
                        "hours_open": st.column_config.NumberColumn(
                            t("cm.col.hours_open"), format="%.0f ч"),
                    },
                )
                st.warning(t("cm.lm.waiting_warn", n=len(waiting)))


# ═══════════════════════════════════════════════════════════════════
# ЗДОРОВЬЕ AMAZON
# ═══════════════════════════════════════════════════════════════════

with tab_amz:
    st.caption(t("cm.amz.scope"))
    inc = load_incidents()

    if inc.empty:
        st.success(t("cm.amz.no_incidents"))
    else:
        # инциденты Leroy Merlin живут в общем журнале — здесь показываем
        # только амазоновские, чтобы вкладки не дублировали друг друга
        inc["source"] = inc["source"].fillna("amazon")
        # в базе коды — на экране человеческие названия
        TYPE_LABEL = {
            "low_stock": t("cm.inc.low_stock"),
            "out_of_stock": t("cm.inc.out_of_stock"),
            "stale_data": t("cm.inc.stale_data"),
            "negative_stock": t("cm.inc.negative_stock"),
            "lm_order_not_accepted": t("cm.inc.lm_not_accepted"),
            "lm_offer_out_of_stock": t("cm.inc.lm_offer_zero"),
            "lm_health_degraded": t("cm.inc.lm_degraded"),
        }
        SEV_LABEL = {"critical": t("cm.sev.critical"), "high": t("cm.sev.high"),
                     "warning": t("cm.sev.warning"), "low": t("cm.sev.low"),
                     "info": t("cm.sev.info")}
        inc["type_label"] = inc["incident_type"].map(
            lambda v: TYPE_LABEL.get(v, v))
        inc["sev_label"] = inc["severity"].map(lambda v: SEV_LABEL.get(v, v))
        amz = inc[~inc["source"].str.contains("leroy|lm", case=False, na=False)].copy()

        a1, a2, a3, a4 = st.columns(4)
        a1.metric(t("cm.amz.open_incidents"), f"{len(amz):,}")
        a2.metric(t("cm.amz.critical"),
                  f"{int((amz['severity'] == 'critical').sum()):,}")
        a3.metric(t("cm.amz.high"),
                  f"{int((amz['severity'] == 'high').sum()):,}")
        a4.metric(t("cm.amz.oldest"),
                  f"{int(amz['days_open'].max()) if len(amz) else 0}",
                  help=t("cm.amz.oldest_help"))

        st.divider()

        # по типу — что именно чаще всего требует внимания
        by_type = (amz.groupby("type_label", as_index=False)
                      .agg(cnt=("type_label", "size"),
                           oldest=("days_open", "max"))
                      .sort_values("cnt", ascending=False))
        fig = px.bar(by_type.sort_values("cnt"), x="cnt", y="type_label",
                     orientation="h", text="cnt",
                     title=t("cm.amz.by_type"),
                     color_discrete_sequence=[ACCENT])
        fig.update_layout(height=max(240, 40 * len(by_type)),
                          xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.markdown(f"**{t('cm.amz.incidents_title')}**")
        view = amz.sort_values("days_open", ascending=False).copy()
        view["created_at"] = pd.to_datetime(view["created_at"]).dt.strftime("%d.%m.%Y")
        view["asin_url"] = catalog.url_series(skus=view["sku"])
        view["photo"] = catalog.image_series(skus=view["sku"])
        st.dataframe(
            view[["photo", "created_at", "days_open", "sev_label",
                  "type_label", "sku", "asin_url", "warehouse_name",
                  "message"]],
            use_container_width=True, height=420, hide_index=True,
            column_config={
                "photo": catalog.image_column(),
                "created_at": st.column_config.TextColumn(
                    t("cm.col.created"), width="small"),
                "asin_url": catalog.asin_column(),
                "days_open": st.column_config.NumberColumn(
                    t("cm.col.days_open"), width="small",
                    help=t("cm.col.days_open_help")),
                "sev_label": st.column_config.TextColumn(
                    t("cm.col.severity"), width="small"),
                "type_label": st.column_config.TextColumn(
                    t("cm.col.type"), width="small"),
                "sku": st.column_config.TextColumn("SKU", width="small"),
                "warehouse_name": st.column_config.TextColumn(
                    t("cm.col.warehouse"), width="medium"),
                "message": st.column_config.TextColumn(
                    t("cm.col.description"), width="large"),
            },
        )
        st.caption(t("cm.amz.incidents_note"))

    # ---- возвраты ----
    rets = load_returns(DAYS, D_FROM, D_TO)
    st.divider()
    st.markdown(f"**{t('cm.amz.returns_title')}**")

    if rets.empty:
        st.info(t("cm.amz.no_returns"))
    else:
        scoped_ret = rets[rets["marketplace"].isin(mp_scope)] if not is_all else rets

        r1, r2, r3 = st.columns(3)
        r1.metric(t("cm.amz.returns"), f"{int(scoped_ret['qty'].sum()):,}",
                  help=(t("cm.amz.returns_range", f=D_FROM_H, to=D_TO_H)
                        if date_from is not None
                        else t("cm.amz.returns_help", d=DAYS)))
        r2.metric(t("cm.amz.refunded"), fmt_money(scoped_ret["refunded"].sum()))
        r3.metric(t("cm.amz.return_skus"), f"{scoped_ret['base_sku'].nunique():,}")

        rc1, rc2 = st.columns([1, 1])
        with rc1:
            top = (scoped_ret.groupby(["base_sku", "product_name"], as_index=False)
                             ["qty"].sum().nlargest(12, "qty"))
            if not top.empty:
                fig = px.bar(top.sort_values("qty"), x="qty", y="base_sku",
                             orientation="h", text="qty",
                             title=t("cm.amz.top_returns"),
                             color_discrete_sequence=[ACCENT])
                fig.update_layout(height=max(280, 28 * len(top)),
                                  xaxis_title=None, yaxis_title=None,
                                  margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        with rc2:
            # причина приходит только по FBA — по остальным Amazon её не отдаёт
            by_reason = (scoped_ret.groupby("reason", as_index=False)["qty"].sum()
                                   .sort_values("qty", ascending=False))
            if not by_reason.empty:
                fig = px.pie(by_reason, names="reason", values="qty", hole=0.5,
                             title=t("cm.amz.by_reason"))
                fig.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
                st.caption(t("cm.amz.reason_note"))


# ═══════════════════════════════════════════════════════════════════
# СВОД ПО ВСЕМ СТРАНАМ
# ═══════════════════════════════════════════════════════════════════

with tab_all:
    if sales.empty:
        st.info(t("common.no_data"))
    else:
        by_mp = (sales.groupby("marketplace", as_index=False)
                      .agg(skus=("base_sku", "nunique"), units=("units", "sum"),
                           revenue=("revenue", "sum"), net=("net_proceeds", "sum"),
                           fees=("fees", "sum"), cogs=("cogs_total", "sum")))
        by_mp["cm"] = by_mp["net"] - by_mp["cogs"]
        by_mp["cm_pct"] = np.round(safe_div(by_mp["cm"], by_mp["revenue"]) * 100, 1)
        by_mp["fees_pct"] = np.round(safe_div(by_mp["fees"], by_mp["revenue"]) * 100, 1)
        # площадку берём из справочника: сравнение с литералом красило
        # любую неамазоновскую площадку в цвета Amazon
        by_mp["platform"] = by_mp["marketplace"].map(
            lambda m: _code2channel.get(str(m).upper(),
                                        t("cm.platform.amazon")))
        by_mp = by_mp.sort_values("revenue", ascending=False)

        cc = st.columns(min(len(by_mp), 5) or 1)
        for i, (_, r) in enumerate(by_mp.iterrows()):
            with cc[i % len(cc)]:
                st.metric(r["marketplace"], fmt_money(r["revenue"]),
                          delta=f"{r['cm_pct']:.0f}%",
                          help=t("cm.all.metric_help"))

        fig = px.bar(by_mp, x="marketplace", y="revenue", color="platform",
                     title=t("cm.all.chart"), text="revenue",
                     color_discrete_sequence=[BLUE, GREEN, AMBER, "#7e57c2",
                                              "#26a69a", "#ef6c00"])
        fig.update_traces(texttemplate="%{text:.0f}")
        fig.update_layout(height=360, xaxis_title=None,
                          yaxis_title="€", margin=dict(l=10, r=10, t=50, b=10),
                          legend=dict(orientation="h", y=1.12, title_text=""))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.dataframe(
            by_mp[["marketplace", "platform", "skus", "units", "revenue",
                   "fees", "fees_pct", "cogs", "cm", "cm_pct"]],
            use_container_width=True, hide_index=True,
            column_config={
                "marketplace": st.column_config.TextColumn(t("cm.col.marketplace")),
                "platform": st.column_config.TextColumn(t("cm.col.platform")),
                "skus": st.column_config.NumberColumn(t("cm.col.skus"), width="small"),
                "units": st.column_config.NumberColumn(t("cm.col.units"), width="small"),
                "revenue": st.column_config.NumberColumn(
                    t("cm.col.revenue"), format="%.0f €"),
                "fees": st.column_config.NumberColumn(
                    t("cm.col.fees"), format="%.0f €"),
                "fees_pct": st.column_config.NumberColumn(
                    t("cm.col.fees_pct"), format="%.0f%%"),
                "cogs": st.column_config.NumberColumn("COGS", format="%.0f €"),
                "cm": st.column_config.NumberColumn(t("cm.col.cm"), format="%.0f €"),
                "cm_pct": st.column_config.NumberColumn(
                    t("cm.col.cm_pct"), format="%.1f%%"),
            },
        )
        st.caption(t("cm.all.note"))
