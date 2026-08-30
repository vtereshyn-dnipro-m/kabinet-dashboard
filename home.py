# home.py — Обзор: сводка для руководителя
import inspect
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-size: 1.6rem; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; }
h1 { margin-bottom: 0.1rem; font-size: 2rem; }
[data-testid="stCaptionContainer"] { margin-top: -0.3rem; }
hr { margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# логотип выводится в сайдбаре через st.logo — второй раз не нужен
st.title(t("home.title"))
st.caption(t("home.subtitle"))

# Как часто Обзор обновляет себя сам и как часто перепроверяется свежесть.
# Плашка устаревания живёт отдельно от остальной страницы: её запрос дешёвый
# (одна таблица), а висеть после того, как загрузчики отработали, она не должна
AUTO_REFRESH_SEC = 300


def _has_fragment_run_every() -> bool:
    """Умеет ли установленный Streamlit перезапускать отдельный фрагмент.
    st.fragment(run_every=...) обновляет только свой кусок страницы и не
    трогает виджеты вокруг — на многостраничном дашборде это важно."""
    frag = getattr(st, "fragment", None)
    if frag is None:
        return False
    try:
        return "run_every" in inspect.signature(frag).parameters
    except (TypeError, ValueError):
        return False


_FRAGMENT_OK = _has_fragment_run_every()

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


def _fragment_every(seconds: int):
    """Декоратор самообновляющегося фрагмента. Если версия Streamlit его не
    поддерживает, возвращает функцию как есть: страница остаётся статичной,
    но рабочей — кнопка «Обновить данные» никуда не девается."""
    if _FRAGMENT_OK:
        return st.fragment(run_every=seconds)
    return lambda fn: fn


def _rerun_app():
    """Полный перезапуск скрипта. Из фрагмента нужен явный scope, иначе
    перезапустится только сам фрагмент, а цифры на странице считаются
    на верхнем уровне и останутся старыми."""
    if _FRAGMENT_OK:
        st.rerun(scope="app")
    else:
        st.rerun()


ACCENT = "#e8484d"
BLUE = "#1f77b4"
AMBER = "#f2b134"
GREEN = "#2e9e5b"
GREY = "#9aa4b2"
PLOTLY_CFG = {"displayModeBar": False}


# ═══════════════════════════════════════════════════════════════════
# ДАННЫЕ — каждый блок независим: нет источника, нет блока
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def load_money(days: int = 30) -> pd.DataFrame:
    if not table_exists("economics_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        # экономику и рекламу агрегируем по отдельности и соединяем уже
        # свёрнутыми — так строки не размножатся, что бы ни лежало в источниках
        return pd.read_sql(f"""
            WITH econ AS (
                SELECT sales_date, marketplace,
                       SUM(units_ordered)                     AS units,
                       SUM(units_refunded)                    AS units_refunded,
                       SUM(net_product_sales)                 AS revenue,
                       SUM(ordered_product_sales)             AS gross_revenue,
                       SUM(net_proceeds_total)                AS net,
                       SUM(COALESCE(cogs, 0) * units_ordered) AS cogs
                FROM kabinet_data.economics_summary
                WHERE sales_date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
                GROUP BY 1, 2
            ),
            ads AS (
                SELECT date AS sales_date, marketplace,
                       SUM(total_spend) AS ads
                FROM kabinet_data.ads_spend
                WHERE date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
                GROUP BY 1, 2
            )
            SELECT e.*, COALESCE(a.ads, 0) AS ads
            FROM econ e
            LEFT JOIN ads a USING (sales_date, marketplace)
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_ordered_sales(days: int = 30) -> pd.DataFrame:
    """Витринная выручка — то же число, что видно в Seller Central.
    С НДС, по дате заказа, отменённые не вычитаются."""
    if not table_exists("sales_traffic_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT snapshot_date AS sales_date, marketplace,
                   ordered_sales, units_ordered
            FROM kabinet_data.sales_traffic_daily
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def coverage_diag() -> dict:
    """Почему свод покрытия пуст: таблицы нет, строк нет или запрос упал.
    Раньше все три случая давали одинаково пустой блок на экране."""
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


@st.cache_data(ttl=300)
def load_coverage() -> pd.DataFrame:
    # фильтр по дате самореферентный: MAX(calc_date) из этой же таблицы,
    # а не CURRENT_DATE. Часовой пояс метки на него не влияет
    if not table_exists("coverage_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT sku, marketplace, coverage_status,
                   realistic_coverage_weeks, first_deficit_week, calc_date
            FROM kabinet_data.coverage_summary
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.coverage_summary)
        """, conn)
    except Exception as e:
        st.session_state["_cov_error"] = f"{type(e).__name__}: {e}"
        return pd.DataFrame()
    finally:
        conn.close()


# ttl=60: инциденты и пульс — сигналы «прямо сейчас», их держат ради
# реакции, а не ради экономии запросов. Остальные загрузчики оставлены
# на своих 300 с: они тянут агрегаты за месяц, там минута роли не играет
@st.cache_data(ttl=60)
def load_incidents() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT incident_type, severity, status, source, created_at,
                   DATE_PART('day', NOW() - created_at)::int AS days_open
            FROM kabinet_data.incidents
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_transfers() -> pd.DataFrame:
    if not table_exists("transfer_recommendations"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT sku, from_location, to_location, transfer_qty, status
            FROM kabinet_data.transfer_recommendations
            WHERE calc_date = (SELECT MAX(calc_date) FROM kabinet_data.transfer_recommendations)
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_reviews(days: int = 30) -> dict:
    """Отправленные запросы и прирост отзывов за период."""
    out = {}
    conn = get_connection()
    try:
        if table_exists("review_request_log"):
            df = pd.read_sql(f"""
                SELECT COUNT(*) FILTER (WHERE status='sent'
                        AND sent_at >= NOW() - INTERVAL '{days} days') AS sent7,
                       MAX(sent_at) FILTER (WHERE status='sent')       AS last_sent
                FROM kabinet_data.review_request_log
            """, conn)
            if not df.empty:
                out["sent7"] = int(df["sent7"].iloc[0] or 0)
                out["last_sent"] = df["last_sent"].iloc[0]
        if table_exists("asin_reviews_daily"):
            # сравниваем только те пары товар×площадка, что есть на обе даты:
            # охват скрапера растёт день ото дня, и общая сумма выросла бы
            # даже без единого нового отзыва
            df = pd.read_sql(f"""
                WITH per_day AS (
                    SELECT snapshot_date, COUNT(*) AS n
                    FROM kabinet_data.asin_reviews_daily
                    WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
                      AND review_count IS NOT NULL
                    GROUP BY 1
                ),
                bounds AS (
                    -- первые дни сбора скрапер охватывал единицы товаров:
                    -- берём начало периода там, где охват стал полным
                    SELECT MIN(snapshot_date) AS d0, MAX(snapshot_date) AS d1
                    FROM per_day
                    WHERE n >= (SELECT MAX(n) * 0.5 FROM per_day)
                ),
                pairs AS (
                    SELECT a.asin, a.marketplace,
                           MAX(CASE WHEN a.snapshot_date = b.d0
                                    THEN a.review_count END) AS first_cnt,
                           MAX(CASE WHEN a.snapshot_date = b.d1
                                    THEN a.review_count END) AS last_cnt
                    FROM kabinet_data.asin_reviews_daily a
                    CROSS JOIN bounds b
                    WHERE a.review_count IS NOT NULL
                      AND a.snapshot_date IN (b.d0, b.d1)
                    GROUP BY a.asin, a.marketplace
                )
                SELECT SUM(last_cnt - first_cnt) AS growth,
                       SUM(last_cnt)             AS total,
                       COUNT(*)                  AS pairs
                FROM pairs
                WHERE first_cnt IS NOT NULL AND last_cnt IS NOT NULL
                  AND last_cnt >= first_cnt
            """, conn)
            if not df.empty and pd.notna(df["growth"].iloc[0]):
                out["reviews_growth"] = int(df["growth"].iloc[0])
                out["reviews_total"] = int(df["total"].iloc[0] or 0)
                out["reviews_pairs"] = int(df["pairs"].iloc[0] or 0)
    except Exception:
        pass
    finally:
        conn.close()
    return out


@st.cache_data(ttl=600)
def load_channels() -> pd.DataFrame:
    """Справочник рынков: код рынка и канал, к которому он относится.

    Канал берём из данных, а не из кода. Раньше площадка определялась
    сравнением `marketplace == "LM"`, и каждый новый канал требовал правки
    здесь: столбец `marketplace` в витринах совмещает две разные вещи —
    у Amazon там страна (ES, DE), у остальных площадок код канала.

    Читаем через `v_marketplaces`: вью отдаёт `marketplace_code` уже
    в верхнем регистре и сводит расхождения вроде co.uk и GB. Джойнить
    справочник с витриной напрямую нельзя — регистр кодов не совпадает,
    и джойн молча не сматчится ни по одной строке.

    Берём `SELECT *`: состав колонок вью может отличаться от справочника,
    и жёсткий список полей сломал бы загрузку целиком из-за одной."""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM kabinet_data.v_marketplaces", conn)
    except Exception:
        return pd.DataFrame(columns=["marketplace_code", "channel"])
    finally:
        conn.close()
    if df.empty or not {"marketplace_code", "channel"} <= set(df.columns):
        return pd.DataFrame(columns=["marketplace_code", "channel"])
    out = df[["marketplace_code", "channel"]].copy()
    out["marketplace_code"] = out["marketplace_code"].astype(str).str.strip().str.upper()
    out["channel"] = out["channel"].astype(str).str.strip()
    return out[out["channel"].ne("") & out["channel"].ne("None")].drop_duplicates()


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def fmt_money(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €"


# ═══════════════════════════════════════════════════════════════════
# ЗАГРУЗКА
# ═══════════════════════════════════════════════════════════════════

# период держим в адресе — иначе он сбрасывается при переходе на другую
# страницу и обратно
P_7, P_30, P_90 = "7", "30", "90"
P_MONTH, P_CUSTOM = t("home.period.month"), t("home.period.custom")
_opts = [P_7, P_30, P_90, P_MONTH, P_CUSTOM]

_qp = st.query_params.get("d", P_30)
_default = _qp if _qp in _opts else P_30

pc1, pc2 = st.columns([2, 2])
with pc1:
    period = st.segmented_control(
        t("home.period"), options=_opts, default=_default, key="home_period")
period = period or P_30
if period != _qp:
    st.query_params["d"] = period

today = pd.Timestamp(datetime.now().date())
date_from = date_to = None

if period == P_MONTH:
    date_from = today.replace(day=1)
    date_to = today
    DAYS = (date_to - date_from).days + 1
elif period == P_CUSTOM:
    with pc2:
        picked = st.date_input(
            t("home.period.range"),
            value=(today - pd.Timedelta(days=29), today),
            max_value=today, format="DD.MM.YYYY", key="home_range")
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        date_from, date_to = (pd.Timestamp(picked[0]), pd.Timestamp(picked[1]))
    else:
        date_from = date_to = today
    DAYS = max((date_to - date_from).days + 1, 1)
else:
    DAYS = int(period)

try:
    # для произвольного диапазона грузим с запасом от его начала,
    # чтобы предыдущий период тоже был полным
    _load_days = (DAYS if date_from is None
                  else (today - date_from).days + DAYS + 10)
    money = load_money(_load_days)
    ordered = load_ordered_sales(_load_days)
    # отдельно берём 90 дней: нужно понять, какие страны продавали раньше,
    # но замолчали в выбранном периоде
    money_wide = load_money(90) if DAYS < 90 else money
    cov = load_coverage()
    inc = load_incidents()
    transfers = load_transfers()
    reviews = load_reviews(DAYS)
except Exception as e:
    st.error(f"{t('home.db_error')}: {e}")
    st.stop()



# ═══════════════════════════════════════════════════════════════════
# ПРОДАЖИ
# ═══════════════════════════════════════════════════════════════════

if date_from is not None:
    _title = t("home.sec.sales_range").format(
        f=date_from.strftime("%d.%m"), to=date_to.strftime("%d.%m.%Y"))
else:
    _title = t("home.sec.sales").format(d=DAYS)
st.markdown(f"##### {_title}")

# «Полный день» — тот, за который пришли и амазоновские отчёты. Финансовые
# отчёты Amazon (комиссии, маржа) отстают на 2-3 дня, а каналы Mirakl
# приходят почти сразу: за свежие дни в economics_summary остаются только
# они. Окно растягивалось на эти дни, и хвост графика проваливался почти
# в ноль — при том что продажи шли в обычном режиме.
#
# Канал берём из справочника, а не перечнем кодов: литеральный список
# протух бы с первой же новой площадкой, как уже протухал «LM»
_full_last = pd.NaT
if not money.empty:
    money["sales_date"] = pd.to_datetime(money["sales_date"])
    _ch = load_channels()
    if not _ch.empty:
        _amz_codes = set(_ch.loc[_ch["channel"].str.upper() == "AMAZON",
                                 "marketplace_code"])
        if _amz_codes:
            _a_days = money.loc[
                money["marketplace"].astype(str).str.strip().str.upper()
                .isin(_amz_codes), "sales_date"]
            if len(_a_days):
                _full_last = _a_days.max()
    if pd.isna(_full_last):
        # справочник недоступен — прежнее поведение, а не пустой экран
        _full_last = money["sales_date"].max()
    money = money[money["sales_date"] <= _full_last]
    if not money_wide.empty:
        money_wide["sales_date"] = pd.to_datetime(money_wide["sales_date"])
        money_wide = money_wide[money_wide["sales_date"] <= _full_last]

# данные о продажах приходят с задержкой в несколько дней — говорим об этом
# прямо, иначе «за 7 дней» читается как «включая вчера»
if not money.empty:
    _last = pd.to_datetime(money["sales_date"]).max()
    _lag = (pd.Timestamp(datetime.now().date()) - _last).days
    if _lag >= 2 and date_from is None:
        _from = (_last - pd.Timedelta(days=DAYS - 1)).strftime("%d.%m")
        st.caption(t("home.sales.lag").format(
            d=_last.strftime("%d.%m"), n=_lag, f=_from))
    elif _lag >= 2 and date_to is not None and date_to > _last:
        st.caption(t("home.sales.lag_range").format(
            d=_last.strftime("%d.%m"), n=_lag))

if money.empty:
    st.caption(t("home.sales.no_data"))
else:
    money["sales_date"] = pd.to_datetime(money["sales_date"])

    if date_from is not None:
        # выбран конкретный диапазон — берём его как есть,
        # предыдущий период той же длины идёт встык перед ним
        cur = money[(money["sales_date"] >= date_from)
                    & (money["sales_date"] <= date_to)]
        prev = money[(money["sales_date"] < date_from)
                     & (money["sales_date"] >= date_from
                        - pd.Timedelta(days=DAYS))]
    else:
        # окно считаем от последней даты с данными, а не от сегодня.
        # Amazon отдаёт отчёты с лагом в несколько дней, и если брать «сегодня
        # минус 7», в текущем окне окажется 4-5 заполненных дней против семи
        # в прошлом — сравнение покажет обвал, которого нет
        anchor = money["sales_date"].max()
        cur = money[money["sales_date"] > anchor - pd.Timedelta(days=DAYS)]
        prev = money[(money["sales_date"] <= anchor - pd.Timedelta(days=DAYS))
                     & (money["sales_date"] > anchor - pd.Timedelta(days=DAYS * 2))]

    rev_cur = float(cur["revenue"].sum())
    rev_prev = float(prev["revenue"].sum())
    _ads = float(cur.get("ads", pd.Series(dtype=float)).sum() or 0)
    cm_cur = float(cur["net"].sum() - cur["cogs"].sum() - _ads)
    cm_pct = round(cm_cur / rev_cur * 100, 1) if rev_cur else 0.0
    units_cur = int(cur["units"].sum())
    delta_pct = (round((rev_cur - rev_prev) / rev_prev * 100, 1)
                 if rev_prev > 0 else None)
    # период неполный или предыдущий пустой — сравнение обманет
    if delta_pct is not None and abs(delta_pct) > 300:
        delta_pct = None

    # витринная выручка за тот же период — то, что видно в Seller Central
    ord_cur = None
    _o_to = _o_from = pd.NaT
    if not ordered.empty:
        ordered["sales_date"] = pd.to_datetime(ordered["sales_date"])
        if date_from is not None:
            _o = ordered[(ordered["sales_date"] >= date_from)
                         & (ordered["sales_date"] <= date_to)]
        else:
            _oa = ordered["sales_date"].max()
            _o = ordered[ordered["sales_date"] > _oa - pd.Timedelta(days=DAYS)]
        ord_cur = float(_o["ordered_sales"].sum())
        # у отчёта заказов лаг меньше, чем у финансовых отчётов, поэтому
        # его окно может заканчиваться позже. Числа рядом за разные дни —
        # повод объяснить, а не молча показать
        if len(_o):
            _o_to = pd.Timestamp(_o["sales_date"].max())
            _o_from = pd.Timestamp(_o["sales_date"].min())
        else:
            _o_to = _o_from = pd.NaT

    _m_to = pd.Timestamp(cur["sales_date"].max()) if len(cur) else pd.NaT
    _m_from = pd.Timestamp(cur["sales_date"].min()) if len(cur) else pd.NaT
    _spans_differ = (pd.notna(_o_to) and pd.notna(_m_to) and _o_to != _m_to)

    s0, s1, s2, s3, s4 = st.columns(5)
    s0.metric(t("home.kpi.ordered"),
              fmt_money(ord_cur) if ord_cur else "—",
              help=(t("home.kpi.ordered_help_span").format(
                        of=_o_from.strftime("%d.%m"), ot=_o_to.strftime("%d.%m"),
                        mf=_m_from.strftime("%d.%m"), mt=_m_to.strftime("%d.%m"))
                    if _spans_differ else t("home.kpi.ordered_help")))
    s1.metric(t("home.kpi.revenue"), fmt_money(rev_cur),
              delta=(f"{delta_pct:+.1f}%" if delta_pct is not None else None),
              help=t("home.kpi.revenue_help").format(d=DAYS))
    s2.metric(t("home.kpi.margin"), f"{cm_cur:,.0f} € · {cm_pct:.0f}%",
              help=t("home.kpi.margin_help"))
    _ref = int(cur.get("units_refunded", pd.Series(dtype=float)).sum() or 0)
    s3.metric(t("home.kpi.units"), f"{units_cur:,}",
              delta=(f"−{_ref} {t('home.kpi.refunded')}" if _ref else None),
              delta_color="inverse" if _ref else "off",
              help=t("home.kpi.units_help"))
    s4.metric(t("home.kpi.markets"), f"{cur['marketplace'].nunique()}")

    gl, gr = st.columns([1.6, 1])

    with gl:
        daily = (cur.groupby("sales_date", as_index=False)["revenue"].sum()
                    .sort_values("sales_date"))
        fig = px.area(daily, x="sales_date", y="revenue",
                      color_discrete_sequence=[BLUE])
        fig.update_layout(height=190, margin=dict(l=0, r=0, t=6, b=0),
                          xaxis_title=None, yaxis_title=None,
                          yaxis=dict(showgrid=False))
        fig.update_traces(line=dict(width=1.5),
                          fillcolor="rgba(31,119,180,0.15)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

    with gr:
        # Канал — это площадка (Amazon, Leroy Merlin, ManoMano, Carrefour),
        # а не страна. Раньше он выводился сравнением с литералом "LM", и
        # каждая новая площадка требовала правки здесь. Теперь берём из
        # справочника — следующая появится сама
        ch_map = load_channels()
        _ch_lookup = dict(zip(ch_map["marketplace_code"], ch_map["channel"]))

        def _channel_of(code) -> str:
            return _ch_lookup.get(str(code or "").strip().upper(),
                                  t("home.sales.channel_other"))

        by_mp = (cur.groupby("marketplace", as_index=False)["revenue"].sum()
                    .sort_values("revenue", ascending=False))
        by_mp["channel"] = by_mp["marketplace"].map(_channel_of)

        by_ch = (by_mp.groupby("channel", as_index=False)["revenue"].sum())

        # канал без продаж за период не прячем: молчащая площадка иначе
        # неотличима от несуществующей, а это разные вещи
        quiet = sorted(set(ch_map["channel"]) - set(by_ch["channel"]))
        if quiet:
            by_ch = pd.concat(
                [by_ch, pd.DataFrame({"channel": quiet, "revenue": 0.0})],
                ignore_index=True)
        by_ch = by_ch.sort_values("revenue", ascending=False)

        # цвет закрепляем за каналом по порядку оборота: список каналов
        # заранее не известен, поэтому палитра циклическая
        PALETTE = [BLUE, GREEN, AMBER, "#7e57c2", "#26a69a", "#ef6c00"]
        color_of = {c: PALETTE[i % len(PALETTE)]
                    for i, c in enumerate(by_ch["channel"])}

        sold_mp = by_mp[by_mp["revenue"] > 0]

        for _, r in by_ch.iterrows():
            share = r["revenue"] / rev_cur * 100 if rev_cur else 0
            codes = sorted(sold_mp.loc[sold_mp["channel"] == r["channel"],
                                       "marketplace"])
            if not codes:
                sub = ""
            elif len(codes) <= 2:
                sub = ", ".join(codes)
            else:
                sub = t("home.sales.n_countries").format(n=len(codes))
            value = (t("home.sales.silent") if r["revenue"] <= 0
                     else f"{r['revenue']:,.0f} €")
            st.markdown(
                f"<div style='margin-bottom:8px'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:0.85rem'><span>{r['channel']} "
                f"<span style='color:var(--text-muted);font-size:0.78rem'>"
                f"{sub}</span></span>"
                f"<b>{value}</b></div>"
                f"<div style='height:6px;border-radius:3px;"
                f"background:rgba(128,128,128,0.18)'>"
                f"<div style='height:6px;border-radius:3px;width:{share:.0f}%;"
                f"background:{color_of[r['channel']]}'></div></div></div>",
                unsafe_allow_html=True)

        # у Amazon страна в коде рынка, у остальных площадок — сам код
        # площадки: подписываем плашки кодом как есть, а группируем цветом
        # по каналу, чтобы «MM_ES» не читался как страна Amazon
        def _chip(label: str, value: float, color: str,
                  muted: bool = False) -> str:
            if muted:
                return (f'<span title="{t("home.sales.silent_hint")}" '
                        f'style="display:inline-block;'
                        f'background:{color}0f;border:1px dashed {color}55;'
                        f'border-radius:6px;padding:3px 9px;margin:0 5px 6px 0;'
                        f'font-size:0.78rem;white-space:nowrap;cursor:help;">'
                        f'<span style="color:var(--text-secondary)">{label}</span>'
                        f'&nbsp;&nbsp;<b style="color:{color}">'
                        f'{t("home.sales.silent")}</b></span>')
            return (f'<span style="display:inline-block;'
                    f'background:{color}14;border:1px solid {color}33;'
                    f'border-radius:6px;padding:3px 9px;margin:0 5px 6px 0;'
                    f'font-size:0.78rem;white-space:nowrap;">'
                    f'<span style="color:var(--text-secondary)">{label}</span>'
                    f'&nbsp;&nbsp;<b style="color:{color}">{value:,.0f} €</b></span>')

        # рынок, который продавал за 90 дней, но молчит в выбранном
        # периоде — это сигнал, а не пустое место
        silent_by_ch = {}
        if not money_wide.empty:
            had = set(money_wide.loc[money_wide["revenue"] > 0, "marketplace"])
            for code in sorted(had - set(sold_mp["marketplace"])):
                silent_by_ch.setdefault(_channel_of(code), []).append(code)

        # плашки идут в том же порядке, что и строки каналов выше
        chips = ""
        for _, r in by_ch.iterrows():
            col = color_of[r["channel"]]
            mine = sold_mp[sold_mp["channel"] == r["channel"]]
            for _, m in mine.sort_values("revenue", ascending=False).iterrows():
                chips += _chip(m["marketplace"], m["revenue"], col)
            for code in silent_by_ch.get(r["channel"], []):
                chips += _chip(code, 0.0, ACCENT, muted=True)

        st.markdown(
            f'<div style="margin-top:6px;line-height:2">{chips}</div>',
            unsafe_allow_html=True)

    if ord_cur and rev_cur:
        st.caption(t("home.sales.two_numbers").format(
            gap=ord_cur - rev_cur, pct=(ord_cur - rev_cur) / ord_cur * 100))
    st.caption(t("home.sales.no_plan"))
    st.page_link("pages/5_Money.py", label=t("home.link.money"),
                 icon=":material/euro:")

st.divider()


# ═══════════════════════════════════════════════════════════════════
# ЗАПАСЫ И ПОКРЫТИЕ
# ═══════════════════════════════════════════════════════════════════

st.markdown(f"##### {t('home.sec.stock')}")
st.caption(t("home.sec.stock_note"))

cl, cr = st.columns([1.4, 1])

with cl:
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
            st.warning(t("cov.err.no_match").format(
                n=d["rows"],
                d=("—" if pd.isna(pd.Timestamp(d["last_calc"]))
                   else pd.Timestamp(d["last_calc"]).strftime("%d.%m.%Y %H:%M"))))
        st.caption(t("home.cov.no_data"))
    else:
        cov["realistic_coverage_weeks"] = pd.to_numeric(
            cov["realistic_coverage_weeks"], errors="coerce")
        n_crit = int((cov["coverage_status"] == "critical").sum())
        n_warn = int((cov["coverage_status"] == "warning").sum())
        n_ok = int((cov["coverage_status"] == "ok").sum())
        total_pairs = len(cov)
        secured = round(n_ok / total_pairs * 100) if total_pairs else 0

        v1, v2, v3 = st.columns(3)
        v1.metric(t("home.kpi.secured"), f"{secured}%",
                  help=t("home.kpi.secured_help"))
        v2.metric(t("home.kpi.deficit_soon"), f"{n_crit:,}",
                  help=t("home.kpi.deficit_soon_help"))
        v3.metric(t("home.kpi.deficit_later"), f"{n_warn:,}",
                  help=t("home.kpi.deficit_later_help"))

        bars = pd.DataFrame({
            "bucket": [t("home.cov.b_crit"), t("home.cov.b_warn"),
                       t("home.cov.b_ok")],
            "n": [n_crit, n_warn, n_ok],
        })
        fig = px.bar(bars, x="n", y="bucket", orientation="h", text="n",
                     color="bucket",
                     color_discrete_map={t("home.cov.b_crit"): ACCENT,
                                         t("home.cov.b_warn"): AMBER,
                                         t("home.cov.b_ok"): GREEN})
        fig.update_layout(height=150, showlegend=False,
                          xaxis_title=None, yaxis_title=None,
                          margin=dict(l=0, r=10, t=6, b=0))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        st.page_link("pages/1_Stock.py", label=t("home.link.coverage"),
                     icon=":material/inventory_2:")

with cr:
    st.markdown(f"**{t('home.sec.reorder')}**")
    if transfers.empty:
        st.caption(t("home.reorder.no_data"))
    else:
        pending = transfers[transfers["status"].isin(["new", "pending"])] \
            if "status" in transfers.columns else transfers
        r1, r2 = st.columns(2)
        r1.metric(t("home.kpi.transfers"), f"{len(pending):,}",
                  help=t("home.kpi.transfers_help"))
        r2.metric(t("home.kpi.transfer_qty"),
                  f"{int(pending['transfer_qty'].sum()):,}")
        st.page_link("pages/4_Reorder.py", label=t("home.link.reorder"),
                     icon=":material/shopping_cart:")

st.divider()


# ═══════════════════════════════════════════════════════════════════
# ИНЦИДЕНТЫ И ОТЗЫВЫ
# ═══════════════════════════════════════════════════════════════════

il, ir = st.columns([1.4, 1])

with il:
    st.markdown(f"##### {t('home.sec.incidents')}")
    if inc.empty:
        st.caption(t("home.inc.no_data"))
    else:
        open_inc = inc[inc["status"].isin(["open", "acknowledged"])]
        n_crit_inc = int((open_inc["severity"].isin(["critical", "high"])).sum())
        oldest = int(open_inc["days_open"].max()) if len(open_inc) else 0

        # снабжение и продажи — два разных потока, смотрят разные люди
        SALES_SRC = open_inc["source"].fillna("").str.contains(
            "leroy|lm|amazon_sales", case=False, na=False)
        n_supply = int((~SALES_SRC).sum())
        n_sales = int(SALES_SRC.sum())

        n1, n2, n3 = st.columns(3)
        n1.metric(t("home.kpi.inc_supply"), f"{n_supply:,}",
                  help=t("home.kpi.inc_supply_help"))
        n2.metric(t("home.kpi.inc_sales"), f"{n_sales:,}",
                  help=t("home.kpi.inc_sales_help"))
        n3.metric(t("home.kpi.inc_oldest"), f"{oldest}",
                  help=t("home.kpi.inc_oldest_help"))

        if len(open_inc):
            TYPE_LABEL = {
                "low_stock": t("home.inc.low_stock"),
                "out_of_stock": t("home.inc.out_of_stock"),
                "stale_data": t("home.inc.stale_data"),
                "negative_stock": t("home.inc.negative_stock"),
                "lm_order_not_accepted": t("home.inc.lm_not_accepted"),
                "lm_offer_out_of_stock": t("home.inc.lm_offer_zero"),
                "lm_health_degraded": t("home.inc.lm_degraded"),
            }
            open_inc = open_inc.copy()
            open_inc["type_label"] = open_inc["incident_type"].map(
                lambda v: TYPE_LABEL.get(v, v))
            by_type = (open_inc.groupby("type_label", as_index=False)
                               .size().rename(columns={"size": "n"})
                               .sort_values("n", ascending=True).tail(5))
            fig = px.bar(by_type, x="n", y="type_label", orientation="h",
                         text="n", color_discrete_sequence=[ACCENT])
            fig.update_layout(height=150, xaxis_title=None, yaxis_title=None,
                              margin=dict(l=0, r=10, t=6, b=0))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        else:
            st.success(t("home.inc.all_clear"))

        st.page_link("pages/2_Incidents.py", label=t("home.link.incidents"),
                     icon=":material/warning:")

with ir:
    st.markdown(f"##### {t('home.sec.reviews')}")
    if not reviews:
        st.caption(t("home.rev.no_data"))
    else:
        q1, q2 = st.columns(2)
        q1.metric(t("home.kpi.requests").format(d=DAYS),
                  f"{reviews.get('sent7', 0):,}",
                  help=t("home.kpi.requests_help").format(d=DAYS))
        growth = reviews.get("reviews_growth")
        q2.metric(t("home.kpi.new_reviews"),
                  f"+{growth:,}" if growth is not None else "—",
                  help=t("home.kpi.new_reviews_help").format(
                      d=DAYS, n=reviews.get("reviews_pairs", 0)))
        if reviews.get("last_sent") is not None:
            ls = pd.to_datetime(reviews["last_sent"])
            hours = (datetime.now(ls.tzinfo) - ls).total_seconds() / 3600
            if hours > 25:
                st.warning(t("home.rev.stopped").format(h=hours))
        st.page_link("pages/7_Reviews.py", label=t("home.link.reviews"),
                     icon=":material/rate_review:")

st.divider()

with st.expander(t("home.how_title")):
    st.markdown(t("home.how_body"))
with st.expander(t("home.roadmap_title")):
    st.markdown(t("home.roadmap_table"))


# ═══════════════════════════════════════════════════════════════════
# АВТООБНОВЛЕНИЕ
# ═══════════════════════════════════════════════════════════════════

# Обзор перечитывает себя раз в пять минут. Только Обзор: это страница,
# на которую смотрят, не трогая, — её держат открытой на втором мониторе.
# На остальных страницах человек работает руками, и перезапуск посреди
# работы сбросил бы выставленные фильтры и поиск.
@_fragment_every(AUTO_REFRESH_SEC)
def _auto_refresh_tick():
    # фрагмент выполняется и при первой отрисовке страницы, поэтому нужна
    # отметка времени: без неё первый же вызов ушёл бы в бесконечный rerun,
    # а после перезапуска — в следующий, и страница залипла бы намертво
    now = time.monotonic()
    last = st.session_state.get("_overview_tick_at")
    if last is None or now - last >= AUTO_REFRESH_SEC:
        st.session_state["_overview_tick_at"] = now
        if last is not None:
            _rerun_app()


if _FRAGMENT_OK:
    _auto_refresh_tick()
elif st_autorefresh is not None:
    # запасной путь для старых версий Streamlit: перезапускает страницу
    # целиком, фильтров на Обзоре нет, терять нечего
    st_autorefresh(interval=AUTO_REFRESH_SEC * 1000, key="overview_autorefresh")
