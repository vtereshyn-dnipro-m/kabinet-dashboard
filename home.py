# home.py — Обзор: сводка для руководителя
import inspect
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db.connection import get_connection, data_version
from i18n import init_lang, t, incident_type_label
from util import as_text, data_boundary, day_axis
import period as period_mod
import plan_fact
import ad_ratios
import money_notes as mn
import pbi

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 12px 14px;
}
[data-testid="stMetricValue"] { font-size: clamp(1.05rem, 1.5vw, 1.6rem); }
[data-testid="stMetricLabel"] { font-size: 0.78rem; }
h1 { margin-bottom: 0.1rem; font-size: 2rem; }
[data-testid="stCaptionContainer"] { margin-top: -0.3rem; }
hr { margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# логотип выводится в сайдбаре через st.logo — второй раз не нужен
import data_passport as passport

st.title(t("home.title"))
st.caption(t("home.subtitle"))
# предупреждение наверху: цифры ниже могут опираться на устаревшие данные (26.09.2026)
passport.banner("home")

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
def load_money(days: int = 30, _v: str = "") -> pd.DataFrame:
    if not table_exists("economics_summary"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        # экономику и рекламу агрегируем по отдельности и соединяем уже
        # свёрнутыми — так строки не размножатся, что бы ни лежало в источниках
        # Маржа — только по SKU с загруженной себестоимостью, как в «Деньгах»: COALESCE(cogs, 0)
        # засчитывал выручку 28 SKU без COGS (~7 900 € за 30 дней) в прибыль почти целиком, и Обзор
        # показывал −59 € там, где «Деньги» честно давали −5 697 € (QA 21.09.2026). Поэтому реклама и
        # логистика присоединяются на уровне SKU, а суммы «по известным» считаются рядом с полными
        return pd.read_sql(f"""
            WITH sku AS (
                SELECT e.sales_date, e.marketplace, e.norm_sku, e.units_ordered, e.units_refunded,
                       e.net_product_sales, e.ordered_product_sales, e.net_proceeds_total, e.cogs,
                       COALESCE(a.ads, 0) AS ads, COALESCE(l.packing_cost + l.shipping_cost, 0) AS logistics
                -- строки экономики плюс «рекламные дни» (SKU × день с рекламой без строки экономики, деньги
                -- нулевые): иначе расход в день без продажи не находил строки и в маржу не попадал (05.10.2026)
                FROM kabinet_data.v_economics_with_ad_days e
                -- в маржу идёт SB + SD + ManoMano, а SP — только там, где строки выплаты нет: в остальных
                -- Sponsored Products Amazon уже удержал внутри net_proceeds_total (сверка сентября 05.10.2026 —
                -- до цента на уровне SKU × день); вычитая total_spend, мы считали SP дважды, −5 973 € за сентябрь
                LEFT JOIN (SELECT date, marketplace, norm_sku, margin_ads AS ads FROM kabinet_data.v_ads_spend_margin
                           WHERE date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days') a
                       ON a.date = e.sales_date AND a.marketplace = e.marketplace AND a.norm_sku = e.norm_sku
                LEFT JOIN kabinet_data.economics_logistics l
                       ON l.sales_date = e.sales_date AND l.marketplace = e.marketplace AND l.norm_sku = e.norm_sku
                WHERE e.sales_date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
            )
            , base AS (
            SELECT sales_date, marketplace,
                   SUM(units_ordered)                                        AS units,
                   SUM(units_refunded)                                       AS units_refunded,
                   SUM(net_product_sales)                                    AS revenue,
                   SUM(ordered_product_sales)                                AS gross_revenue,
                   SUM(net_proceeds_total)                                   AS net,
                   SUM(ads)                                                  AS ads,
                   SUM(logistics)                                            AS logistics,
                   SUM(cogs * units_ordered)                                 AS cogs,          -- NULL-строки выпадают сами
                   SUM(CASE WHEN cogs IS NOT NULL THEN net_product_sales END)  AS revenue_known,
                   SUM(CASE WHEN cogs IS NOT NULL THEN net_proceeds_total END) AS net_known,
                   SUM(CASE WHEN cogs IS NOT NULL THEN ads END)               AS ads_known,
                   SUM(CASE WHEN cogs IS NOT NULL THEN logistics END)         AS logistics_known,
                   COUNT(DISTINCT norm_sku) FILTER (WHERE cogs IS NULL AND units_ordered > 0) AS skus_no_cogs
            FROM sku
            GROUP BY 1, 2
            ),
            -- себестоимость годных возвратов (FBA — SELLABLE, Мадрид — годный запас Odoo сразу или с DEF, продажа с DEF в Польшу) возвращается в маржу на дату возврата. Не join'ом к
            -- строкам SKU — в день возврата продажи этого SKU может не быть, — а к дневной сумме рынка; и не
            -- позже последнего дня экономики СВОЕГО рынка, иначе возврат «из завтра» сдвинул бы окно периода.
            -- Граница была общей на все каналы (07.10.2026): ManoMano грузится утром, и FBA-возврат Испании за
            -- день, по которому Amazon ещё не отчитался, давал строку ES за этот день — граница данных уезжала на
            -- день вперёд, и подпись писала «06.10 ещё загружается» вместо «за 06.10 отчёта Amazon ещё нет»
            last_mk AS (SELECT marketplace, MAX(sales_date) AS last_day FROM sku GROUP BY 1),
            credit AS (
                SELECT r.return_date AS sales_date, r.marketplace, SUM(r.cogs_credit)::float AS cogs_credit
                FROM kabinet_data.v_returns_cogs_credit r
                -- рынок без строк экономики в окне не теряет возврат: для него остаётся общая граница
                LEFT JOIN last_mk m ON m.marketplace = r.marketplace
                WHERE r.return_date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
                  AND r.return_date <= COALESCE(m.last_day, (SELECT MAX(sales_date) FROM sku))
                GROUP BY 1, 2
            )
            SELECT COALESCE(b.sales_date, c.sales_date) AS sales_date,
                   COALESCE(b.marketplace, c.marketplace) AS marketplace,
                   b.units, b.units_refunded, b.revenue, b.gross_revenue, b.net, b.ads, b.logistics, b.cogs,
                   b.revenue_known, b.net_known, b.ads_known, b.logistics_known, b.skus_no_cogs,
                   COALESCE(c.cogs_credit, 0) AS cogs_credit
            FROM base b
            FULL JOIN credit c ON c.sales_date = b.sales_date AND c.marketplace = b.marketplace
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_money_pbi(days: int = 30, _v: str = "") -> pd.DataFrame:
    """Цифры как в Power BI (08.10.2026): день × рынок из реплики его витрины (pbi.py). Колонки названы так же,
    как у load_money, чтобы граница периода, окна и графики работали без второй копии кода: revenue — продажи
    без НДС (до возвратов, у Amazon — продажи с НДС, делённые на ставку страны), cp — Contribution Profit."""
    try:
        _to = datetime.now().date()
        df = pbi.load_daily(_to - pd.Timedelta(days=days * 2 + 10).to_pytimedelta(), _to)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.rename(columns={"sales_vat_excl": "revenue"})
    df["gross_revenue"] = df["revenue"]
    # себестоимость в витрине есть у всех строк (пустая там — ноль), поэтому «маржа по части выручки» не бывает
    df["revenue_known"] = df["revenue"]
    df["ads"] = df["spend"]
    df["cogs_credit"] = 0.0
    return df


@st.cache_data(ttl=300)
def load_day_status(_v: str = ""):
    """Граница полных дней и предварительные дни (money_notes.day_status) — по последней загрузке каждого
    канала: день, по которому не прошли все загрузчики, в цифры и сравнение не берём."""
    conn = get_connection()
    try:
        return mn.day_status(conn)
    except Exception:
        return mn.DayStatus(pd.NaT, pd.NaT, 0.0)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_ad_ratios(d_from, d_to, v: str = "") -> dict:
    """ACOS и TACOS за окно маржи — по формулам Дарины (ad_ratios.py). Ошибка чтения не роняет Обзор:
    карточки покажут прочерк, а не ноль."""
    try:
        return ad_ratios.load(d_from, d_to)
    except Exception:
        return {}


@st.cache_data(ttl=300)
def load_plan_month(_v: str = "") -> tuple:   # (строки по маркетплейсам и пулам, порог темпа, текст ошибки или None)
    """План текущего месяца против факта с начала месяца — сырьё для трёх разрезов.

    Всегда текущий календарный месяц, период страницы сюда не передаётся намеренно.
    v_forecast_current — представление, table_exists его не видит; ошибка чтения
    возвращается текстом: «плана нет» и «не смогли прочитать» — разные вещи."""
    conn = get_connection()
    try:
        today = datetime.now().date()
        df = plan_fact.load_month(conn, today)
        thr = pd.read_sql("SELECT value FROM kabinet_data.reorder_params "
                          "WHERE key = 'forecast_pace_threshold_pct'", conn)
        thr = float(thr.iloc[0, 0]) if not thr.empty else 25.0
        return df, thr, None
    except Exception as e:
        return pd.DataFrame(), 25.0, f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        conn.close()


@st.cache_data(ttl=300)
def load_ordered_sales(days: int = 30, _v: str = "") -> pd.DataFrame:
    """Витринная выручка — то же число, что видно в Seller Central.
    С НДС, по дате заказа, отменённые не вычитаются."""
    if not table_exists("sales_traffic_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT snapshot_date AS sales_date, marketplace,
                   ordered_sales, units_ordered
            FROM kabinet_data.v_sales_traffic_daily_eur
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
        """, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


# Каналы, которых в Кабинете пока нет (08.10.2026): оговорка «без … — подключаем» под карточкой продаж по всем каналам
# уходит сама, как только строки канала появятся в v_sales_vat_incl_daily. Узнаём канал по коду рынка.
_PENDING_CHANNELS = (("wallapop", ("WALLAPOP", "WP_", "WLP")), ("site", ("WEB", "SITE")))


@st.cache_data(ttl=3600)
def connected_sales_channels() -> list:
    """Коды рынков, по которым продажи с НДС есть хоть когда-нибудь — не только в окне страницы. У сайта бывают
    недели без заказов, и проверка по окну вернула бы «без сайта — подключаем» к уже подключённому каналу."""
    if not table_exists("v_sales_vat_incl_daily"):
        return []
    conn = get_connection()
    try:
        return pd.read_sql("SELECT DISTINCT upper(marketplace) AS m FROM kabinet_data.v_sales_vat_incl_daily", conn)["m"].tolist()
    except Exception:
        return []
    finally:
        conn.close()


def sales_all_extra(sales_all: pd.DataFrame) -> str:
    """Подпись под «Продажи с НДС, все каналы»: «до возвратов» и, пока Wallapop или сайта нет в данных, —
    «без … — подключаем». Имён людей в подписи нет: источник называем системой (правило 08.10.2026).
    Подключён ли канал — по всей истории продаж, а не по окну страницы (08.10.2026)."""
    codes = connected_sales_channels() or (
        [str(c).upper() for c in sales_all["marketplace"].dropna().unique()]
        if not sales_all.empty and "marketplace" in sales_all else [])
    missing = [k for k, marks in _PENDING_CHANNELS if not any(c.startswith(m) for c in codes for m in marks)]
    out = t("home.kpi.sales_all_extra")
    if missing:
        what = t("home.kpi.sales_all_missing.both") if len(missing) == 2 else t(f"home.kpi.sales_all_missing.{missing[0]}")
        out += " · " + t("home.kpi.sales_all_missing", what=what)
    return out


@st.cache_data(ttl=300)
def load_sales_all_channels(days: int = 30, _v: str = "") -> pd.DataFrame:
    """Продажи с НДС по ВСЕМ каналам по дате заказа, до возвратов — то, что в Power BI называется
    «Revenue VAT Incl» (07.10.2026). Вью v_sales_vat_incl_daily: Amazon — витрина S&T в евро, Mirakl — строки
    заказов с НДС тем же отбором, что в Power BI; Wallapop и сайт (с 08.10.2026) — заказы Odoo из реплики
    raw_odoo_channel_sales (Kabinet - Odoo Channels Loader)."""
    if not table_exists("v_sales_vat_incl_daily"):
        return pd.DataFrame()
    conn = get_connection()
    try:
        return pd.read_sql(f"""
            SELECT date AS sales_date, marketplace, sales_vat_incl
            FROM kabinet_data.v_sales_vat_incl_daily
            WHERE date >= CURRENT_DATE - INTERVAL '{days * 2 + 10} days'
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
@st.cache_data(ttl=600)
def load_incident_titles() -> dict:
    """Названия типов из справочника incident_types — запас для типов без строки в словаре."""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT incident_type, title FROM kabinet_data.incident_types WHERE title IS NOT NULL", conn)
        return dict(zip(df["incident_type"], df["title"]))
    except Exception:
        return {}
    finally:
        conn.close()


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
def load_reviews(d_from, d_to) -> dict:
    """Отправленные запросы и прирост отзывов за ДАТЫ периода (06.10.2026). Раньше блок брал «последние N дней
    от сегодня» и свой период не видел вовсе: при 01.10–06.10 запросы считались за 30.09–06.10, а подпись
    говорила «за 6 дней» рядом с продажами за 5 — веб-агент записал это расхождением."""
    out = {}
    conn = get_connection()
    try:
        if table_exists("review_request_log"):
            df = pd.read_sql(f"""
                SELECT COUNT(*) FILTER (WHERE status='sent'
                        AND (sent_at AT TIME ZONE 'Europe/Kyiv')::date BETWEEN %(f)s AND %(t)s) AS sent7,
                       MAX(sent_at) FILTER (WHERE status='sent')       AS last_sent
                FROM kabinet_data.review_request_log
            """, conn, params={"f": d_from, "t": d_to})
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
                    WHERE snapshot_date BETWEEN %(f)s AND %(t)s
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
                       COUNT(*)                  AS pairs,
                       (SELECT d0 FROM bounds)   AS d0,
                       (SELECT d1 FROM bounds)   AS d1
                FROM pairs
                WHERE first_cnt IS NOT NULL AND last_cnt IS NOT NULL
                  AND last_cnt >= first_cnt
            """, conn, params={"f": d_from, "t": d_to})
            if not df.empty and pd.notna(df["growth"].iloc[0]):
                out["reviews_growth"] = int(df["growth"].iloc[0])
                out["reviews_total"] = int(df["total"].iloc[0] or 0)
                out["reviews_pairs"] = int(df["pairs"].iloc[0] or 0)
                out["d0"], out["d1"] = df["d0"].iloc[0], df["d1"].iloc[0]
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
        # каноничный код справочника (AMZ-ES, LM-ES, MM-FR) — для подписей; в витринах
        # лежит legacy-код (ES, LM, MM_ES), и на экране он читается как страна, а не рынок
        canon = pd.read_sql("SELECT id, code AS label FROM kabinet_data.marketplaces_new", conn)
    except Exception:
        return pd.DataFrame(columns=["marketplace_code", "channel", "label"])
    finally:
        conn.close()
    if df.empty or not {"marketplace_code", "channel"} <= set(df.columns):
        return pd.DataFrame(columns=["marketplace_code", "channel", "label"])
    out = df[["id", "marketplace_code", "channel"]].merge(canon, on="id", how="left")[["marketplace_code", "channel", "label"]]
    out["marketplace_code"] = out["marketplace_code"].astype(str).str.strip().str.upper()
    out["channel"] = out["channel"].astype(str).str.strip()
    out["label"] = out["label"].fillna(out["marketplace_code"])
    return out[out["channel"].ne("") & out["channel"].ne("None")].drop_duplicates()


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


def fmt_money(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.0f} €"


# ═══════════════════════════════════════════════════════════════════
# ЗАГРУЗКА
# ═══════════════════════════════════════════════════════════════════

# период — общий для всего Кабинета: набор, умолчание и память живут в
# period.py, чтобы Обзор и Деньги нельзя было развести по разным окнам
pc1, pc2 = st.columns([2, 2])
PERIOD = period_mod.control(columns=(pc1, pc2))
period = PERIOD.choice
DAYS = PERIOD.days
today = pd.Timestamp(datetime.now().date())
date_from, date_to = PERIOD.d_from, PERIOD.d_to

try:
    # для произвольного диапазона грузим с запасом от его начала,
    # чтобы предыдущий период тоже был полным
    _load_days = (DAYS if date_from is None
                  else (today - date_from).days + DAYS + 10)
    # _v — отметка последней записи: входит в ключ кеша, чтобы Обзор и
    # Деньги обновлялись вместе, а не каждый по своему TTL
    if pbi.OWN_METHOD:
        # наша методика маржи — для будущего документа (pbi.OWN_METHOD)
        money = load_money(_load_days, data_version("economics_summary", "updated_at"))
        ordered = load_ordered_sales(_load_days, data_version("sales_traffic_daily", "loaded_at"))
        sales_all = load_sales_all_channels(_load_days, data_version("sales_traffic_daily", "loaded_at"))
        # отдельно берём 90 дней: нужно понять, какие страны продавали раньше,
        # но замолчали в выбранном периоде
        money_wide = (load_money(90, data_version("economics_summary", "updated_at"))
                      if DAYS < 90 else money)
    else:
        # цифры как в Power BI (08.10.2026): все карточки — из одной реплики его витрины. «Продажи Amazon» и
        # «все каналы» — та же колонка sales_vat_incl, что у карточки Revenue VAT Incl в Power BI
        _vp = data_version("pbi_spiderweb_report", "loaded_at")
        money = load_money_pbi(_load_days, _vp)
        _amz_rows = (money["platform"].astype(str) == "Amazon") if not money.empty else pd.Series(dtype=bool)
        ordered = (money.loc[_amz_rows, ["sales_date", "marketplace", "sales_vat_incl", "units"]]
                   .rename(columns={"sales_vat_incl": "ordered_sales", "units": "units_ordered"})
                   if not money.empty else pd.DataFrame())
        sales_all = (money[["sales_date", "marketplace", "sales_vat_incl"]].copy()
                     if not money.empty else pd.DataFrame())
        money_wide = load_money_pbi(90, _vp) if DAYS < 90 else money
    cov = load_coverage()
    inc = load_incidents()
    transfers = load_transfers()
    # отзывы и запросы — по вчера включительно: сегодняшний день данными не считается (07.10.2026)
    _rev_end = min(PERIOD.end.date(), today.date() - pd.Timedelta(days=1).to_pytimedelta())
    reviews = load_reviews(PERIOD.start.date(), _rev_end)
except Exception as e:
    st.error(f"{t('home.db_error')}: {e}")
    st.stop()



# ═══════════════════════════════════════════════════════════════════
# ПРОДАЖИ
# ═══════════════════════════════════════════════════════════════════

# Граница данных. Правило одно на обе страницы и живёт в
# util.data_boundary: день закрыт, если Amazon отдал отчёт за него хоть
# по одной стране. Держать здесь свою копию нельзя — копии расходятся.
#
# Канал берём из справочника, а не перечнем кодов: литеральный список
# протух бы с первой же новой площадкой, как уже протухал «LM»
_full_last = pd.NaT
_loaded_last = pd.NaT
_dstat = mn.DayStatus(pd.NaT, pd.NaT, 0.0)
_ahead_mk = pd.Series(dtype="datetime64[ns]")
if not money.empty:
    money["sales_date"] = pd.to_datetime(money["sales_date"])
    _ch = load_channels()
    _amz_codes = (set(_ch.loc[_ch["channel"].str.upper() == "AMAZON",
                              "marketplace_code"])
                  if not _ch.empty else set())
    _dstat = load_day_status(data_version("economics_summary", "updated_at"))
    # сегодня по Киеву — по базе (сервер живёт в UTC); сегодняшний день данными не считается никогда
    _today = _dstat.today if pd.notna(_dstat.today) else pd.Timestamp.now(tz="Europe/Kyiv").normalize().tz_localize(None)
    _b = data_boundary(money, "sales_date", "marketplace", _amz_codes, today=_today)
    _full_last, _ahead_mk = _b.last, _b.ahead
    # день, который Amazon ещё догружает, в цифры и сравнение не входит (06.10.2026): экономика за вчера
    # приходит неполной, и неполный день в периоде давал «обвал», которого нет
    _loaded_last = _full_last
    _settled = _dstat.settled
    if pd.notna(_settled) and pd.notna(_full_last) and _settled < _full_last:
        _full_last = _settled
    money = money[money["sales_date"] <= _full_last]
    if not money_wide.empty:
        money_wide["sales_date"] = pd.to_datetime(money_wide["sales_date"])
        money_wide = money_wide[money_wide["sales_date"] <= _full_last]

# Заголовок пишет фактическую границу, а не запрошенную — как на Деньгах.
# «01.09 — 13.09» при данных по 10.09 обещает три дня, которых в цифрах
# ниже нет, и заставляет сверяться с подписью под графиком
if date_from is not None:
    _to_eff = (min(pd.Timestamp(date_to), _full_last) if pd.notna(_full_last)
               else pd.Timestamp(date_to))
    _title = t("home.sec.sales_range", 
        f=date_from.strftime("%d.%m"), to=_to_eff.strftime("%d.%m.%Y"))
else:
    _title = t("home.sec.sales", d=DAYS)
st.markdown(f"##### {_title}")

# часть каналов ушла дальше границы полных дней — говорим об этом над карточками; где кончились данные
# и каких дней ещё нет, говорит одна строка периода под карточками
if not money.empty:
    _last = pd.to_datetime(money["sales_date"]).max()
    if len(_ahead_mk):
        # часть каналов ушла дальше границы — говорим об этом прямо,
        # иначе непонятно, почему период кончается раньше выбранного
        st.caption(t("period.boundary_max", 
            d=_last.strftime("%d.%m"),
            more=", ".join(sorted(_ahead_mk.index)),
            dmax=_ahead_mk.max().strftime("%d.%m")))
    # где кончились данные и каких дней ещё нет — одной строкой периода под карточками (07.10.2026): отдельная
    # подпись здесь говорила то же самое второй раз

if money.empty:
    st.caption(t("home.sales.no_data"))
else:
    money["sales_date"] = pd.to_datetime(money["sales_date"])

    # Сравниваем только одинаковые ПОЛНЫЕ периоды (06.10.2026). Текущий кончается на последнем полном дне
    # (выше: граница и день, который Amazon ещё догружает), прошлый — столько же дней встык перед ним.
    # Раньше прошлый брался той же длины, что ВЫБРАННЫЙ период: 01–05.10 при данных по 04.10 сравнивались
    # четыре дня с пятью — отсюда −38 % «Выручки», из которых настоящего падения около −30 %.
    anchor = money["sales_date"].max()
    if date_from is not None:
        _w = mn.windows(date_from, date_to, anchor)
    else:
        # окно считаем от последней даты с данными, а не от сегодня: Amazon отдаёт отчёты с лагом
        _w = mn.windows(anchor - pd.Timedelta(days=DAYS - 1), anchor, anchor)
    cur = money[(money["sales_date"] >= _w.cur_from) & (money["sales_date"] <= _w.cur_to)]
    prev = money[(money["sales_date"] >= _w.prev_from) & (money["sales_date"] <= _w.prev_to)]

    rev_cur = float(cur["revenue"].sum())
    rev_prev = float(prev["revenue"].sum())
    _ads = float(cur.get("ads", pd.Series(dtype=float)).sum() or 0)
    # тот же периметр, что в «Деньгах»: только строки с себестоимостью; доля выручки без COGS — в подписи
    def _s(col):
        return float(pd.to_numeric(cur.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    if pbi.OWN_METHOD:
        cm_cur = _s("net_known") - _s("cogs") + _s("cogs_credit") - _s("ads_known") - _s("logistics_known")
    else:
        # Contribution Profit Power BI: сумма колонки contribution_profit витрины (= profit − spend в каждой строке)
        cm_cur = _s("cp")
    # доля — к продажам без НДС, как «% Contribution Margin (VAT Excl)» в Power BI
    cm_pct = round(cm_cur / rev_cur * 100, 1) if rev_cur else 0.0
    _rev_known = _s("revenue_known")
    _no_cogs_rev = rev_cur - _rev_known
    units_cur = int(cur["units"].sum())
    # прошлый период без данных хотя бы за один день (раньше начала экономики) — сравнения нет
    _rev_delta = mn.delta_text(rev_cur, rev_prev, _w, prev["sales_date"].nunique())

    # витринная выручка за тот же период — то, что видно в Seller Central
    ord_cur = None
    _ord_delta = None
    _o_to = _o_from = pd.NaT
    if not ordered.empty:
        ordered["sales_date"] = pd.to_datetime(ordered["sales_date"])
        # окно — то же, что у экономики: витрина Amazon есть с 01.2025 (сырьё Дарины), экономика Data Kiosk —
        # с 15.05.2026; на годовом периоде карточка без отсечки показывала 549 тыс. против 256 тыс. «Выручки»
        # и читалась как разрыв в 53 % (QA 21.09.2026). Раньше первого дня экономики витрину не суммируем
        _econ_first = pd.Timestamp(money["sales_date"].min()) if len(money) else pd.NaT
        _econ_anchor = pd.Timestamp(money["sales_date"].max()) if len(money) else ordered["sales_date"].max()
        # те же даты, что у выручки: один и тот же полный период для всех карточек
        _lo = max(_w.cur_from, _econ_first) if pd.notna(_econ_first) else _w.cur_from
        _o = ordered[(ordered["sales_date"] >= _lo) & (ordered["sales_date"] <= _w.cur_to)]
        _o_clipped = date_from is not None and pd.notna(_econ_first) and pd.Timestamp(date_from) < _econ_first
        ord_cur = float(_o["ordered_sales"].sum())
        # прошлый период — те же даты, что у «Выручки»; если текущий урезан первым днём экономики, сравнивать
        # не с чем: окна разной длины дали бы ложный рост
        _op = ordered[(ordered["sales_date"] >= _w.prev_from) & (ordered["sales_date"] <= _w.prev_to)]
        _ord_delta = (None if _o_clipped or (pd.notna(_econ_first) and _w.cur_from < _econ_first) else
                      mn.delta_text(ord_cur, float(_op["ordered_sales"].sum()), _w, _op["sales_date"].nunique()))
        # у отчёта заказов лаг меньше, чем у финансовых отчётов, поэтому
        # его окно может заканчиваться позже. Числа рядом за разные дни —
        # повод объяснить, а не молча показать
        if len(_o):
            _o_to = pd.Timestamp(_o["sales_date"].max())
            _o_from = pd.Timestamp(_o["sales_date"].min())
        else:
            _o_to = _o_from = pd.NaT

    # Продажи с НДС по всем каналам (07.10.2026): то же окно и тот же прошлый период, что у карточки Amazon, —
    # иначе две соседние карточки сравнивали бы разные дни
    all_cur, _all_delta = None, None
    if not sales_all.empty and not ordered.empty:
        sales_all["sales_date"] = pd.to_datetime(sales_all["sales_date"])
        _ac = sales_all[(sales_all["sales_date"] >= _lo) & (sales_all["sales_date"] <= _w.cur_to)]
        _ap = sales_all[(sales_all["sales_date"] >= _w.prev_from) & (sales_all["sales_date"] <= _w.prev_to)]
        all_cur = float(_ac["sales_vat_incl"].sum())
        _all_delta = (None if _o_clipped or (pd.notna(_econ_first) and _w.cur_from < _econ_first) else
                      mn.delta_text(all_cur, float(_ap["sales_vat_incl"].sum()), _w, _ap["sales_date"].nunique()))

    _m_to = pd.Timestamp(cur["sales_date"].max()) if len(cur) else pd.NaT
    _m_from = pd.Timestamp(cur["sales_date"].min()) if len(cur) else pd.NaT
    _spans_differ = (pd.notna(_o_to) and pd.notna(_m_to) and _o_to != _m_to)

    # пять карточек в ряд: шестая («Площадок») уходит во второй ряд к ACOS и TACOS — при шести названия обрезались
    s0, s0b, s1, s2, s3 = st.columns(5)
    # под каждой денежной цифрой — видимая подпись: НДС · каналы · дата (money_notes, 06.10.2026); с 08.10.2026 цифры
    # те же, что в Power BI, и подпись говорит это словами «как в Power BI»
    _pbi = not pbi.OWN_METHOD
    _as = (lambda x: " · ".join(p for p in (x, t("mn.x.as_pbi")) if p)) if _pbi else (lambda x: x)
    mn.money_metric(s0, t("home.kpi.ordered"), fmt_money(ord_cur) if ord_cur else "—", delta=_ord_delta,
                    vat=mn.VAT_INCL, channels="amazon", basis="order", extra=_as(t("mn.x.before_cancel")),
                    help=passport.tip("home", "ordered",
                        (t("home.kpi.ordered_help_span",
                           of=_o_from.strftime("%d.%m"), ot=_o_to.strftime("%d.%m"),
                           mf=_m_from.strftime("%d.%m"), mt=_m_to.strftime("%d.%m"))
                         if _spans_differ else t("home.kpi.ordered_help"))))
    mn.money_metric(s0b, t("home.kpi.sales_all"), fmt_money(all_cur) if all_cur else "—", delta=_all_delta,
                    vat=mn.VAT_INCL, channels="all", basis="order", extra=_as(sales_all_extra(sales_all)),
                    help=passport.tip("home", "ordered_all", t("home.kpi.sales_all_help")))
    mn.money_metric(s1, t("home.kpi.revenue_pbi") if _pbi else t("home.kpi.revenue"), fmt_money(rev_cur),
                    delta=_rev_delta, vat=mn.VAT_EXCL, channels="all", basis="order",
                    extra=_as(t("mn.x.before_returns") if _pbi else t("mn.x.after_returns")),
                    help=passport.tip("home", "revenue",
                        t("home.kpi.revenue_help_pbi", f=_w.cur_from.strftime("%d.%m"), to=_w.cur_to.strftime("%d.%m"),
                          pf=_w.prev_from.strftime("%d.%m"), pt=_w.prev_to.strftime("%d.%m")) if _pbi else
                        t("home.kpi.revenue_help_r",
                          f=_w.cur_from.strftime("%d.%m"), to=_w.cur_to.strftime("%d.%m"),
                          pf=_w.prev_from.strftime("%d.%m"), pt=_w.prev_to.strftime("%d.%m"))))
    # У маржи процента изменения нет намеренно (07.10.2026): себестоимость возврата, принятого на склад брака,
    # возвращается в маржу датой возврата, но только когда склад его разберёт (в среднем 6–23 дня). Прошлый период
    # всегда «богаче» текущего: неделя 07.09 получила так +626 €, недели 21.09 и 28.09 — пока ноль, при марже около
    # 800 € в неделю. Процент показывал бы падение, которого нет. У Contribution Profit Power BI то же самое:
    # возвраты в его витрине идут по дате расчёта Amazon и приходят в прошлые недели задним числом
    mn.money_metric(s2, t("home.kpi.margin_pbi") if _pbi else t("home.kpi.margin"), f"{cm_cur:,.0f} € · {cm_pct:.0f}%",
                    vat=mn.VAT_EXCL, channels="all", basis="order",
                    extra=_as(t("mn.x.share_of_sales_excl") if _pbi else t("mn.x.after_costs")),
                    help=passport.tip("home", "margin", (t("home.kpi.margin_help_pbi") if _pbi
                                                         else t("home.kpi.margin_help") + " " + t("mn.margin_no_delta"))))
    _ref = int(cur.get("units_refunded", pd.Series(dtype=float)).sum() or 0)
    mn.money_metric(s3, t("home.kpi.units"), f"{units_cur:,}",
                    delta=(f"−{_ref} {t('home.kpi.refunded')}" if _ref else None),
                    delta_color="inverse" if _ref else "off",
                    # «возврат» — не изменение к прошлому периоду: стрелка «↑ −62» читалась как рост
                    delta_arrow="off",
                    vat=mn.VAT_NONE, channels="all", basis="order", extra=_as(None),
                    help=passport.tip("home", "units", t("home.kpi.units_help_pbi") if _pbi else t("home.kpi.units_help")))
    # площадка с продажами — где были штуки: строка одного возврата и «рекламный день» без продаж (05.10.2026) не в счёт
    _n_markets = cur.loc[pd.to_numeric(cur['units'], errors='coerce').fillna(0) > 0, 'marketplace'].nunique()
    # «По какое число» — подписью, а не только в подсказке ⓘ. Еженедельная сверка с внешним
    # отчётом расходилась ровно на один день (28.09.2026: отчёт за 1–26.09 против наших 1–27.09,
    # три рынка из четырёх сошлись до евро), и пока дата не написана рядом с цифрой, этот вопрос
    # возвращается каждую неделю. Источников у ряда два, и даты у них разные, поэтому когда они
    # расходятся — называем обе: карточка «Продажи по заказам» живёт на витрине S&T,
    # выручка и маржа — на экономике, и экономика обычно отстаёт на день.
    # Одна строка про период: по какое число, каких дней ещё нет, что отрезано как недогруженное и что ещё
    # предварительно — общая функция money_notes.period_line, та же, что в «Деньгах» (07.10.2026)
    _cut = pd.notna(_loaded_last) and pd.notna(_full_last) and _loaded_last > _full_last
    if _spans_differ and not _cut:
        # витрина и экономика кончаются разными днями — называем обе даты; это единственное, чего общая строка не умеет
        _period_txt = " ".join(x for x in (
            t("home.kpi.as_of_split", o=_o_to.strftime("%d.%m"), m=_m_to.strftime("%d.%m")),
            mn.provisional_text(_dstat, _w.cur_from, _w.cur_to)) if x)
    else:
        _as_of = _m_to if pd.notna(_m_to) else (_o_to if pd.notna(_o_to) else _full_last)
        _period_txt = mn.period_line(_dstat, _w.cur_from, _as_of, PERIOD.end, _loaded_last)
    if _period_txt:
        st.caption(_period_txt)
    # ACOS и TACOS — формулы Power BI (05.10.2026): весь расход на рекламу к продажам с рекламы и ко всем продажам
    # с НДС; с 08.10.2026 и числа те же — из реплики его витрины (ad_ratios). Окно — то же, что у выручки и маржи
    if pd.notna(_m_from) and pd.notna(_m_to):
        _ar = load_ad_ratios(_m_from.date(), _m_to.date(),
                             data_version("ads_market_daily", "updated_at") if pbi.OWN_METHOD
                             else data_version("pbi_spiderweb_report", "loaded_at"))
        _a1, _a2, _a3, _ = st.columns([1, 1, 1, 2])
        _a3.metric(t("home.kpi.markets"), f"{_n_markets}", help=passport.tip("home", "channels"))
        mn.money_metric(_a1, "ACOS", f"{_ar['acos']:.1f} %" if _ar.get("acos") is not None else "—",
                        vat=mn.VAT_NONE, channels="all", basis=None, extra=_as(t("mn.x.acos_pbi") if _pbi else t("mn.x.acos")),
                        help=passport.tip("home", "acos", mn.help_with_vat(mn.VAT_INCL, t("home.kpi.acos_help"))))
        mn.money_metric(_a2, "TACOS", f"{_ar['tacos']:.1f} %" if _ar.get("tacos") is not None else "—",
                        vat=mn.VAT_NONE, channels="all", basis="order", extra=_as(t("mn.x.tacos")),
                        help=passport.tip("home", "tacos", mn.help_with_vat(mn.VAT_INCL, t("home.kpi.tacos_help"))))
    if rev_cur and _no_cogs_rev > 0.5:
        st.caption(t("home.kpi.margin_partial", rev=f"{_no_cogs_rev:,.0f}", pct=f"{_no_cogs_rev / rev_cur * 100:.0f}",
                     known=f"{_rev_known / rev_cur * 100:.0f}"))

    gl, gr = st.columns([1.6, 1])

    with gl:
        # Ось — весь выбранный период, а не только дни, где нашлись строки.
        # Без этого девятидневный период с данными за два дня рисовался двумя
        # точками, и Plotly подписывал их часами: выглядело так, будто продажи
        # шли полдня и кончились
        if date_from is not None:
            _ax_from, _ax_to = date_from, date_to
        else:
            _ax_from, _ax_to = _w.cur_from, _w.cur_to
        daily = day_axis(
            cur.groupby("sales_date", as_index=False)["revenue"].sum(),
            "sales_date", _ax_from, _ax_to)

        # Пустой день бывает двух видов, и различает их только свидетель —
        # витринная выручка: она приходит другим загрузчиком и другим отчётом.
        # Показывает продажи, а строки у нас нет — это дыра, ноль там был бы
        # ложью (17.08: трафик 57 штук, в экономике ни строки). Ноль ставим
        # только когда свидетель подтверждает, что продаж не было.
        # Дни за границей загрузки — всегда разрыв, там отчёт ещё не пришёл
        _witness = (ordered.groupby("sales_date")["ordered_sales"].sum()
                    if not ordered.empty else pd.Series(dtype=float))
        _empty = daily["revenue"].isna() & (daily["sales_date"] <= _full_last)
        _zero = _empty & daily["sales_date"].map(
            lambda d: _witness.get(d, None) == 0).astype(bool)
        daily.loc[_zero, "revenue"] = 0.0
        _holes = daily.loc[_empty & ~_zero, "sales_date"]

        mn.chart_note(t("mn.what.revenue_by_day"), mn.VAT_EXCL, "all", "order", _w.cur_from, _w.cur_to,
                      extra=_as(t("mn.x.before_returns") if _pbi else t("mn.x.after_returns")))
        # линия с заливкой, а не px.area: у area пропуск складывается как НОЛЬ (stackgaps), и день, который
        # ещё не приехал (06.10 при данных по 05.10), рисовался обвалом выручки до нуля
        fig = px.line(daily, x="sales_date", y="revenue",
                      color_discrete_sequence=[BLUE])
        fig.update_layout(height=190, margin=dict(l=0, r=0, t=6, b=0),
                          xaxis_title=None, yaxis_title=None,
                          yaxis=dict(showgrid=False))
        fig.update_xaxes(type="date", tickformat="%d.%m",
                         range=[_ax_from, _ax_to])
        fig.update_traces(line=dict(width=1.5), fill="tozeroy", connectgaps=False,
                          fillcolor="rgba(31,119,180,0.15)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        # Подписи под графиком: где кончились данные и где дыры внутри.
        # Если за период нет вообще ничего, про обрыв говорить нечего
        if daily["revenue"].isna().all():
            st.caption(t("home.chart.no_data_period"))
        else:
            # где кончились данные — говорит строка периода под карточками; вторая подпись здесь дублировала её
            if len(_holes):
                # на длинном периоде «21.09» без года читается как будущий день текущего
                # месяца; и полсотни дат подряд — простыня, показываем первые пятнадцать
                _hf = "%d.%m.%Y" if _ax_from.year != _ax_to.year else "%d.%m"
                _hd = list(_holes.dt.strftime(_hf))
                st.caption(t("home.chart.holes", n=len(_hd),
                             d=", ".join(_hd[:15]) + ("…" if len(_hd) > 15 else "")))

    with gr:
        # Канал — это площадка (Amazon, Leroy Merlin, ManoMano, Carrefour),
        # а не страна. Раньше он выводился сравнением с литералом "LM", и
        # каждая новая площадка требовала правки здесь. Теперь берём из
        # справочника — следующая появится сама
        ch_map = load_channels()
        _ch_lookup = dict(zip(ch_map["marketplace_code"], ch_map["channel"]))
        if not pbi.OWN_METHOD and "platform" in money.columns:
            # площадка — как в Power BI, из самой витрины: Wallapop и сайт до 09.10.2026 сливались в «Прочие» одной
            # суммой, потому что их кодов нет в справочнике маркетплейсов
            _ch_lookup.update({str(k).upper(): v for k, v in
                               money[["marketplace", "platform"]].dropna().drop_duplicates().values})
        _label_of = dict(zip(ch_map["marketplace_code"], ch_map.get("label", ch_map["marketplace_code"])))
        def _lbl(code) -> str:
            c = as_text(code).strip().upper()
            return _label_of.get(c, c)

        def _channel_of(code) -> str:
            return _ch_lookup.get(as_text(code).strip().upper(),
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

        # это не «Продажи по заказам» из карточки сверху: здесь выручка без НДС и после
        # возвратов — база маржи. Без подписи «Amazon · продажи в 6 странах» читалось как
        # то же число, что в карточке, и разница в 12 тыс. € выглядела ошибкой (20.09.2026)
        mn.chart_note(t("mn.what.revenue_by_channel"), mn.VAT_EXCL, "all", "order", _w.cur_from, _w.cur_to,
                      extra=_as(t("mn.x.before_returns") if _pbi else t("mn.x.after_returns")))
        for _, r in by_ch.iterrows():
            share = r["revenue"] / rev_cur * 100 if rev_cur else 0
            codes = sorted(sold_mp.loc[sold_mp["channel"] == r["channel"],
                                       "marketplace"])
            if not codes:
                sub = ""
            elif len(codes) <= 2:
                sub = ", ".join(_lbl(c) for c in codes)
            else:
                sub = t("home.sales.n_countries", n=len(codes))
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
                chips += _chip(_lbl(m["marketplace"]), m["revenue"], col)
            for code in silent_by_ch.get(r["channel"], []):
                chips += _chip(_lbl(code), 0.0, ACCENT, muted=True)

        st.markdown(
            f'<div style="margin-top:6px;line-height:2">{chips}</div>',
            unsafe_allow_html=True)

    if ord_cur and rev_cur and _o_clipped:
        st.caption(t("home.sales.ordered_clipped", d=_econ_first.strftime("%d.%m.%Y")))
    # Разбор «почему две цифры разные» — про нашу методику (НДС по факту, отмены, возвраты, лаг экономики). В цифрах
    # Power BI разница Amazon — ровно НДС по ставке страны, и подпись про отмены и возвраты была бы неправдой
    if ord_cur and rev_cur and pbi.OWN_METHOD:
        # Разница карточки и выручки каналов — НДС, отмены, возвраты И лаг: за последний день
        # экономика обычно неполная (18.09.2026: 116 € против 1 753 € в витрине), а даты
        # у источников совпадают, поэтому проверка «окна разные» молчала и лаг читался как отмены.
        # Неполным считаем день, где экономика без НДС меньше 60 % витрины с НДС: одна ставка
        # НДС (≤ 25 %) и отмены такого провала не дают.
        _LAG_RATIO = 0.6
        _lag = ""
        _amz_codes = set(ordered["marketplace"].dropna().astype(str).str.upper()) if not ordered.empty else set()
        _ecur = cur[cur["marketplace"].astype(str).str.upper().isin(_amz_codes)] if len(cur) else cur
        if len(_ecur) and len(_o):
            _d = pd.Timestamp(_ecur["sales_date"].max())
            _e_last = float(_ecur.loc[_ecur["sales_date"] == _d, "gross_revenue"].sum())
            _s_last = float(_o.loc[_o["sales_date"] == _d, "ordered_sales"].sum())
            if _s_last > 0 and _e_last < _s_last * _LAG_RATIO:
                _lag = t("home.sales.two_numbers_lag", d=_d.strftime("%d.%m"), e=_e_last, s=_s_last)
        # «Продажи по заказам» — только Amazon, «Выручка» — все каналы: сравнивать их целиком значило бы
        # вычитать из Amazon с НДС ещё и Leroy Merlin, ManoMano и Carrefour (06.10.2026: «разница −142 €»).
        # Разницу считаем Amazon к Amazon, выручку Mirakl называем отдельно
        _rev_amz = float(_ecur["revenue"].sum()) if len(_ecur) else 0.0
        _rev_other = rev_cur - _rev_amz
        # с НДС и до возвратов витрина больше выручки всегда; обратное значит, что витрина Amazon за конец
        # периода ещё не догружена, — говорим это, а не «разница −330 €»
        _gap = ord_cur - _rev_amz
        st.caption((t("home.sales.two_numbers", gap=_gap, pct=_gap / ord_cur * 100) if _gap > 0
                    else t("home.sales.two_numbers_neg", gap=-_gap)) + _lag
            + (t("home.sales.two_numbers_other", m=_rev_other) if _rev_other > 0.5 else ""))
    # План текущего месяца из реестра прогноза (ТЗ 010) в трёх разрезах. От периода
    # страницы не зависит: человек менял период и думал, что план пересчитался
    _today = datetime.now().date()
    plan_raw, pace_thr, plan_err = load_plan_month(data_version("economics_summary", "updated_at"))
    st.markdown(f"**{t('home.plan.month_title', m=_today.strftime('%m.%Y'))}**")
    st.caption(t("home.plan.always_current"))
    if plan_err:
        st.caption(t("home.plan.error", e=plan_err))
    elif plan_raw.empty or plan_raw["plan_units"].notna().sum() == 0:
        st.caption(t("home.plan.none"))
    else:
        _modes = {"country": t("home.plan.mode_country"), "country_mp": t("home.plan.mode_country_mp"),
                  "platform": t("home.plan.mode_platform")}
        pm1, pm2 = st.columns([3, 1])
        _mode_lbl = pm1.radio(t("home.plan.mode"), list(_modes.values()), horizontal=True,
                              key="plan_mode", label_visibility="collapsed")
        _mode = next(k for k, v in _modes.items() if v == _mode_lbl)
        _units = pm2.toggle(t("home.plan.units_toggle"), value=False, key="plan_units")
        rows, total, _share = plan_fact.month_view(plan_raw, _mode, _today)

        # итог — по всем объектам плана, одинаковый во всех разрезах
        _pace_total = total.get("pace_rev")   # темп итога — по строкам с планом; факт — по всем
        # к чему темп — словами и датой: «−77 %» без опоры читалось как падение к прошлому периоду
        _dt = total.get("data_through")
        _dt_txt = _dt.strftime("%d.%m") if _dt else "—"
        tt1, tt2, tt3 = st.columns(3)
        mn.money_metric(tt1, t("home.plan.total_plan"), fmt_money(total["plan_rev"]),
                        vat=mn.VAT_INCL, channels="amazon", basis="month_plan", help=t("home.plan.total_help"))
        mn.money_metric(tt2, t("home.plan.total_expected"), fmt_money(total["expected_rev"]),
                        vat=mn.VAT_INCL, channels="amazon", basis="month_to_date",
                        help=t("home.plan.total_expected_help", k=total["covered"], n=total["days_in_month"]))
        mn.money_metric(tt3, t("home.plan.total_fact"), fmt_money(total["fact_rev"]),
                        delta=(None if _pace_total is None
                               else t("mn.pace_vs", p=f"{_pace_total:+.0f}", d=_dt_txt)),
                        vat=mn.VAT_INCL, channels="amazon", basis="shipment", extra=t("mn.x.vs_expected"),
                        help=t("home.plan.total_fact_help"))

        def _pace_txt(v):
            if v is None or pd.isna(v):
                return "—"
            mark = "▲" if v > pace_thr else ("▼" if v < -pace_thr else "•")
            return f"{mark} {v:+.0f}%"
        # узел и маркетплейс — две колонки, заполненные в каждой строке: таблицу сортируют
        # кликом по заголовку, и строка с отступом «↳ CF-ES» после сортировки оказывалась под Бельгией
        _out = []
        for _, r in rows.iterrows():
            # строка узла: «Σ итого» — после сортировки по колонке она оказывается среди маркетплейсов,
            # и без метки читалась как ещё один рынок (QA 21.09)
            grp, nm = r["parent"], (("Σ " + t("home.plan.node_total")) if r["level"] == 0 else r["name"])
            _out.append(dict(group=grp, name=nm, sub=r["sub"], unit="€", plan=r["plan_rev"], expected=r["expected_rev"],
                             fact=r["fact_rev"], done=r["done_rev"], pace=_pace_txt(r["pace_rev"]), skus=r["plan_skus"]))
            if _units:
                _out.append(dict(group=grp, name=nm, sub=r["sub"], unit="шт", plan=r["plan_units"], expected=r["expected_units"],
                                 fact=r["fact_units"], done=r["done_units"], pace=_pace_txt(r["pace_units"]),
                                 skus=r["plan_skus"]))   # то же число: счётчик SKU не зависит от единицы, а пропуск NumberColumn рисует словом «None»
        _pt = pd.DataFrame(_out)
        for c in ("plan", "expected", "fact"):
            _pt[c] = _pt[c].round(0)
        _pt["skus"] = pd.to_numeric(_pt["skus"], errors="coerce").astype("Int64")
        # «Выполнение» — ТЕКСТОМ, а не ProgressColumn. Веб-агент видел в этой колонке
        # 29.897751605995726: виджет прогресса при части значений отдаёт число как есть,
        # и воспроизвести это в отрыве от страницы не удалось. Соседний «Темп» с самого
        # начала собирается текстом и таких сюрпризов не давал — приводим к нему.
        _pt["done"] = [("—" if pd.isna(v) else f"{float(v):.0f} %") for v in _pt["done"]]
        # в разрезе «По стране» строка узла — единственная, колонка «Маркетплейс» сплошь «итого» — не показываем
        _has_mp = _mode != "country"
        _cols = [c for c in (["group", "name", "unit", "plan", "expected", "fact", "done", "pace", "skus", "sub"] if _units
                             else ["group", "name", "plan", "expected", "fact", "done", "pace", "skus", "sub"]) if _has_mp or c != "name"]
        _grp_lbl = t("home.plan.col_platform") if _mode == "platform" else t("home.plan.col_country")
        st.caption(t("home.plan.note", d=_dt_txt,
                     k=total["covered"], n=total["days_in_month"], thr=f"{pace_thr:.0f}"))
        # 1. НДС — в заголовке каждой денежной колонки, а не только в пояснении
        _vat_hdr = "home.plan.hdr_units" if _units else "home.plan.hdr_eur"
        st.dataframe(_pt[_cols], hide_index=True, use_container_width=True,
                     height=min(600, 38 + 35 * len(_pt)),
                     column_config={
                         "group": st.column_config.TextColumn(_grp_lbl, width="small"),
                         "name": st.column_config.TextColumn(t("home.plan.col_name"), width="medium"),
                         "unit": st.column_config.TextColumn(t("home.plan.col_unit"), width="small"),
                         "plan": st.column_config.NumberColumn(t(_vat_hdr, c=t("home.plan.col_plan")), format="%,.0f",
                                                               help=t("home.plan.col_plan_help")),
                         "expected": st.column_config.NumberColumn(t(_vat_hdr, c=t("home.plan.col_expected")), format="%,.0f",
                                                                   help=t("home.plan.col_expected_help")),
                         "fact": st.column_config.NumberColumn(t(_vat_hdr, c=t("home.plan.col_fact")), format="%,.0f"),
                         "done": st.column_config.TextColumn(t("home.plan.col_done"), width="small"),
                         "pace": st.column_config.TextColumn(t("home.plan.col_pace_to", d=_dt_txt),
                                                             help=t("home.plan.col_pace_help")),
                         "skus": st.column_config.NumberColumn(t("home.plan.col_skus"), format="%d"),
                         "sub": st.column_config.TextColumn(t("home.plan.col_sub"), width="medium"),
                     })
        # отгрузка без строки заказа: в штуках она есть, в евро её нет — и об этом надо
        # сказать словом, иначе «Факт, €» выглядит полным при неполной цене
        _unp = float(total.get("fact_unpriced_units") or 0)
        if _unp > 0:
            _fu = float(total.get("fact_units") or 0)
            st.caption(t("plan.unpriced", n=f"{_unp:,.0f}".replace(",", " "),
                         p=f"{(_unp / _fu * 100) if _fu else 0:.1f}"))
        st.caption(t("home.plan.pool_note"))
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
            st.error(t("cov.err.query", e=err))
        elif not d["table"]:
            st.error(t("cov.err.no_table"))
        elif not d["rows"]:
            st.warning(t("cov.err.no_rows"))
        else:
            st.warning(t("cov.err.no_match", 
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
                  help=passport.tip("home", "coverage", t("home.kpi.secured_help")))
        v2.metric(t("home.kpi.deficit_soon"), f"{n_crit:,}",
                  help=passport.tip("home", "coverage", t("home.kpi.deficit_soon_help")))
        v3.metric(t("home.kpi.deficit_later"), f"{n_warn:,}",
                  help=passport.tip("home", "coverage", t("home.kpi.deficit_later_help")))

        bars = pd.DataFrame({
            "bucket": [t("home.cov.b_crit"), t("home.cov.b_warn"),
                       t("home.cov.b_ok")],
            "n": [n_crit, n_warn, n_ok],
        })
        _cd = pd.to_datetime(cov["calc_date"]).max() if "calc_date" in cov else pd.NaT
        mn.chart_note(t("mn.what.cov_buckets"), mn.VAT_NONE, "=" + t("mn.ch.fba_madrid"), None,
                      extra=(t("mn.x.calc_on", d=_cd.strftime("%d.%m.%Y")) if pd.notna(_cd) else None))
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
                  help=passport.tip("home", "transfers", t("home.kpi.transfers_help")))
        r2.metric(t("home.kpi.transfer_qty"),
                  f"{int(pending['transfer_qty'].sum()):,}",
                  help=passport.tip("home", "transfers"))
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
                  help=passport.tip("home", "incidents", t("home.kpi.inc_supply_help")))
        n2.metric(t("home.kpi.inc_sales"), f"{n_sales:,}",
                  help=passport.tip("home", "incidents", t("home.kpi.inc_sales_help")))
        n3.metric(t("home.kpi.inc_oldest"), f"{oldest}",
                  help=t("home.kpi.inc_oldest_help"))

        if len(open_inc):
            # подпись типа: словарь → название из справочника «Алерты» → код
            _titles = load_incident_titles()
            open_inc = open_inc.copy()
            open_inc["type_label"] = open_inc["incident_type"].map(
                lambda v: incident_type_label(v, _titles))
            by_type = (open_inc.groupby("type_label", as_index=False)
                               .size().rename(columns={"size": "n"})
                               .sort_values("n", ascending=True).tail(5))
            mn.chart_note(t("mn.what.inc_by_type"), mn.VAT_NONE, "", None, extra=t("mn.x.now_open"))
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
        # даты — те же, что у периода страницы, и названы числами, а не «за N дней»
        _rf, _rt = PERIOD.start.strftime("%d.%m"), _rev_end.strftime("%d.%m")
        q1.metric(t("home.kpi.requests_r", f=_rf, to=_rt),
                  f"{reviews.get('sent7', 0):,}",
                  help=passport.tip("home", "reviews", t("home.kpi.requests_help_r", f=_rf, to=_rt)))
        growth = reviews.get("reviews_growth")
        _d0, _d1 = reviews.get("d0"), reviews.get("d1")
        q2.metric(t("home.kpi.new_reviews"),
                  f"+{growth:,}" if growth is not None else "—",
                  help=passport.tip("home", "reviews", t("home.kpi.new_reviews_help_r",
                      f=(pd.Timestamp(_d0).strftime("%d.%m") if _d0 is not None and pd.notna(_d0) else _rf),
                      to=(pd.Timestamp(_d1).strftime("%d.%m") if _d1 is not None and pd.notna(_d1) else _rt),
                      n=reviews.get("reviews_pairs", 0))))
        if reviews.get("last_sent") is not None:
            ls = pd.to_datetime(reviews["last_sent"])
            hours = (datetime.now(ls.tzinfo) - ls).total_seconds() / 3600
            if hours > 25:
                st.warning(t("home.rev.stopped", h=hours))
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

# блок «Откуда данные» — последним на странице
passport.footer("home")
