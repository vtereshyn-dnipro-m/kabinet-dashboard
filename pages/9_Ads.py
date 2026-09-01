# pages/9_Ads.py — Реклама: что отключить и куда добавить
"""Страница отвечает на один вопрос, а не показывает одиннадцать
наборов данных.

Витрина заставляет человека считать самому: вот расход, вот продажи,
дальше сам. Инструмент выносит вывод наверх, а числа оставляет как
обоснование. Поэтому колонка «Действие» стоит в таблице кампаний, а
справочные разрезы свёрнуты внизу — к ним обращаются раз в месяц.
"""
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from db.connection import get_connection
from i18n import init_lang, t
from util import as_text
import period as period_mod
import catalog
from links import MARKETPLACE_ID, amazon_url, market_name

init_lang()

# Оба порога заданы вручную и ни на чём не основаны, кроме привычки.
# ACOS сам по себе не значит ничего без маржи: при марже 20 % убыточен и
# ACOS 22 %, при марже 45 % нормален и 32 %. Экономика ASIN в Кабинете
# есть, и считать порог надо от неё — пока не связано, на экране стоит
# подпись «задан вручную», чтобы его не приняли за расчётный
ACOS_TARGET = 25.0
# Граница между «не те запросы» и «карточка не продаёт». Ниже неё людям
# показываются, но не кликают — проблема до клика; выше кликают, но не
# покупают — проблема после.
#
# Число выставлено по разобранному вручную примеру: SP-Manual-Auto-B2B
# с охватом 11 032 и шестьюдесятью кликами (0,54 %) должен читаться как
# проблема таргетинга. Это калибровка по одному случаю, а не norm по
# рынку, — если начнёт помечать «сузить таргетинг» слишком многих,
# двигать надо здесь
CTR_MIN = 0.6

# Адрес Listing Suite для действия «проверить листинг». Пока пусто —
# ссылка ведёт на саму карточку Amazon: проверять листинг можно и там,
# а мёртвая кнопка хуже живой, но не той
LISTING_SUITE_URL = ""

# Атрибуция AMC закрывается 14 дней, но основная масса покупок доезжает
# за трое суток. Кампания, запущенная вчера, попадёт в no_sales не
# потому что плохая, а потому что покупки ещё не случились
PRELIM_DAYS = 3

PLOTLY_CFG = {"displayModeBar": False}
# Часы приходят в UTC, а решения принимают по местному времени. Сдвигать
# на +2 нельзя: летом это +2, зимой +1, и константа тихо разъедется в
# последнее воскресенье октября — зона знает про переход, число не знает
LOCAL_TZ = ZoneInfo("Europe/Madrid")

MASKED = "__MASKED__"
ASIN_RE = re.compile(r"^B0[A-Z0-9]{8}$")
# В названиях кампаний ASIN обычно стоит в конце: ...-B0DFWVNRWB.
# Оттуда его и берём — другого способа связать кампанию с товаром в
# attribution нет
CAMP_ASIN_RE = re.compile(r"B0[A-Z0-9]{8}")

RED, AMBER, GREEN, GREY = "#e8484d", "#f0a500", "#2e9e5b", "#8a94a6"
BLUE = "#1f77b4"

# ── Контракт по колонкам ────────────────────────────────────────────
# Часть имён названа в ТЗ прямо (campaign_status, reach, acos_pct,
# ntb_rate_pct), часть выведена по смыслу. Держим их одним списком:
# если загрузчик назвал колонку иначе, страница не гадает и не падает —
# она говорит, каких колонок не хватает и какие есть, и правится одной
# строкой здесь
NEED = {
    "v_amc_attribution": ["report_date", "campaign_id", "campaign_name",
                          "campaign_status", "spend", "sales_14d", "clicks",
                          "purchases_14d", "acos_pct", "reach", "impressions"],
    "amc_ntb_by_asin": ["report_date", "asin", "total_purchases",
                        "ntb_purchases", "total_sales", "ntb_rate_pct"],
    "amc_search_terms": ["report_date", "customer_search_term",
                         "unique_buyers", "sales"],
    "amc_dayparting": ["report_date", "hour_utc", "purchases"],
    "amc_overlap": ["ad_type_1", "ad_type_2", "overlap_users"],
}

# Технические поля загрузки. На экран не идут: инстанс и id рынка ничего
# не говорят тому, кто ведёт кампании, а loaded_at — время записи, а не
# дата данных, и путать их дороже, чем не показывать
SERVICE = ("loaded_at", "instance_id", "amazon_marketplace_id")

# Рынок различается по инстансу AMC. Пока он один, но резать данные
# нужно уже по нему: когда появятся Германия и Италия, поменяется только
# подпись
MK_COL = "amazon_marketplace_id"


@st.cache_data(ttl=600)
def load_amc(table: str) -> tuple:
    """Таблица AMC целиком и текст ошибки, если запрос не прошёл.

    Ошибку возвращаем, а не глотаем. Первый же прогон показал, зачем:
    вью не оказалось в схеме, запрос упал, пустой ответ дошёл до экрана
    как «данных нет» — и выглядело это так, будто не отработал
    загрузчик, хотя данные лежали на месте. Молчаливый except здесь
    стоит дороже любой некрасивой строки на экране.

    SELECT * намеренно: перечислять колонки значит гадать их имена
    внутри SQL, где ошибка роняет запрос целиком."""
    conn = get_connection()
    try:
        return pd.read_sql(f"SELECT * FROM kabinet_data.{table}", conn), ""
    except Exception as e:
        return pd.DataFrame(), f"{type(e).__name__}: {e}".strip()
    finally:
        conn.close()


@st.cache_data(ttl=600)
def amc_objects() -> list:
    """Что вообще лежит в схеме с именем amc. Без этого списка разбор
    «почему пусто» превращается в переписку: видно только то, чего нет,
    и не видно того, что есть."""
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'kabinet_data'
              AND table_name LIKE '%%amc%%'
            ORDER BY 1
        """, conn)
        return df["table_name"].astype(str).tolist()
    except Exception:
        return []
    finally:
        conn.close()


def load_first(*names) -> tuple:
    """Первый существующий источник из перечисленных.

    Действия считаются по campaign_status, а он живёт во вью. Если вью
    нет, берём базовую таблицу: карточки и суммы соберутся и по ней, а
    чего именно не хватит — скажет проверка колонок."""
    errs = []
    for n in names:
        df, err = load_amc(n)
        if not df.empty:
            return df, n, ""
        errs.append(f"{n} — {err or '0 строк'}")
    return pd.DataFrame(), names[0], "; ".join(errs)


def missing(df: pd.DataFrame, table: str) -> list:
    return [c for c in NEED.get(table, []) if c not in df.columns]


def contract_error(df: pd.DataFrame, table: str) -> bool:
    """Экран несоответствия схемы. Показывает и чего не хватает, и что
    есть: без второго списка правка превращается в переписку."""
    miss = missing(df, table)
    if not miss:
        return False
    st.error(t("ads.err.columns", 
        table=table, miss=", ".join(miss),
        have=", ".join(map(str, df.columns)) or "—"))
    return True


def campaign_asins(campaign_name) -> list:
    """Все ASIN из названия кампании, а не первый попавшийся.

    В названиях их бывает несколько: SB-кампания на три товара так и
    подписана — ...-B0DFWVNRWB-B0FNRR3H51-B0FNX5JNKJ. Показывать из
    троих один значит соврать о том, что рекламируется."""
    seen, out = set(), []
    for a in CAMP_ASIN_RE.findall(as_text(campaign_name).upper()):
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def asin_link(asin: str) -> str:
    """Куда вести по ASIN.

    Здесь AMC и Listing Suite сходятся: AMC говорит «сюда идёт платный
    трафик и не покупают», Suite отвечает «вот что не так с карточкой».
    Пока адрес Suite не задан, ведём на саму карточку Amazon — проверить
    листинг можно и там, а ссылка в никуда хуже ссылки не туда."""
    if LISTING_SUITE_URL:
        return LISTING_SUITE_URL.rstrip("/") + "/" + asin
    code = MARKETPLACE_ID.get(_markets[0]) if _markets else None
    return amazon_url(code or "ES", asin)


def listing_url(campaign_name) -> str:
    """Ссылка действия «проверить листинг» — по первому товару кампании.
    ASIN в названии нет — ссылки не будет вовсе."""
    a = campaign_asins(campaign_name)
    return asin_link(a[0]) if a else ""


def money(v, dec=0) -> str:
    v = pd.to_numeric(v, errors="coerce")
    return "—" if pd.isna(v) else f"{v:,.{dec}f}".replace(",", " ") + " €"


def card(col, label: str, base: str, value: str, tone: str = "") -> None:
    """Карточка с обязательной второй строкой.

    Без периода и базы сравнения цифра — загадка: «продажи 384 €» за
    какой срок и по какой атрибуции. Поэтому base не необязателен."""
    bg = {"bad": "rgba(232,72,77,0.10)", "good": "rgba(46,158,91,0.10)"}.get(tone, "")
    bd = {"bad": RED, "good": GREEN}.get(tone, "rgba(128,128,128,0.28)")
    col.markdown(
        f'<div style="border:1px solid {bd};border-radius:12px;padding:12px 16px;'
        f'background:{bg};height:100%">'
        f'<div style="font-size:0.82rem;font-weight:600">{label}</div>'
        f'<div style="font-size:0.72rem;color:var(--text-secondary);'
        f'line-height:1.3;margin-bottom:6px">{base}</div>'
        f'<div style="font-size:1.6rem;font-weight:700">{value}</div></div>',
        unsafe_allow_html=True)


st.title(t("ads.title"))
st.caption(t("ads.subtitle"))

attr, ATTR_SRC, _err = load_first("v_amc_attribution", "amc_attribution")
if attr.empty:
    st.error(t("ads.err.load", 
        e=_err or "—", have=", ".join(amc_objects()) or "—"))
    st.stop()
if ATTR_SRC != "v_amc_attribution":
    # Вью считает campaign_status, roas и acos_pct. Без него это придётся
    # считать здесь, а логика в двух местах однажды разойдётся — поэтому
    # не считаем, а говорим
    st.warning(t("ads.err.no_view", src=ATTR_SRC))
if contract_error(attr, "v_amc_attribution"):
    st.stop()

attr["report_date"] = pd.to_datetime(attr["report_date"], errors="coerce")
_markets = (sorted({str(m) for m in attr[MK_COL].dropna().unique()})
            if MK_COL in attr.columns else [])

# ---- свежесть загрузки ----
# amc_run_log — внешняя точка контроля: если job молчит, таблицы просто
# перестают пополняться, и без этой проверки страница показывает старое
# как свежее
_log = load_amc("amc_run_log")[0]
if not _log.empty:
    _dcol = next((c for c in ("finished_at", "started_at", "run_at", "calc_date")
                  if c in _log.columns), None)
    if _dcol:
        _last = pd.to_datetime(_log[_dcol], errors="coerce").max()
        _age = (pd.Timestamp.now() - _last).days if pd.notna(_last) else None
        if _age is not None and _age >= 2:
            st.warning(t("ads.stale", n=_age))

# ---- фильтры ----
f1, f2, f3 = st.columns([2, 2, 2])
PERIOD = period_mod.control(columns=(f1, f2), key="ads_period")
with f3:
    if len(_markets) > 1:
        _mk = st.multiselect(t("ads.filter.market"), options=_markets,
                             format_func=market_name,
                             placeholder=t("ads.filter.market_all"),
                             key="ads_mk")
    else:
        # Селектор с единственным пунктом — обманка: выглядит выбором,
        # которого нет. Показываем значение подписью, а место под
        # настоящий селектор останется, когда инстансов станет больше
        _mk = []
        st.caption(t("ads.filter.market_one", 
            m=market_name(_markets[0]) if _markets else "—"))

# ---- предварительные дни ----
_today = pd.Timestamp.today().normalize()
_closed_to = _today - pd.Timedelta(days=PRELIM_DAYS)
show_prelim = st.toggle(t("ads.prelim.toggle", n=PRELIM_DAYS),
                        value=False, key="ads_prelim")
_from, _to = PERIOD.start, PERIOD.end
if not show_prelim:
    _to = min(_to, _closed_to)

st.markdown(f"""
<div style="border:1px solid rgba(240,165,0,0.45);border-left:3px solid {AMBER};
            border-radius:10px;padding:10px 16px;margin:10px 0 6px 0;
            background:rgba(240,165,0,0.08);font-size:0.92rem;">
{t("ads.limits", m=", ".join(market_name(m) for m in _markets) or "—")}
</div>
""", unsafe_allow_html=True)
st.caption(t("ads.prelim.on", n=PRELIM_DAYS) if show_prelim
           else t("ads.prelim.off", 
               n=PRELIM_DAYS, d=_to.strftime("%d.%m.%Y")))


def scope(df: pd.DataFrame) -> pd.DataFrame:
    """Один и тот же отбор для всех блоков страницы.

    Разъехавшийся фильтр — первое, что ломает сверку карточек с
    таблицей, поэтому период и рынок режутся в одном месте."""
    if df.empty or "report_date" not in df.columns:
        return df
    d = pd.to_datetime(df["report_date"], errors="coerce")
    out = df[(d >= _from) & (d <= _to)]
    if _mk and MK_COL in out.columns:
        out = out[out[MK_COL].astype(str).isin(_mk)]
    return out.copy()


A = scope(attr)
for c in ("spend", "sales_14d", "clicks", "purchases_14d",
          "acos_pct", "reach", "impressions"):
    if c in A.columns:
        A[c] = pd.to_numeric(A[c], errors="coerce")

if A.empty:
    # Границы имеющихся данных в сообщении обязательны: без них «за этот
    # период данных нет» неотличимо от «загрузчик умер», и человек идёт
    # чинить то, что работает
    _dd = pd.to_datetime(attr["report_date"], errors="coerce").dropna()
    st.info(t("ads.empty.period_range", 
        a=_dd.min().strftime("%d.%m.%Y") if len(_dd) else "—",
        b=_dd.max().strftime("%d.%m.%Y") if len(_dd) else "—",
        f=_from.strftime("%d.%m.%Y"), to=_to.strftime("%d.%m.%Y")))
    st.stop()

# ═══════════════════════════════════════════════════════════════════
# КАРТОЧКИ
# ═══════════════════════════════════════════════════════════════════
_spend, _sales = A["spend"].sum(), A["sales_14d"].sum()
_days = max((_to - _from).days + 1, 1)
_acos = (_spend / _sales * 100) if _sales > 0 else np.inf

ntb = scope(load_amc("amc_ntb_by_asin")[0])
_ntb_share, _ntb_buys = np.nan, np.nan
if not ntb.empty and {"total_purchases", "ntb_rate_pct"} <= set(ntb.columns):
    if "ntb_purchases" in ntb.columns:
        _ntb_buys = float(pd.to_numeric(ntb["ntb_purchases"],
                                        errors="coerce").fillna(0).sum())
    _o = pd.to_numeric(ntb["total_purchases"], errors="coerce").fillna(0)
    _r = pd.to_numeric(ntb["ntb_rate_pct"], errors="coerce")
    if _r.max() is not np.nan and (_r > 100).any():
        # ntb_rate_pct считается в источнике; больше 100 быть не может
        st.error(t("ads.err.ntb_over100"))
    if _o.sum() > 0:
        _ntb_share = float((_o * _r).sum() / _o.sum())

# Пятая карточка — стоимость привода нового покупателя. 97 % покупок
# делают те, кто бренд ещё не знал: главный вопрос тут не «какой ACOS»,
# а «сколько стоит привести человека». Если она выше маржи с первой
# покупки, а повторных нет, разговор не про ставки вообще
_cac = (_spend / _ntb_buys) if (_ntb_buys and _ntb_buys > 0) else np.nan
c1, c2, c3, c4, c5 = st.columns(5)
card(c1, "ACOS", t("ads.card.acos_manual", n=f"{ACOS_TARGET:.0f}"),
     "∞" if np.isinf(_acos) else f"{_acos:.0f} %",
     "bad" if (np.isinf(_acos) or _acos > ACOS_TARGET) else "good")
card(c2, t("ads.card.spend"), t("ads.card.spend_base", n=_days),
     money(_spend))
card(c3, t("ads.card.sales"), t("ads.card.sales_base"), money(_sales))
card(c4, t("ads.card.ntb"), t("ads.card.ntb_base"),
     "—" if pd.isna(_ntb_share) else f"{_ntb_share:.0f} %")
card(c5, t("ads.card.cac"), t("ads.card.cac_base"),
     "—" if pd.isna(_cac) else money(_cac, 2))

# ═══════════════════════════════════════════════════════════════════
# КАМПАНИИ
# ═══════════════════════════════════════════════════════════════════
st.markdown(f"### {t('ads.camp.title')}")

# Скрытые строки отделяем ДО группировки. У них нет ни campaign_id, ни
# названия — Amazon убирает и то и другое, оставляя суммы. В общей
# группировке они схлопывались в никуда, и строка «скрыто Amazon»
# пропадала с экрана, хотя её продажи оставались в карточках: итог по
# таблице переставал сходиться, а объяснить это было нечем
_st_raw = A["campaign_status"].astype(str).str.strip()
M = A[_st_raw == "masked"]
V = A[_st_raw != "masked"].copy()

# Группируем по кампании, а НЕ по (кампания, статус). Статус во вью
# считается на каждый день, поэтому кампания с разными статусами по дням
# распадалась на несколько строк — одна и та же кампания встречалась в
# таблице дважды с разными числами
C = (V.groupby("campaign_id", as_index=False, dropna=False)
      .agg(campaign_name=("campaign_name", "first"),
           spend=("spend", "sum"), sales=("sales_14d", "sum"),
           clicks=("clicks", "sum"), orders=("purchases_14d", "sum"),
           impressions=("impressions", "sum"),
           days=("report_date", "nunique"),
           reach=("reach", lambda x: x.sum(min_count=1)),
           statuses=("campaign_status", lambda x: set(map(str, x)))))
# ACOS считаем от сумм, а не усредняем дневные: среднее из процентов —
# не процент от суммы, и на кампании с одним дорогим днём расходится
# заметно
C["acos"] = np.where(C["sales"] > 0, C["spend"] / C["sales"] * 100, np.inf)
# CTR и CPC тоже считаем от сумм. Во вью они есть, но подневные: среднее
# из процентов не равно проценту от суммы, а на кампании с одним крупным
# днём разница видна невооружённым глазом
C["ctr"] = np.where(C["impressions"] > 0,
                    C["clicks"] / C["impressions"] * 100, np.nan)
C["cpc"] = np.where(C["clicks"] > 0, C["spend"] / C["clicks"], np.nan)
# Охват за несколько дней неизвестен: сумма уникальных пользователей по
# дням не равна числу уникальных за период. Пустое место честнее числа,
# которое выглядит точным и не является им
C.loc[C["days"] > 1, "reach"] = np.nan


def period_status(row) -> str:
    """Диагноз кампании за период.

    Действий три, а не два, потому что «клики есть, покупок нет» — не
    повод отключать. Реклама в этом случае сработала: человека нашли, он
    заинтересовался, кликнул, за клик заплатили. Ушёл он уже с карточки
    товара. Отключить кампанию значит вылечить симптом — тот же
    посетитель не купит и из органики, просто там это бесплатно и потому
    незаметно.

    Разделяем по CTR: не кликают при показах — проблема ДО клика, не те
    запросы; кликают и не покупают — проблема ПОСЛЕ клика, карточка.

    Статус за период сводится здесь, а не берётся из вью: там он
    посчитан на каждый день, а дневной ярлык не описывает месяц. Словарь
    статусов и правила — из ТЗ, место одно."""
    if row["clicks"] <= 0 and row["spend"] <= 0:
        return "no_traffic"          # ничего не тратит — в подвал
    if row["clicks"] <= 0:
        return "dead"                # тратит и не получает даже кликов
    if row["sales"] <= 0:
        # 1 800 кликов без единой покупки — это не про ставки. При
        # конверсии хотя бы 3 % они дали бы полсотни заказов
        return ("narrow" if (pd.notna(row["ctr"]) and row["ctr"] < CTR_MIN)
                else "listing")
    if row["acos"] > ACOS_TARGET:
        return "high_acos"
    return "ok"


C["status"] = C.apply(period_status, axis=1)
_masked = M
_quiet = C[C["status"] == "no_traffic"]
_live = C[C["status"] != "no_traffic"].copy()

# Диагноз → действие и цвет. Красное только там, где деньги уходят и не
# возвращается ничего: остальное — работа, а не выключатель
ACTION = {"dead": ("ads.act.off", RED),
          "listing": ("ads.act.listing", AMBER),
          "narrow": ("ads.act.narrow", AMBER),
          "high_acos": ("ads.act.lower", AMBER),
          "ok": ("ads.act.keep", GREY)}
# Сортировка по величине потерь, а не по расходу и не по алфавиту:
# сверху то, где деньги утекают быстрее. Расход без продаж — потеря
# целиком, расход при высоком ACOS — та часть, что выше порога
_live["loss"] = np.where(
    _live["sales"] > 0,
    np.maximum(_live["spend"] - _live["sales"] * ACOS_TARGET / 100, 0),
    _live["spend"])
_live = _live.sort_values("loss", ascending=False)

if _live.empty and _masked.empty:
    st.info(t("ads.camp.all_masked") if not _quiet.empty
            else t("ads.empty.period"))
else:
    rows = []
    for _, r in _live.iterrows():
        key, colr = ACTION.get(r["status"], ("ads.act.keep", GREY))
        rows.append({
            "name": str(r["campaign_name"]),
            # В подстроке показы, а не охват. Охват честно пуст на любом
            # окне длиннее суток — сумма уникальных по дням не равна
            # числу уникальных, — и «охват —» стояло в каждой строке.
            # Подпись, которая всегда прочерк, приучает не читать строку
            "sub": t("ads.camp.sub",
                     c=int(r["clicks"] or 0), o=int(r["orders"] or 0),
                     i="—" if pd.isna(r["impressions"])
                       else f"{int(r['impressions']):,}".replace(",", " ")),
            "asins": campaign_asins(r["campaign_name"]),
            "spend": float(r["spend"] or 0),
            "sales": float(r["sales"] or 0),
            "acos": r["acos"],
            "ctr": r["ctr"], "cpc": r["cpc"],
            "act": t(key), "act_color": colr,
            "act_url": listing_url(r["campaign_name"])
                       if r["status"] == "listing" else "",
        })
    tbl = pd.DataFrame(rows)

    def _cell(v, colr, bold=False):
        return (f'<span style="color:{colr};font-weight:{600 if bold else 400}">'
                f'{v}</span>')

    html = ['<table style="width:100%;border-collapse:collapse;font-size:0.9rem">',
            f'<tr style="text-align:left;color:var(--text-secondary);'
            f'font-size:0.78rem"><th style="padding:6px 8px">{t("ads.camp.col_name")}</th>'
            f'<th style="padding:6px 8px;text-align:right">{t("ads.camp.col_spend")}</th>'
            f'<th style="padding:6px 8px;text-align:right">ACOS</th>'
            f'<th style="padding:6px 8px">{t("ads.camp.col_action")}</th></tr>']
    for _, r in tbl.iterrows():
        acos_txt = "∞" if np.isinf(r["acos"]) else f'{r["acos"]:.0f} %'
        acos_col = RED if (np.isinf(r["acos"]) or r["acos"] > ACOS_TARGET) else GREEN
        # CTR красим по своему порогу: он отвечает на другой вопрос, чем
        # ACOS, — не «дорого ли», а «доходит ли до карточки хоть кто-то»
        ctr_txt = ("—" if pd.isna(r["ctr"])
                   else _cell(f'{r["ctr"]:.2f} %',
                              AMBER if r["ctr"] < CTR_MIN else GREY))
        cpc_txt = "—" if pd.isna(r["cpc"]) else money(r["cpc"], 2)
        # ASIN из названия — рядом со строкой, а не только у действия:
        # посмотреть товар хочется по любой кампании, а не лишь по той,
        # где мы советуем проверить карточку
        asin_html = ""
        if r["asins"]:
            asin_html = " · " + " ".join(
                f'<a href="{asin_link(a)}" target="_blank" '
                f'style="color:{BLUE};text-decoration:none">{a}</a>'
                for a in r["asins"][:3])
            if len(r["asins"]) > 3:
                asin_html += f' +{len(r["asins"]) - 3}'
        act_html = _cell(r["act"], r["act_color"], True)
        if r["act_url"]:
            act_html = (f'<a href="{r["act_url"]}" target="_blank" '
                        f'style="color:{r["act_color"]};font-weight:600">'
                        f'{r["act"]} ↗</a>')
        html.append(
            '<tr style="border-top:1px solid rgba(128,128,128,0.18)">'
            f'<td style="padding:8px">{r["name"]}<div style="font-size:0.74rem;'
            f'color:var(--text-secondary)">{r["sub"]}</div></td>'
            f'<td style="padding:8px;text-align:right">{money(r["spend"])}</td>'
            f'<td style="padding:8px;text-align:right">{_cell(acos_txt, acos_col, True)}</td>'
            f'<td style="padding:8px">{_cell(r["act"], r["act_color"], True)}</td></tr>')
    if not _masked.empty:
        _ms, _mv = _masked["spend"].sum(), _masked["sales_14d"].sum()
        _ma = f"{_ms / _mv * 100:.0f} %" if _mv > 0 else "∞"
        html.append(
            '<tr style="border-top:1px solid rgba(128,128,128,0.18);'
            'font-style:italic;color:var(--text-secondary)">'
            f'<td style="padding:8px">{t("ads.camp.masked")}</td>'
            f'<td style="padding:8px;text-align:right">{money(_ms)}</td>'
            f'<td style="padding:8px;text-align:right">{money(_mv)}</td>'
            '<td style="padding:8px;text-align:right">—</td>'
            '<td style="padding:8px;text-align:right">—</td>'
            f'<td style="padding:8px;text-align:right">{_ma}</td>'
            '<td style="padding:8px">—</td></tr>')
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.caption(t("ads.camp.three_actions"))
    if not _masked.empty:
        st.caption(t("ads.camp.masked_note"))
    st.caption(t("ads.camp.thresholds", 
        a=f"{ACOS_TARGET:.0f}", c=f"{CTR_MIN:.1f}"))

# Кампании без кликов — по строке на каждую пустоту. Одиннадцать пустых
# строк вытесняют вниз то, ради чего таблицу открывают
if not _quiet.empty:
    with st.expander(t("ads.camp.quiet", 
            n=len(_quiet), s=money(_quiet["spend"].sum()))):
        st.dataframe(_quiet[["campaign_name", "spend", "clicks"]],
                     use_container_width=True, hide_index=True,
                     column_config={
                         "campaign_name": st.column_config.TextColumn(
                             t("ads.camp.col_name"), width="large"),
                         "spend": st.column_config.NumberColumn(
                             t("ads.camp.col_spend"), format="%.2f €"),
                         "clicks": st.column_config.NumberColumn(
                             t("ads.camp.col_clicks"), width="small"),
                     })

# ═══════════════════════════════════════════════════════════════════
# ТОВАРЫ
# ═══════════════════════════════════════════════════════════════════
st.markdown(f"### {t('ads.asin.title')}")
if ntb.empty:
    st.info(t("ads.empty.period"))
elif not contract_error(ntb, "amc_ntb_by_asin"):
    ntb = ntb.copy()
    for c in ("total_purchases", "total_sales", "ntb_rate_pct"):
        ntb[c] = pd.to_numeric(ntb[c], errors="coerce")
    G = (ntb.groupby("asin", as_index=False)
            .agg(orders=("total_purchases", "sum"),
                 sales=("total_sales", "sum"),
                 ntb=("ntb_rate_pct", "mean")))
    _m = G[G["asin"].astype(str) == MASKED]
    G = G[G["asin"].astype(str) != MASKED].sort_values("sales", ascending=False)
    if G.empty and _m.empty:
        st.info(t("ads.empty.period"))
    else:
        G["url"] = catalog.url_series(asins=G["asin"], markets=_markets[:1] * len(G)
                                      if _markets else None)
        G["photo"] = catalog.image_series(asins=G["asin"])
        st.dataframe(
            G[["photo", "url", "orders", "ntb", "sales"]],
            use_container_width=True, hide_index=True,
            column_config={
                "photo": catalog.image_column(),
                "url": catalog.asin_column(),
                "orders": st.column_config.NumberColumn(
                    t("ads.asin.col_orders"), width="small"),
                "ntb": st.column_config.NumberColumn(
                    t("ads.asin.col_ntb"), format="%.0f%%",
                    help=t("ads.asin.col_ntb_help")),
                "sales": st.column_config.NumberColumn(
                    t("ads.asin.col_sales"), format="%.2f €"),
            })
        # Скрытые заказы — не шум, а большинство: по первому прогону 39
        # из 49. Без этой строки сумма по таблице вдвое меньше реальной
        if not _m.empty:
            st.markdown(
                f'<div style="font-style:italic;color:var(--text-secondary);'
                f'font-size:0.9rem;padding:4px 8px">{t("ads.asin.masked")} · '
                f'{int(_m["orders"].sum())} · {money(_m["sales"].sum(), 2)} · —</div>',
                unsafe_allow_html=True)
            st.caption(t("ads.asin.masked_note"))

# ═══════════════════════════════════════════════════════════════════
# СПРАВОЧНЫЕ РАЗРЕЗЫ
# ═══════════════════════════════════════════════════════════════════
st.divider()
st.caption(t("ads.ref.note"))

with st.expander(t("ads.ref.dayparting"), expanded=True):
    _d = scope(load_amc("amc_dayparting")[0]).drop(columns=list(SERVICE),
                                                   errors="ignore")
    if _d.empty:
        st.info(t("ads.empty.period"))
    elif not contract_error(_d, "amc_dayparting"):
        # Час считаем через зону, а не прибавлением двойки: дата у строки
        # есть, значит переход на зимнее время учтётся сам
        _ts = (pd.to_datetime(_d["report_date"], errors="coerce")
               + pd.to_timedelta(pd.to_numeric(_d["hour_utc"],
                                               errors="coerce").fillna(0),
                                 unit="h"))
        _d["hour"] = (_ts.dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
                        .dt.hour)
        _h = (_d.groupby("hour", as_index=False)["purchases"].sum()
                .set_index("hour").reindex(range(24), fill_value=0)
                .reset_index())
        _h["purchases"] = pd.to_numeric(_h["purchases"],
                                        errors="coerce").fillna(0)
        fig = px.bar(_h, x="hour", y="purchases",
                     color_discrete_sequence=[GREEN])
        fig.update_xaxes(dtick=1, title=None,
                         tickmode="array", tickvals=list(range(24)))
        fig.update_yaxes(title=None)
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        st.caption(t("ads.ref.hours_local"))
        if st.toggle(t("ads.ref.numbers"), key="amc_hours_tbl"):
            st.dataframe(_d.drop(columns=["hour"], errors="ignore"),
                         use_container_width=True, hide_index=True)

with st.expander(t("ads.ref.terms"), expanded=True):
    S = scope(load_amc("amc_search_terms")[0])
    if S.empty:
        st.info(t("ads.empty.period"))
    elif not contract_error(S, "amc_search_terms"):
        S = S.copy()
        for c in ("unique_buyers", "sales"):
            S[c] = pd.to_numeric(S[c], errors="coerce")
        T = (S.groupby("customer_search_term", as_index=False)
              .agg(customers=("unique_buyers", "sum"), sales=("sales", "sum"))
              .rename(columns={"customer_search_term": "search_term"}))
        _tm = T[T["search_term"].astype(str) == MASKED]
        T = T[T["search_term"].astype(str) != MASKED].copy()
        # Средний чек важнее самих продаж: одинаковый спрос при разнице
        # в чеке втрое — это и есть решение о приоритетах
        T["avg"] = np.where(T["customers"] > 0, T["sales"] / T["customers"], np.nan)
        _is_asin = T["search_term"].astype(str).str.upper().str.match(ASIN_RE)

        def _terms_bars(df):
            """Полосы вместо таблицы: длина сразу показывает, во что
            упирается спрос, а средний чек остаётся подписью на полосе —
            он важнее самих продаж и должен читаться без второго
            взгляда."""
            top = df.sort_values("sales", ascending=False).head(10)
            if top.empty:
                return
            top = top.sort_values("sales")
            top["label"] = [f"{v:,.0f} €".replace(",", " ") +
                            (f"  ·  {a:,.0f} € "
                             .replace(",", " ") + t("ads.terms.per_buyer")
                             if pd.notna(a) else "")
                            for v, a in zip(top["sales"], top["avg"])]
            fig = px.bar(top, x="sales", y="search_term", orientation="h",
                         text="label", color_discrete_sequence=[GREEN])
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_xaxes(title=None, showticklabels=False,
                             range=[0, float(top["sales"].max()) * 1.45])
            fig.update_yaxes(title=None)
            fig.update_layout(height=max(220, 34 * len(top)),
                              margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

        def _terms_table(df, key, as_asin=False):
            """Таблица запросов. Когда запрос — это ASIN, он становится
            ссылкой: сырой код в ячейке ничем не помогает, а по нему как
            раз и хочется посмотреть, что за товар ищут по артикулу."""
            top = df.sort_values("sales", ascending=False).head(10).copy()
            if as_asin:
                _code = MARKETPLACE_ID.get(_markets[0]) if _markets else None
                top["search_term"] = [
                    amazon_url(_code or "ES", a) for a in top["search_term"]]
            st.dataframe(
                top[["search_term", "customers", "sales", "avg"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "search_term": (catalog.asin_column(
                        t("ads.terms.col_term")) if as_asin
                        else st.column_config.TextColumn(
                            t("ads.terms.col_term"), width="large")),
                    "customers": st.column_config.NumberColumn(
                        t("ads.terms.col_customers"), width="small"),
                    "sales": st.column_config.NumberColumn(
                        t("ads.terms.col_sales"), format="%.0f €"),
                    "avg": st.column_config.NumberColumn(
                        t("ads.terms.col_avg"), format="%.0f €",
                        help=t("ads.terms.col_avg_help")),
                }, key=key)

        st.markdown(f"**{t('ads.terms.top')}**")
        _terms_bars(T[~_is_asin])
        if _is_asin.any():
            # Поиск по коду товара — другое поведение: человек пришёл с
            # другой площадки или сравнивает цену. Смешивать со
            # смысловыми запросами значит усреднять разные намерения
            st.markdown(f"**{t('ads.terms.asins')}**")
            st.caption(t("ads.terms.asins_note"))
            _terms_bars(T[_is_asin])
        # Скрытое в полосы не мешаем: это не запрос, а сумма по всем, что
        # не прошли порог, — рядом с настоящими запросами такая полоса
        # читалась бы как самый популярный из них
        if not _tm.empty:
            st.caption(t("ads.terms.masked", 
                s=money(_tm["sales"].sum()),
                p=f'{_tm["sales"].sum() / max(_tm["sales"].sum() + T["sales"].sum(), 1) * 100:.0f}'))
        st.caption(t("ads.terms.no_acos"))
        if st.toggle(t("ads.ref.numbers"), key="amc_terms_tbl"):
            _terms_table(T[~_is_asin], "amc_terms_words")
            if _is_asin.any():
                _terms_table(T[_is_asin], "amc_terms_asins")

with st.expander(t("ads.ref.overlap"), expanded=True):
    _o = scope(load_amc("amc_overlap")[0]).drop(columns=list(SERVICE),
                                                errors="ignore")
    if _o.empty:
        st.info(t("ads.empty.period"))
    elif not contract_error(_o, "amc_overlap"):
        # График на одну строку — это рамка вокруг числа. Фразой короче
        # и понятнее
        _ov = (_o.groupby(["ad_type_1", "ad_type_2"], as_index=False)
                 ["overlap_users"].max())
        for _, r in _ov.iterrows():
            st.markdown(t("ads.ref.overlap_line", 
                n=f"{int(r['overlap_users']):,}".replace(",", " "),
                a=r["ad_type_1"], b=r["ad_type_2"]))
        st.caption(t("ads.ref.overlap_note"))
        if st.toggle(t("ads.ref.numbers"), key="amc_overlap_tbl"):
            st.dataframe(_o, use_container_width=True, hide_index=True)
