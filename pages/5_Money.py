# pages/5_Money.py — Деньги: полная P&L (Contribution Margin)
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from db.connection import get_connection
from i18n import init_lang, t
from util import as_text
import catalog
from links import AMAZON_DOMAIN, amazon_url
import period as period_mod

init_lang()

st.markdown("""
<style>
[data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.9rem; }
</style>
""", unsafe_allow_html=True)

st.title(t("money.title"))
st.caption(t("money.caption"))


def clean_sku(sku: str) -> str:
    s = as_text(sku).strip()
    s = re.sub(r"^amzn\.gr\.", "", s)
    s = s.replace("-FBA", "").replace("-FBM", "")
    s = re.sub(r"-[A-Za-z0-9]{8,}$", "", s)
    s = re.sub(r"-[A-Za-z]$", "", s)
    return s.strip(" -")


WINDOW_DEFAULT = 30


@st.cache_data(ttl=600)
def load_marketplaces() -> list:
    """Список рынков для фильтра — из фактических данных, а не из справочника.
    Каналы вне Amazon (LM) в v_marketplace_map отсутствуют, и построенный
    по нему фильтр их бы не показал. DISTINCT по двум таблицам берёт всё,
    что реально продавалось, включая Mirakl."""
    conn = get_connection()
    try:
        r = pd.read_sql("""
            SELECT DISTINCT marketplace FROM kabinet_data.economics_summary
            WHERE marketplace IS NOT NULL
            UNION
            SELECT DISTINCT marketplace FROM kabinet_data.sales_traffic_daily
            WHERE marketplace IS NOT NULL
        """, conn)
        return sorted(r["marketplace"].dropna().astype(str).str.strip().unique())
    except Exception:
        return []
    finally:
        conn.close()


def _mk_clause(markets, col: str = "marketplace") -> tuple:
    """Условие фильтра по рынкам. Пустой выбор — все рынки.
    Сравниваем через UPPER с обеих сторон: economics_summary и
    sales_traffic_daily заполняются разными загрузчиками, и регистр
    кода рынка между ними может расходиться."""
    if not markets:
        return "", []
    return f" AND UPPER({col}) = ANY(%s)", [[m.upper() for m in markets]]


@st.cache_data(ttl=600)
def load_pnl(days: int, d_from=None, d_to=None, markets: tuple = ()):
    conn = get_connection()
    if d_from and d_to:
        where = f"e.sales_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = f"""e.sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days} days'
                               FROM kabinet_data.economics_summary)"""
    mk_sql, mk_params = _mk_clause(markets, "e.marketplace")
    df = pd.read_sql(f"""
        SELECT e.norm_sku, e.product_name, e.marketplace, e.sales_date,
               e.units_ordered      AS units,
               e.ordered_product_sales AS gross_revenue,
               e.net_product_sales  AS revenue,
               e.total_fees         AS fees,
               e.net_proceeds_total AS net_proceeds,
               -- COGS без COALESCE: ноль и «не загружено» это разные вещи.
               -- Раньше пустая себестоимость превращалась в 0 и давала
               -- прибыль, равную выручке — по этим SKU показываем прочерк
               e.cogs               AS cogs_unit,
               e.commission_fee     AS commission,
               COALESCE(a.total_spend, 0) AS ads,
               s.asin
        FROM kabinet_data.economics_summary e
        LEFT JOIN (
            -- схлопываем рекламу до одной строки на ключ: иначе несколько
            -- кампаний по одному SKU размножат строку экономики,
            -- и выручка посчитается дважды
            SELECT date, marketplace, norm_sku,
                   SUM(total_spend) AS total_spend
            FROM kabinet_data.ads_spend
            GROUP BY 1, 2, 3
        ) a
          ON a.date = e.sales_date
         AND a.marketplace = e.marketplace
         AND a.norm_sku = e.norm_sku
        LEFT JOIN (
            -- ASIN берём из справочника соответствия товара и листинга.
            -- Раньше собирали из остатков и заказов — там ASIN заполнен
            -- не везде, и часть товаров оставалась без ссылки.
            -- Одна строка на товар: ASIN общий на всю Европу, а страну
            -- для ссылки определяем по маркетплейсу самой продажи
            SELECT sku_group, MAX(asin) AS asin
            FROM kabinet_data.sku_asin_map
            WHERE asin IS NOT NULL
            GROUP BY sku_group
        ) s ON s.sku_group = SUBSTRING(e.norm_sku FROM '([0-9]{{5,}})')
        WHERE {where}{mk_sql}
    """, conn, params=mk_params or None)
    conn.close()
    return df


@st.cache_data(ttl=600)
def load_bsr(days: int) -> pd.DataFrame:
    """Позиция товара в категории Amazon и её изменение за период.
    Ранг зависит не только от наших продаж: конкурент вырос — мы опустились
    при тех же продажах. Поэтому читаем как относительное положение."""
    conn = get_connection()
    try:
        df = pd.read_sql(f"""
            WITH bounds AS (
                SELECT MIN(snapshot_date) AS d0, MAX(snapshot_date) AS d1
                FROM kabinet_data.asin_bsr_daily
                WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
            )
            SELECT b.asin,
                   MAX(CASE WHEN b.snapshot_date = x.d1 THEN b.rank END)     AS rank_now,
                   MAX(CASE WHEN b.snapshot_date = x.d0 THEN b.rank END)     AS rank_was,
                   MAX(CASE WHEN b.snapshot_date = x.d1 THEN b.category END) AS category
            FROM kabinet_data.asin_bsr_daily b
            CROSS JOIN bounds x
            WHERE b.rank IS NOT NULL
              AND b.snapshot_date IN (x.d0, x.d1)
            GROUP BY b.asin
        """, conn)
        if df.empty:
            return df
        # ранг меньше — значит выше в категории, поэтому знак переворачиваем:
        # положительное число означает подъём
        df["rank_delta"] = df["rank_was"] - df["rank_now"]
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_ordered_sales(days: int, d_from=None, d_to=None, markets: tuple = ()):
    """Витринная выручка — то же число, что в Seller Central.
    Рынки передаём кортежем: он хешируется и попадает в ключ кеша."""
    if d_from and d_to:
        where = f"snapshot_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = (f"snapshot_date >= (SELECT MAX(snapshot_date) - INTERVAL '{days} days' "
                 f"FROM kabinet_data.sales_traffic_daily)")
    mk_sql, mk_params = _mk_clause(markets)
    conn = get_connection()
    try:
        r = pd.read_sql(f"""
            SELECT COALESCE(SUM(ordered_sales), 0) AS ordered_sales,
                   COALESCE(SUM(units_ordered), 0) AS units
            FROM kabinet_data.sales_traffic_daily
            WHERE {where}{mk_sql}
        """, conn, params=mk_params or None)
        return float(r["ordered_sales"].iloc[0])
    except Exception:
        return None
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_amazon_codes() -> tuple:
    """Коды рынков, относящихся к Amazon.

    Витринная выручка живёт в sales_traffic_daily — это отчёт Seller
    Central, других площадок в нём нет. Раньше их отсеивал литерал
    `!= "LM"`, и с появлением ManoMano и Carrefour это сломалось бы молча:
    выбранный фильтром MM_ES прошёл бы за амазоновский, запрос вернул бы
    ноль, и карточка показала бы «0 €» вместо прочерка — тот же баг, что
    чинили для LM, только в новом составе.

    Признак берём из справочника: channel = 'Amazon'. Не по заполненности
    amazon_id — это техническое поле, и у новой страны его могут не
    заполнить, тогда она молча уедет не в тот канал."""
    conn = get_connection()
    try:
        r = pd.read_sql("""
            SELECT marketplace_code
            FROM kabinet_data.v_marketplaces
            WHERE UPPER(channel) = 'AMAZON'
        """, conn)
        return tuple(sorted(r["marketplace_code"].dropna().astype(str)
                             .str.strip().str.upper().unique()))
    except Exception:
        return ()


@st.cache_data(ttl=600)
def load_period_bounds(days: int, d_from=None, d_to=None) -> tuple:
    """Границы периода — общий якорь для всех карточек. Витринная выручка
    лежит в другой таблице, и без якоря она считалась от MAX(snapshot_date)
    своей, а остальные карточки — от MAX(sales_date) своей. Загрузчики
    отрабатывают не синхронно, поэтому окна разъезжались на день, и
    карточки на одной странице показывали разные периоды."""
    if d_from and d_to:
        return d_from, d_to
    conn = get_connection()
    try:
        r = pd.read_sql(f"""
            SELECT MAX(sales_date) - INTERVAL '{days} days' AS d0,
                   MAX(sales_date)                          AS d1
            FROM kabinet_data.economics_summary
        """, conn)
        d0, d1 = r["d0"].iloc[0], r["d1"].iloc[0]
        if pd.isna(d0) or pd.isna(d1):
            return None, None
        return pd.Timestamp(d0).date(), pd.Timestamp(d1).date()
    except Exception:
        return None, None
    finally:
        conn.close()


@st.cache_data(ttl=600)
def load_control_total(days: int, d_from=None, d_to=None, markets: tuple = ()):
    """Контрольная выручка прямо из таблицы, без соединений.
    Если основной запрос разойдётся с ней — значит строки размножились
    при JOIN, и цифры на странице завышены. Такое уже случалось."""
    if d_from and d_to:
        where = f"sales_date BETWEEN '{d_from}' AND '{d_to}'"
    else:
        where = (f"sales_date >= (SELECT MAX(sales_date) - INTERVAL '{days} days' "
                 f"FROM kabinet_data.economics_summary)")
    mk_sql, mk_params = _mk_clause(markets)
    conn = get_connection()
    try:
        r = pd.read_sql(f"""
            SELECT COALESCE(SUM(net_product_sales), 0) AS revenue,
                   COALESCE(SUM(units_ordered), 0)     AS units,
                   COUNT(*)                            AS rows
            FROM kabinet_data.economics_summary
            WHERE {where}{mk_sql}
        """, conn, params=mk_params or None)
        return r.iloc[0].to_dict()
    except Exception:
        return {}
    finally:
        conn.close()


# ---------- выбор периода ----------
# Набор вариантов и память о выборе — общие для Кабинета, см. period.py
pc1, pc2 = st.columns([2, 2])
PERIOD = period_mod.control(columns=(pc1, pc2))
period = PERIOD.choice
d_from = PERIOD.d_from.date() if PERIOD.is_range else None
d_to = PERIOD.d_to.date() if PERIOD.is_range else None

# ---------- фильтры ----------
# Объявляем до загрузки: рынок теперь режется в SQL, а не в pandas, поэтому
# его значение нужно знать раньше, чем уйдёт запрос. Заодно фильтр виден
# даже когда выборка пустая — иначе из состояния «ничего не нашлось»
# нельзя было выйти, не перезагрузив страницу
c1, c2 = st.columns([1, 2])
with c1:
    mp_filter = st.multiselect(
        t("money.filter.marketplace"),
        load_marketplaces(),
        placeholder=t("money.filter.marketplace_ph"),
    )
with c2:
    search = st.text_input(t("money.filter.search"),
                           placeholder=t("money.filter.search_ph"))

MK = tuple(sorted(mp_filter))

WINDOW = PERIOD.days
# «Этот месяц» и свой период приходят готовыми границами, остальные —
# отступом от сегодня: у диапазона конец может быть в прошлом
df = (load_pnl(0, d_from, d_to, MK) if PERIOD.is_range
      else load_pnl(WINDOW, markets=MK))

if df.empty:
    st.info(t("money.empty"))
    st.stop()

# подпись периода — как на Обзоре: показываем выбранный диапазон,
# а под ним предупреждаем, если данные за конец периода ещё не пришли
# Граница данных считается по КАЖДОМУ маркетплейсу отдельно, а берётся
# минимальная. Data Kiosk отдаёт отчёты с разной задержкой по странам:
# max по всей выборке обещал бы данные до самой свежей из них, хотя по
# остальным их нет. Раньше стоял именно max, и при нескольких странах
# подпись называла дату, которой по части из них не существует
_by_mp = (df.assign(_d=pd.to_datetime(df["sales_date"], errors="coerce"))
            .groupby("marketplace")["_d"].max().dropna())
_last = _by_mp.min() if len(_by_mp) else pd.NaT
_behind = sorted(_by_mp[_by_mp == _last].index) if len(_by_mp) else []
_ahead = _by_mp[_by_mp > _last] if len(_by_mp) else _by_mp

# заголовок пишет фактическую границу, а не запрошенную: показывать
# «01.08 — 28.08», когда данных нет после 25-го, значит обещать три дня,
# которых в цифрах ниже нет
_to_eff = (min(pd.Timestamp(d_to), _last) if (d_to and pd.notna(_last))
           else (pd.Timestamp(d_to) if d_to else None))
if d_from and d_to:
    _ptitle = t("money.period_title", 
        f=pd.Timestamp(d_from).strftime("%d.%m"),
        to=_to_eff.strftime("%d.%m.%Y"))
else:
    _ptitle = t("money.period_days", d=WINDOW)
st.markdown(f"##### {_ptitle}")

if pd.notna(_last):
    _lag = (pd.Timestamp(pd.Timestamp.now().date()) - _last).days
    if len(_ahead):
        # границы по странам разошлись — называем и отстающую, и остальные
        st.caption(t("money.period_lag_mixed", 
            d=_last.strftime("%d.%m"), mp=", ".join(_behind),
            more=", ".join(sorted(_ahead.index)),
            dmax=_ahead.max().strftime("%d.%m")))
    elif _lag >= 2:
        st.caption(t("money.period_lag", 
            d=_last.strftime("%d.%m"), n=_lag))

# сверяем с контрольной суммой: расхождение означает размножение строк
_ctrl = (load_control_total(0, d_from, d_to, MK) if (d_from and d_to)
         else load_control_total(WINDOW, markets=MK))
if _ctrl and _ctrl.get("rows"):
    _mine = float(pd.to_numeric(df["revenue"], errors="coerce").fillna(0).sum())
    _real = float(_ctrl["revenue"])
    if _real > 0 and abs(_mine - _real) / _real > 0.01:
        st.error(t("money.mismatch", 
            mine=_mine, real=_real,
            k=(_mine / _real if _real else 0),
            rows=int(len(df)), ctrl_rows=int(_ctrl["rows"])))

df["sku_display"] = df["norm_sku"].apply(clean_sku)
for c in ["units", "gross_revenue", "revenue", "fees", "net_proceeds", "ads"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
# себестоимость и комиссию НЕ заполняем нулём: пустое значение означает
# «не загружено», и ноль на его месте даёт фейковую прибыль
for c in ["cogs_unit", "commission"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["cogs_total"] = df["cogs_unit"] * df["units"]

# рынок уже отфильтрован в SQL, здесь остаётся только поиск по SKU
f = df.copy()
if search:
    f = f[f["sku_display"].str.contains(search, case=False, na=False)]

# ---------- KPI: полная воронка P&L ----------
tot_rev = f["revenue"].sum()
tot_net = f["net_proceeds"].sum()
tot_ads = f["ads"].sum()
# min_count=1 оставляет NaN, если по выборке не известна ни одна строка:
# обычный sum() вернул бы 0 и был бы неотличим от честного нуля
tot_cogs = f["cogs_total"].sum(min_count=1)
tot_comm = f["commission"].sum(min_count=1)

# прибыль считаем только там, где себестоимость известна: иначе по SKU
# без COGS вся выручка засчиталась бы в прибыль.
#
# Комиссия площадки отдельным слагаемым НЕ вычитается: у LM commission_fee
# и total_fees — одно и то же поле, а не два разных, и «Чистыми» её уже
# не содержит. Вычесть ещё раз означало бы посчитать комиссию дважды
known = f[pd.notna(f["cogs_total"])]
cm = (known["net_proceeds"].sum() - known["cogs_total"].sum()
      - known["ads"].sum())
cm_pct = (cm / tot_rev * 100) if tot_rev > 0 else 0
sku_all = f["norm_sku"].nunique()
sku_known = known["norm_sku"].nunique()
# доля выручки, покрытая известной себестоимостью. Считать надо именно её,
# а не долю SKU: 73 позиции из 124 могут быть и девяноста процентами
# выручки, и третью, и процент маржи читается совершенно по-разному
rev_known = float(known["revenue"].sum())
rev_share = (rev_known / tot_rev * 100) if tot_rev > 0 else 0.0

# Витринная выручка есть только по Amazon: sales_traffic_daily — отчёт
# Seller Central, каналов Mirakl в нём нет, поэтому LM из списка убираем.
# Важно различать два пустых состояния: «ничего не выбрано» = все рынки,
# и «выбран только LM» = амазоновских строк в выборке нет вовсе. Раньше оба
# сводились к пустой строке, WHERE не доходил до запроса, и карточка
# показывала сумму по всем странам при любом фильтре
_amz_all = load_amazon_codes()
if _amz_all:
    _amz = tuple(sorted({m.upper() for m in mp_filter if m.upper() in _amz_all}))
    _no_amazon = bool(mp_filter) and not _amz
else:
    # справочник недоступен — не выдумываем состав каналов, отдаём выбор
    # как есть. Лучше прежнее поведение, чем прочерк на каждом фильтре
    _amz = tuple(sorted({m.upper() for m in mp_filter}))
    _no_amazon = False

if _no_amazon:
    _ordered = None
else:
    _b0, _b1 = load_period_bounds(WINDOW, d_from, d_to)
    # sales_traffic_daily приходит через Ads/SP-API и опережает Data Kiosk
    # на несколько дней. Без обрезки «Продажи по заказам» считались за 28
    # дней, а «Выручка» рядом — за 25, и разницу между ними подпись ниже
    # объясняла НДС и возвратами, хотя часть её была просто разным периодом
    if _b1 and pd.notna(_last):
        _b1 = min(pd.Timestamp(_b1), _last).date()
    _ordered = (load_ordered_sales(0, _b0, _b1, _amz) if (_b0 and _b1)
                else load_ordered_sales(WINDOW, markets=_amz))

k0, k1, k2, k3, k4, k5 = st.columns(6)
k0.metric(t("money.kpi.ordered"),
          "—" if pd.isna(_ordered) else f"{_ordered:,.0f} €",
          help=t("money.kpi.ordered_help"))
k1.metric(t("money.kpi.revenue", d=WINDOW), f"{tot_rev:,.0f} €",
          help=t("money.kpi.revenue_help"))
k2.metric(t("money.kpi.net"), f"{tot_net:,.0f} €", help=t("money.kpi.net_help"))
k3.metric(t("money.kpi.cogs"),
          "—" if pd.isna(tot_cogs) else f"−{tot_cogs:,.0f} €",
          help=(t("money.kpi.cogs_missing") if pd.isna(tot_cogs)
                else t("money.kpi.cogs_help")))
k4.metric(t("money.kpi.ads"), f"−{tot_ads:,.0f} €", help=t("money.kpi.ads_help"))
# Период уезжает вместе с переходом: он общий для Кабинета и лежит в
# session_state, отдельно передавать нечего
with k4:
    st.page_link("pages/9_Ads.py", label=t("money.kpi.ads_link"),
                 icon=":material/arrow_forward:")
k5.metric(t("money.kpi.cm"),
          "—" if pd.isna(tot_cogs) else f"{cm:,.0f} €",
          delta=None if pd.isna(tot_cogs) else f"{cm_pct:.1f}%",
          help=t("money.kpi.cm_help"))

if sku_known < sku_all:
    st.caption(t("money.cogs_partial", 
        n=sku_known, total=sku_all, miss=sku_all - sku_known,
        pct=f"{rev_share:.0f}", rev=f"{rev_known:,.0f}"))

st.divider()

tab_pnl, tab_country, tab_fees, tab_alerts = st.tabs(
    [t("money.tab.pnl"), t("money.tab.by_marketplace"), t("money.tab.fees"),
     t("money.tab.alerts")]
)

BLUE = "#1f77b4"
ACCENT = "#e8484d"
GREEN = "#2e9e5b"


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)


# ---------- P&L по товарам ----------
with tab_pnl:
    def _first_filled(x):
        """Первое непустое значение. Товар продаётся в нескольких странах,
        и если первой попалась строка без ASIN, ссылки не будет вовсе."""
        v = x.dropna()
        v = v[v.astype(str).str.strip().ne("") & v.astype(str).ne("None")]
        return v.iloc[0] if len(v) else None

    by_sku = (f.groupby(["sku_display", "norm_sku"], as_index=False)
                .agg(product_name=("product_name", _first_filled),
                     asin=("asin", _first_filled),
                     marketplace=("marketplace", _first_filled),
                     markets=("marketplace", "nunique"),
                     units=("units", "sum"), revenue=("revenue", "sum"),
                     fees=("fees", "sum"), net_proceeds=("net_proceeds", "sum"),
                     cogs=("cogs_total", lambda x: x.sum(min_count=1)),
                     commission=("commission", lambda x: x.sum(min_count=1)),
                     ads=("ads", "sum")))

    # где товар продаётся: одна страна — её код, несколько — сколько их
    _mk = (f.groupby("sku_display")["marketplace"]
             .apply(lambda x: ", ".join(sorted(set(x.dropna())))))
    by_sku["markets_label"] = by_sku["sku_display"].map(_mk).fillna("—")
    # комиссия площадки — справочная колонка, в прибыль отдельно не входит:
    # «Чистыми» уже за вычетом комиссий, а у LM commission_fee и total_fees
    # это одно поле. В рекламу её тоже не подмешиваем: на Mirakl нет PPC,
    # и ноль в рекламе по LM — правда, а не пропуск данных
    by_sku["cm"] = by_sku["net_proceeds"] - by_sku["cogs"] - by_sku["ads"]
    by_sku["cm_pct"] = np.round(safe_div(by_sku["cm"], by_sku["revenue"]) * 100, 1)
    by_sku["acos_pct"] = np.round(safe_div(by_sku["ads"], by_sku["revenue"]) * 100, 1)
    # страну для ссылки берём амазоновскую: если первым в списке оказался
    # Leroy Merlin, домена Amazon для него нет и ссылка не построится,
    # хотя сам товар на Amazon продаётся
    _amz_mp = (f[f["marketplace"].isin(AMAZON_DOMAIN.keys())]
                 .groupby("sku_display")["marketplace"].first())
    by_sku["link_mp"] = by_sku["sku_display"].map(_amz_mp)

    by_sku["amazon_url"] = [
        amazon_url(mp, a) for mp, a in zip(by_sku["link_mp"], by_sku["asin"])
    ]
    # ASIN у Amazon общий на всю Европу: если по «своей» стране ссылка
    # не строится, ведём на испанский листинг — карточка та же
    by_sku["amazon_url"] = [
        u if u else amazon_url("ES", a)
        for u, a in zip(by_sku["amazon_url"], by_sku["asin"])
    ]
    by_sku["photo"] = catalog.image_series(
        asins=by_sku["asin"], skus=by_sku["sku_display"],
        markets=by_sku["link_mp"])

    def flag(row):
        if pd.isna(row["cm"]):
            return "⚪"
        if row["cm"] < 0:
            return "🔴"
        if row["cm_pct"] < 5:
            return "🟠"
        if row["cm_pct"] < 15:
            return "🟡"
        return "🟢"

    by_sku["flag_col"] = by_sku.apply(flag, axis=1)

    _bsr = load_bsr(WINDOW)
    if not _bsr.empty:
        by_sku = by_sku.merge(_bsr[["asin", "rank_now", "rank_delta", "category"]],
                              on="asin", how="left")
    else:
        by_sku["rank_now"] = None
        by_sku["rank_delta"] = None

    @st.cache_data(ttl=600)
    def load_annotations():
        conn = get_connection()
        try:
            adf = pd.read_sql("""
                SELECT sku, annotation_type, note
                FROM kabinet_data.pnl_annotations
            """, conn)
        except Exception:
            adf = pd.DataFrame(columns=["sku", "annotation_type", "note"])
        conn.close()
        return adf

    ann = load_annotations()
    ANN_ICON = {"vine": "🌿", "promo": "🏷️", "repricing": "💱", "issue": "⚠️"}
    if not ann.empty:
        ann["badge"] = ann["annotation_type"].map(lambda x: ANN_ICON.get(x, "📌"))
        ann_map = ann.groupby("sku").agg(
            badge=("badge", "first"), note=("note", " | ".join)).to_dict("index")
    else:
        ann_map = {}
    by_sku["ann_col"] = by_sku["norm_sku"].map(
        lambda s: ann_map.get(s, {}).get("badge", ""))
    by_sku["ann_note"] = by_sku["norm_sku"].map(
        lambda s: ann_map.get(s, {}).get("note", ""))

    by_sku = by_sku.sort_values("cm", ascending=False)

    # алерты: только РЕАЛЬНЫЕ проблемы (есть продажи и заметная выручка)
    MIN_REV_ALERT = 100   # € за период — ниже это хвост, не сигнал
    losers = by_sku[(by_sku["cm"] < 0) & (by_sku["units"] > 0)
                    & (by_sku["revenue"] >= MIN_REV_ALERT)]
    thin = by_sku[(by_sku["cm"] >= 0) & (by_sku["cm_pct"] < 5)
                  & (by_sku["revenue"] >= MIN_REV_ALERT * 5)]

    # предупреждения работают как фильтр: нажал — в таблице остались
    # только проблемные позиции, искать их глазами не нужно
    if "pnl_quick" not in st.session_state:
        st.session_state.pnl_quick = None

    def _pnl_toggle(key: str):
        st.session_state.pnl_quick = (
            None if st.session_state.pnl_quick == key else key)

    if not losers.empty or not thin.empty:
        al, ar = st.columns(2)
        if not losers.empty:
            with al:
                st.warning(t("money.alert.losers", 
                    n=len(losers), skus=", ".join(losers["sku_display"].head(5))))
                st.button(
                    t("money.alert.show_losers", n=len(losers)),
                    key="btn_losers", use_container_width=True,
                    type=("primary" if st.session_state.pnl_quick == "losers"
                          else "secondary"),
                    on_click=_pnl_toggle, args=("losers",))
        if not thin.empty:
            with ar:
                st.warning(t("money.alert.thin", 
                    n=len(thin), skus=", ".join(thin["sku_display"].head(5))))
                st.button(
                    t("money.alert.show_thin", n=len(thin)),
                    key="btn_thin", use_container_width=True,
                    type=("primary" if st.session_state.pnl_quick == "thin"
                          else "secondary"),
                    on_click=_pnl_toggle, args=("thin",))

    # ---------- Waterfall: как выручка превращается в прибыль ----------
    st.markdown(f"**{t('money.waterfall_title')}**")
    wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=[t("money.wf.revenue"), t("money.wf.fees"), t("money.wf.cogs"),
           t("money.wf.ads"), t("money.wf.cm")],
        y=[tot_rev, -(tot_rev - tot_net), -tot_cogs, -tot_ads, 0],
        text=[f"{tot_rev:,.0f}€", f"−{tot_rev - tot_net:,.0f}€",
              f"−{tot_cogs:,.0f}€", f"−{tot_ads:,.0f}€", f"{cm:,.0f}€"],
        textposition="outside",
        connector={"line": {"color": "#9aa4b2"}},
        decreasing={"marker": {"color": ACCENT}},
        increasing={"marker": {"color": GREEN}},
        totals={"marker": {"color": GREEN if cm >= 0 else ACCENT}},
    ))
    wf.update_layout(height=380, showlegend=False,
                     margin=dict(l=10, r=10, t=10, b=10),
                     yaxis_title="€")
    st.plotly_chart(wf, use_container_width=True)
    st.caption(t("money.waterfall_caption"))

    st.markdown(f"**{t('money.pnl_table')}**")

    _quick = st.session_state.pnl_quick
    if _quick == "losers":
        by_sku = by_sku[by_sku["sku_display"].isin(losers["sku_display"])]
        st.caption(t("money.alert.filtered_losers", n=len(by_sku)))
    elif _quick == "thin":
        by_sku = by_sku[by_sku["sku_display"].isin(thin["sku_display"])]
        st.caption(t("money.alert.filtered_thin", n=len(by_sku)))

    st.dataframe(
        by_sku[["photo", "flag_col", "ann_col", "sku_display", "product_name",
                "markets_label", "units", "revenue",
                "net_proceeds", "cogs", "commission", "ads", "cm", "cm_pct", "acos_pct",
                "rank_now", "rank_delta", "amazon_url"]],
        use_container_width=True, height=480, hide_index=True,
        column_config={
            "photo": catalog.image_column(),
            "flag_col": st.column_config.TextColumn(t("money.col.flag"), width="small",
                help=t("money.col.flag_help")),
            "ann_col": st.column_config.TextColumn(t("money.col.ann"), width="small",
                help=t("money.col.ann_help")),
            "sku_display": st.column_config.TextColumn("SKU", width="small"),
            "product_name": st.column_config.TextColumn(t("money.col.product"), width="medium"),
            "markets_label": st.column_config.TextColumn(
                t("money.col.markets"), width="small",
                help=t("money.col.markets_help")),
            "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €",
                help=t("money.col.net_help")),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €",
                help=t("money.col.cogs_help")),
            "commission": st.column_config.NumberColumn(
                t("money.col.commission"), format="%.0f €",
                help=t("money.col.commission_help")),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €",
                help=t("money.col.cm_help")),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
            "acos_pct": st.column_config.NumberColumn("ACOS", format="%.1f%%",
                help=t("money.col.acos_help")),
            "rank_now": st.column_config.NumberColumn(
                t("money.col.bsr"), format="%d", width="small",
                help=t("money.col.bsr_help")),
            "rank_delta": st.column_config.NumberColumn(
                t("money.col.bsr_delta"), format="%+d", width="medium",
                help=t("money.col.bsr_delta_help")),
            "amazon_url": st.column_config.LinkColumn(
                "ASIN", display_text=r"/dp/([A-Z0-9]{10})", width="small",
                help=t("money.col.asin_help")),
        },
    )
    st.caption(t("money.legend"))
    # подсказку в заголовке колонки Streamlit прячет за знаком вопроса, и его
    # не замечают — то же самое повторяем текстом там, где на него смотрят
    st.caption(t("money.bsr_legend"))
    st.caption(t("money.pnl_note"))

    st.download_button(
        t("money.download"),
        by_sku.to_csv(index=False).encode("utf-8-sig"),
        file_name="pnl_by_sku.csv", mime="text/csv",
    )

# ---------- по маркетплейсам ----------
with tab_country:
    by_c = (f.groupby("marketplace", as_index=False)
              .agg(units=("units", "sum"), revenue=("revenue", "sum"),
                   net_proceeds=("net_proceeds", "sum"),
                   cogs=("cogs_total", lambda x: x.sum(min_count=1)),
                   commission=("commission", lambda x: x.sum(min_count=1)),
                   ads=("ads", "sum")))
    by_c["cm"] = by_c["net_proceeds"] - by_c["cogs"] - by_c["ads"]
    by_c["cm_pct"] = np.round(safe_div(by_c["cm"], by_c["revenue"]) * 100, 1)
    by_c = by_c.sort_values("cm", ascending=False)

    cc = st.columns(min(len(by_c), 5) or 1)
    for i, (_, r) in enumerate(by_c.iterrows()):
        with cc[i % len(cc)]:
            st.metric(r["marketplace"],
                     "—" if pd.isna(r["cm"]) else f"{r['cm']:,.0f} €",
                     delta=None if pd.isna(r["cm"]) else f"{r['cm_pct']:.0f}%",
                     help=(t("money.kpi.cogs_missing") if pd.isna(r["cm"])
                           else t("money.country_metric_help")))

    melt = by_c.melt(id_vars="marketplace",
                     value_vars=["cm", "cogs", "ads"],
                     var_name="part", value_name="eur")
    part_names = {"cm": t("money.col.cm"), "cogs": "COGS", "ads": t("money.col.ads")}
    melt["part"] = melt["part"].map(part_names)
    fig = px.bar(melt, x="marketplace", y="eur", color="part",
                 title=t("money.marketplace_chart"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT])
    fig.update_layout(height=380, xaxis_title=None, yaxis_title="€",
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_c[["marketplace", "units", "revenue", "net_proceeds", "cogs",
              "commission", "ads", "cm", "cm_pct"]],
        use_container_width=True, hide_index=True,
        column_config={
            "marketplace": st.column_config.TextColumn(t("money.col.marketplace")),
            "units": st.column_config.NumberColumn(t("money.col.units")),
            "revenue": st.column_config.NumberColumn(t("money.col.revenue"), format="%.0f €"),
            "net_proceeds": st.column_config.NumberColumn(t("money.col.net"), format="%.0f €"),
            "cogs": st.column_config.NumberColumn("COGS", format="%.0f €"),
            "commission": st.column_config.NumberColumn(
                t("money.col.commission"), format="%.0f €",
                help=t("money.col.commission_help")),
            "ads": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
            "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €"),
            "cm_pct": st.column_config.NumberColumn(t("money.col.cm_pct"), format="%.1f%%"),
        },
    )

# ---------- комиссии/структура ----------
with tab_fees:
    st.markdown(f"**{t('money.struct_title')}**")
    total_rev = f["revenue"].sum()
    # Комиссии в круге ровно один раз — куском «Комиссии маркетплейса».
    # Отдельного куска «Комиссия площадки» здесь нет: у LM это то же самое
    # поле, и вторым сегментом те же деньги посчитались бы дважды.
    # Как справочная величина комиссия осталась колонкой в таблицах ниже
    parts = pd.DataFrame({
        "part": [t("money.col.cm"), "COGS", t("money.col.ads"),
                 t("money.struct.fees")],
        "value": [max(cm, 0), 0 if pd.isna(tot_cogs) else tot_cogs, tot_ads,
                  f["fees"].sum()],
    })
    parts = parts[parts["value"] > 0]
    fig = px.pie(parts, names="part", values="value", hole=0.5,
                 title=t("money.struct_pie_title"),
                 color_discrete_sequence=[GREEN, "#9aa4b2", ACCENT, "#f2b134"])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    # справочно: сколько из этих комиссий приходится на комиссию площадки.
    # Отдельным куском в круге её нет — это те же деньги, что и «Комиссии
    # маркетплейса», просто у Mirakl они приходят одним понятным полем
    if not pd.isna(tot_comm) and tot_comm > 0:
        st.caption(t("money.struct.commission_note", 
            v=f"{tot_comm:,.0f}"))

    fee_share = (f.groupby("marketplace", as_index=False)
                   .agg(revenue=("revenue", "sum"), fees=("fees", "sum")))
    fee_share["fees_pct"] = np.round(safe_div(fee_share["fees"], fee_share["revenue"]) * 100, 1)
    fig = px.bar(fee_share.sort_values("fees_pct", ascending=False),
                 x="marketplace", y="fees_pct", text="fees_pct",
                 title=t("money.fees_by_marketplace"), color_discrete_sequence=["#f2b134"])
    fig.update_traces(texttemplate="%{text:.0f}%")
    fig.update_layout(height=340, xaxis_title=None, yaxis_title=t("money.fees_axis"),
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(t("money.pnl_note"))

# ---------- рекламные алерты ----------
with tab_alerts:
    @st.cache_data(ttl=600)
    def load_ads_alerts():
        """Алерты по рекламе за все окна сразу.

        Таблица считается загрузчиком по трём окнам, и строк в ней три
        сотни — тянуть их одним запросом дешевле, чем ходить в базу на
        каждое переключение периода."""
        conn = get_connection()
        try:
            return pd.read_sql("""
                SELECT sku, marketplace, alert_type, window_days,
                       units, ads_spend, cm, net_proceeds, cogs_total,
                       cogs_per_unit, days_with_sales, days_ads_only,
                       calc_date
                FROM kabinet_data.ads_alerts
                WHERE calc_date = (SELECT MAX(calc_date)
                                   FROM kabinet_data.ads_alerts)
                ORDER BY CASE alert_type
                    WHEN 'zero_sales' THEN 0
                    WHEN 'negative_cm' THEN 1
                    ELSE 2 END,
                    ads_spend DESC NULLS LAST
            """, conn)
        except Exception:
            return pd.DataFrame()
        finally:
            conn.close()

    def alert_details(row) -> str:
        """Фраза для колонки «Детали», собранная из чисел.

        Раньше текст приходил готовым из базы и оставался русским в
        английском интерфейсе — язык жил вне i18n, и починить это
        переводом было нельзя. Теперь загрузчик отдаёт числа, а фразу
        собирает страница: тип алерта и есть ключ перевода."""
        def _n(v, dec=0, unit=""):
            # Знак валюты внутри форматирования, а не в шаблоне фразы:
            # иначе у отсутствующего числа получалось «— €», и прочерк
            # читался как «ноль евро», хотя значения просто нет
            v = pd.to_numeric(v, errors="coerce")
            if pd.isna(v):
                return "—"
            return (f"{v:,.{dec}f}".replace(",", "\u00a0") + unit)
        return t("money.alerts.details." + str(row["alert_type"])).format(
            days=_n(row.get("window_days")),
            units=_n(row.get("units")),
            ads=_n(row.get("ads_spend"), 2, " €"),
            cm=_n(row.get("cm"), 2, " €"),
            net=_n(row.get("net_proceeds"), 2, " €"),
            cogs=_n(row.get("cogs_total"), 2, " €"),
            cogs_unit=_n(row.get("cogs_per_unit"), 2, " €"),
            sale_days=_n(row.get("days_with_sales")),
            ad_days=_n(row.get("days_ads_only")))

    alerts = load_ads_alerts()

    # ---- окно ----
    # Список окон берём из данных, а не из кода: загрузчик заведёт
    # четвёртое — оно появится само. Период страницы в фиксированное окно
    # ложится не всегда: «этот месяц» и свой диапазон — произвольной
    # длины, поэтому берём ближайшее и говорим, какое именно показано
    _wins = (sorted(int(w) for w in
                    pd.to_numeric(alerts["window_days"], errors="coerce")
                      .dropna().unique())
             if not alerts.empty and "window_days" in alerts.columns else [])
    _win = None
    if _wins:
        _win = min(_wins, key=lambda w: (abs(w - PERIOD.days), w))
        alerts = alerts[pd.to_numeric(alerts["window_days"],
                                      errors="coerce") == _win]

    _cd = (pd.to_datetime(alerts["calc_date"], errors="coerce").max()
           if not alerts.empty and "calc_date" in alerts.columns else pd.NaT)
    _cd_s = _cd.strftime("%d.%m.%Y") if pd.notna(_cd) else "—"
    if _win is None:
        st.caption(t("money.alerts.snapshot", d=_cd_s))
    elif _win == PERIOD.days:
        st.caption(t("money.alerts.window_exact", n=_win, d=_cd_s))
    else:
        # окно не совпало с выбранным периодом — называем оба, иначе
        # цифры молча относятся не к тому отрезку, что стоит сверху
        st.caption(t("money.alerts.window_near", 
            n=_win, p=PERIOD.title, d=_cd_s,
            all=" / ".join(str(w) for w in _wins)))

    # применяем те же фильтры, что и ко всей странице
    if not alerts.empty:
        if mp_filter and alerts["marketplace"].notna().any():
            alerts = alerts[alerts["marketplace"].isin(mp_filter)]
        if search:
            alerts = alerts[alerts["sku"].astype(str)
                            .str.contains(search, case=False, na=False)]
    if alerts.empty:
        st.success(t("money.alerts.none"))
    else:
        alerts["sku_display"] = alerts["sku"].apply(clean_sku)
        TYPE_LABEL = {
            "zero_sales": t("money.alerts.zero"),
            "negative_cm": t("money.alerts.negcm"),
            "wasted_days": t("money.alerts.wasted"),
        }
        alerts["type_label"] = alerts["alert_type"].map(TYPE_LABEL)

        z = alerts[alerts["alert_type"] == "zero_sales"]
        n = alerts[alerts["alert_type"] == "negative_cm"]
        w = alerts[alerts["alert_type"] == "wasted_days"]

        a1, a2, a3 = st.columns(3)
        a1.metric(t("money.alerts.zero"), len(z),
                  delta=f"−{z['ads_spend'].sum():,.0f} €" if len(z) else None,
                  delta_color="inverse", help=t("money.alerts.zero_help"))
        a2.metric(t("money.alerts.negcm"), len(n),
                  delta=f"{n['cm'].sum():,.0f} €" if len(n) else None,
                  delta_color="inverse")
        a3.metric(t("money.alerts.wasted"), len(w))

        alerts = alerts.copy()
        alerts["details"] = [alert_details(r) for _, r in alerts.iterrows()]
        alerts["asin_url"] = catalog.url_series(
            skus=alerts["sku_display"], markets=alerts["marketplace"])
        alerts["photo"] = catalog.image_series(
            skus=alerts["sku_display"], markets=alerts["marketplace"])
        st.dataframe(
            alerts[["photo", "type_label", "sku_display", "asin_url",
                    "marketplace",
                    "units", "ads_spend", "cm", "details"]],
            use_container_width=True, height=480, hide_index=True,
            column_config={
                "photo": catalog.image_column(),
                "type_label": st.column_config.TextColumn(t("money.alerts.col_type"), width="small"),
                "sku_display": st.column_config.TextColumn("SKU", width="small"),
                "asin_url": catalog.asin_column(),
                "marketplace": st.column_config.TextColumn(
                    t("money.col.marketplace"), width="small"),
                "units": st.column_config.NumberColumn(t("money.col.units"), width="small"),
                "ads_spend": st.column_config.NumberColumn(t("money.col.ads"), format="%.0f €"),
                "cm": st.column_config.NumberColumn(t("money.col.cm"), format="%.0f €"),
                "details": st.column_config.TextColumn(t("money.alerts.col_details"), width="large"),
            },
        )
        st.caption(t("money.alerts.note"))
        st.caption(t("money.alerts.window_note"))
