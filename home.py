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
PULSE_REFRESH_SEC = 30


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
def load_coverage() -> pd.DataFrame:
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
    except Exception:
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


@st.cache_data(ttl=60)
def load_pulse() -> pd.DataFrame:
    """Когда загрузчики последний раз отработали успешно.
    Это внешняя точка контроля: если умрут и сторож, и загрузчики,
    инциденты никто не создаст — но метка перестанет обновляться,
    и человек увидит это здесь."""
    if not table_exists("system_pulse"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql("""
            SELECT job_name, last_success_at,
                   ROUND(EXTRACT(EPOCH FROM (NOW() - last_success_at)) / 3600.0, 1)
                       AS hours_ago
            FROM kabinet_data.system_pulse
            ORDER BY last_success_at
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


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

# состояние системы: если загрузчики встали, все цифры ниже устарели —
# об этом надо знать до того, как их читать.
# Блок вынесен в отдельный фрагмент с минутным интервалом: перечитывается
# только он, остальная страница и выставленный период не трогаются
@_fragment_every(PULSE_REFRESH_SEC)
def render_system_status():
    # Кеш здесь только мешает: интервал фрагмента и есть период опроса, а при
    # ttl=60 момент истечения записи и момент тика разъезжаются — плашка
    # переживала загрузчик на 78 с (замерено), худший случай ttl + интервал.
    # Сбрасываем запись перед чтением: тогда задержку задаёт один интервал
    # фрагмента, а не сумма двух таймеров. Запрос — одна строка из
    # system_pulse, раз в полминуты это ничто.
    # ttl=60 на самой функции оставлен: он страхует от повторного чтения
    # внутри одного прогона скрипта
    load_pulse.clear()
    pulse = load_pulse()
    if pulse.empty:
        return
    stale = pulse[pulse["hours_ago"] > 26]
    if not len(stale):
        return

    msg_col, btn_col = st.columns([6, 1])
    with msg_col:
        if len(stale) == len(pulse):
            st.error(t("home.pulse.down").format(
                h=float(pulse["hours_ago"].min())))
        else:
            st.warning(t("home.pulse.partial").format(
                n=len(stale), jobs=", ".join(stale["job_name"].head(3))))
    with btn_col:
        # ждать минуту, когда уже видно, что загрузчик отработал, незачем
        if st.button(t("home.refresh"), key="btn_refresh_data",
                     help=t("home.refresh_help"), use_container_width=True):
            # только кеш данных: cache_resource держит клиент Databricks,
            # и сбрасывать его — это лишний раунд авторизации на ровном месте
            st.cache_data.clear()
            _rerun_app()


render_system_status()


# ═══════════════════════════════════════════════════════════════════
# ПРОДАЖИ
# ═══════════════════════════════════════════════════════════════════

if date_from is not None:
    _title = t("home.sec.sales_range").format(
        f=date_from.strftime("%d.%m"), to=date_to.strftime("%d.%m.%Y"))
else:
    _title = t("home.sec.sales").format(d=DAYS)
st.markdown(f"##### {_title}")

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
    if not ordered.empty:
        ordered["sales_date"] = pd.to_datetime(ordered["sales_date"])
        if date_from is not None:
            _o = ordered[(ordered["sales_date"] >= date_from)
                         & (ordered["sales_date"] <= date_to)]
        else:
            _oa = ordered["sales_date"].max()
            _o = ordered[ordered["sales_date"] > _oa - pd.Timedelta(days=DAYS)]
        ord_cur = float(_o["ordered_sales"].sum())

    s0, s1, s2, s3, s4 = st.columns(5)
    s0.metric(t("home.kpi.ordered"),
              fmt_money(ord_cur) if ord_cur else "—",
              help=t("home.kpi.ordered_help"))
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
        # Leroy Merlin — отдельная площадка, а не ещё одна страна Amazon:
        # свои комиссии, своя логистика, свой контракт
        by_mp = (cur.groupby("marketplace", as_index=False)["revenue"].sum()
                    .sort_values("revenue", ascending=False))
        by_mp["platform"] = np.where(by_mp["marketplace"] == "LM",
                                     t("home.platform.lm"),
                                     t("home.platform.amazon"))
        # сколько стран стоит за каждой площадкой — чтобы «Leroy Merlin»
        # не выглядел как ещё одна страна рядом с Amazon.
        # считаем только те, где выручка ненулевая: иначе подпись обещает
        # больше стран, чем показано плашками ниже
        countries = (by_mp[by_mp["revenue"] > 0]
                     .groupby("platform")["marketplace"].nunique().to_dict())
        by_pl = by_mp.groupby("platform", as_index=False)["revenue"].sum()

        for _, r in by_pl.iterrows():
            share = r["revenue"] / rev_cur * 100 if rev_cur else 0
            color = GREEN if r["platform"] == t("home.platform.lm") else BLUE
            n_c = countries.get(r["platform"], 0)
            sub = (t("home.sales.n_countries").format(n=n_c)
                   if r["platform"] == t("home.platform.amazon")
                   else t("home.sales.lm_where"))
            st.markdown(
                f"<div style='margin-bottom:8px'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:0.85rem'><span>{r['platform']} "
                f"<span style='color:var(--text-muted);font-size:0.78rem'>"
                f"{sub}</span></span>"
                f"<b>{r['revenue']:,.0f} €</b></div>"
                f"<div style='height:6px;border-radius:3px;"
                f"background:rgba(128,128,128,0.18)'>"
                f"<div style='height:6px;border-radius:3px;width:{share:.0f}%;"
                f"background:{color}'></div></div></div>",
                unsafe_allow_html=True)

        # у Amazon страна в коде маркетплейса, у Leroy Merlin — нет:
        # подписываем обе площадки одинаково, иначе LM читается как страна
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

        # стран немного — показываем все, чтобы не гадать, кто скрыт за «ещё N».
        # Leroy Merlin ставим последним: иначе он вклинивается в середину
        # списка стран Amazon и выглядит как одна из них
        sold = by_mp[by_mp["revenue"] > 0]
        amz = sold[sold["marketplace"] != "LM"]
        lm = sold[sold["marketplace"] == "LM"]

        chips = "".join(_chip(r["marketplace"], r["revenue"], BLUE)
                        for _, r in amz.iterrows())

        # страна, которая продавала за 90 дней, но молчит в выбранном
        # периоде — это сигнал, а не пустое место
        silent = []
        if not money_wide.empty:
            had = set(money_wide.loc[money_wide["revenue"] > 0, "marketplace"])
            silent = sorted(had - set(sold["marketplace"]) - {"LM"})
        for mp in silent:
            chips += _chip(mp, 0.0, ACCENT, muted=True)

        for _, r in lm.iterrows():
            chips += _chip(t("home.platform.lm_short"), r["revenue"], GREEN)

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
