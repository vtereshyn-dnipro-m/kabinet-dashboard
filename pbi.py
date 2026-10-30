# pbi.py — цифры «как в Power BI» (решение владельца 08.10.2026)
"""Кабинет показывает ТЕ ЖЕ цифры, что Power BI «Marketplaces Report», по всем денежным метрикам.

Источник один — `kabinet_data.pbi_spiderweb_report`, реплика витрины Power BI
`dnipro_m.v_all_marketplaces_spiderweb_report` (джоба Kabinet - Power BI Replica, 12:45 и 16:45 Kyiv). Модель
Power BI — Import, DAX в ней почти нет: каждая карточка отчёта — прямая сумма колонки витрины. Поэтому и здесь
никакой своей арифметики, только суммы колонок и отношения сумм — те же, что у карточек Power BI:

    Revenue VAT Incl / Excl        sum(sales_vat_incl) / sum(sales_vat_excl)
    Units Sold                     sum(units_sold)
    Contribution Profit            sum(contribution_profit)          = profit − spend в каждой строке витрины
    % Contribution Margin          Contribution Profit / Revenue VAT Incl (или Excl)
    Expenses                       sum(expenses)                     = комиссии + себестоимость + доставка + упаковка
    Quantity Refund                sum(quantity_refund)
    Expenses Refund                sum(cogs_refund − shipping_cost_refund − expenses_refund)
    Spend / Paid Sales / Paid Units  sum(spend) / sum(paid_sales) / sum(paid_units)
    ACOS / TACOS                   Spend / Paid Sales, Spend / Revenue VAT Incl

Тождество витрины (проверено по всем строкам с 01.08.2026): profit = sales_vat_excl − expenses + cogs_refund −
shipping_cost_refund − expenses_refund + reimbursment, поэтому разложение Contribution Profit на слагаемые
сходится с ним до цента без единой своей поправки.

Наша методика маржи (себестоимость только годных возвратов, фактические комиссии Amazon, промо и удержания из
выплат, фактический НДС, реклама Leroy Merlin) не удалена: таблицы и код на месте, страницы просто её не
показывают. Вернуть — `OWN_METHOD = True`; разбор методик пойдёт отдельным документом.
"""
import re
from datetime import date

import pandas as pd

from db.connection import get_connection
from util import as_text

OWN_METHOD = False          # True — страницы показывают прежнюю методику Кабинета вместо цифр Power BI
SOURCE = "kabinet_data.pbi_spiderweb_report"

# Площадки витрины, чьи строки страницы показывают только при включённом флаге (30.10.2026, вариант (а) владельца).
# Worten вошёл в витрину Power BI (PR #407), а на «Обзор» он — только после сверки заказов с кабинетом Worten, за флагом
# worten_overview_enabled (решение владельца 28.10.2026). Без этого первый же прогон реплики добавил бы Worten в итоги
# «Обзора» и «Денег» мимо флага. Отбор — по площадке витрины (pbi_marketplace), а не по коду рынка: так же работает и
# с кодом «?Worten/Portugal», который давала реплика до своего кода Worten. Нет строки флага — строки скрыты. Реплика
# и сверка (Kabinet - Reconciliation) по-прежнему держат все строки витрины: скрываем только на страницах.
GATED = {"Worten": "worten_overview_enabled"}


def _gate() -> str:
    """Условие WHERE: строки площадок из GATED — только при флаге = 1. Флаг читает сам запрос — без отдельного
    обращения к базе и без кеша, который пережил бы переключение."""
    # IS DISTINCT FROM, а не «NOT (… = …)»: строка с пустой площадкой иначе дала бы NULL и пропала со страниц
    return "".join(
        f" AND (pbi_marketplace IS DISTINCT FROM '{mk}' OR COALESCE((SELECT value FROM kabinet_data.reorder_params"
        f" WHERE key = '{flag}'), 0) = 1)" for mk, flag in GATED.items())


# суммы по дню × рынку: всё, что нужно карточкам и графикам
DAILY_SQL = f"""
    SELECT date AS sales_date, marketplace, pbi_marketplace AS platform, pbi_country AS country,
           SUM(units_sold)                                   AS units,
           SUM(quantity_refund)                              AS units_refunded,
           SUM(sales_vat_incl)                               AS sales_vat_incl,
           SUM(sales_vat_excl)                               AS sales_vat_excl,
           SUM(commission_fee_vat_excl + cancel_commission_vat_excl) AS commission,
           SUM(cogs_total)                                   AS cogs,
           SUM(shipping_cost_total + packing_cost_total)     AS logistics,
           SUM(expenses)                                     AS expenses,
           SUM(cogs_refund - shipping_cost_refund - expenses_refund) AS expenses_refund,
           SUM(reimbursment)                                 AS reimbursment,
           SUM(refund_total_vat_excl)                        AS refund_vat_excl,
           SUM(spend)                                        AS spend,
           SUM(paid_sales)                                   AS paid_sales,
           SUM(paid_units)                                   AS paid_units,
           SUM(tax_amount)                                   AS tax,
           SUM(profit)                                       AS profit,
           SUM(contribution_profit)                          AS cp
    FROM {SOURCE}
    WHERE date BETWEEN %(a)s AND %(b)s {{mk}}{_gate()}
    GROUP BY 1, 2, 3, 4
"""


def _mk(markets) -> str:
    return "AND marketplace = ANY(%(mk)s)" if markets else ""


def load_daily(d_from: date, d_to: date, markets: tuple = ()) -> pd.DataFrame:
    """День × рынок за период. `markets` — коды Кабинета (ES, GB, LM, MM_ES…); пусто — все каналы, как в Power BI."""
    conn = get_connection()
    try:
        df = pd.read_sql(DAILY_SQL.format(mk=_mk(markets)), conn,
                         params={"a": d_from, "b": d_to, "mk": list(markets)})
    finally:
        conn.close()
    if not df.empty:
        df["sales_date"] = pd.to_datetime(df["sales_date"])
    return df


def totals(df: pd.DataFrame) -> dict:
    """Карточки отчёта Power BI из сумм дня × рынка: те же формулы, что у его карточек (см. шапку модуля)."""
    s = {c: float(pd.to_numeric(df[c], errors="coerce").fillna(0).sum()) if c in df else 0.0
         for c in ("units", "units_refunded", "sales_vat_incl", "sales_vat_excl", "commission", "cogs", "logistics",
                   "expenses", "expenses_refund", "reimbursment", "refund_vat_excl", "spend", "paid_sales",
                   "paid_units", "tax", "profit", "cp")}
    s["cm_pct_incl"] = s["cp"] / s["sales_vat_incl"] * 100 if s["sales_vat_incl"] else None
    s["cm_pct_excl"] = s["cp"] / s["sales_vat_excl"] * 100 if s["sales_vat_excl"] else None
    s["avg_price_incl"] = s["sales_vat_incl"] / s["units"] if s["units"] else None
    s["acos"] = s["spend"] / s["paid_sales"] * 100 if s["paid_sales"] else None
    s["tacos"] = s["spend"] / s["sales_vat_incl"] * 100 if s["sales_vat_incl"] else None
    # всё, что витрина добавляет к прибыли сверх «выручка − расходы»: себестоимость и доставка возвратов, их
    # комиссии и компенсации Amazon. Отдельной строкой — чтобы карточки складывались в Contribution Profit
    s["returns_other"] = s["profit"] - (s["sales_vat_excl"] - s["expenses"])
    return s


SKU_SQL = f"""
    SELECT sku, marketplace, pbi_marketplace AS platform, pbi_country AS country, date AS sales_date,
           SUM(units_sold) AS units, SUM(quantity_refund) AS units_refunded, SUM(tax_amount) AS tax,
           SUM(sales_vat_incl) AS sales_vat_incl, SUM(sales_vat_excl) AS sales_vat_excl,
           SUM(commission_fee_vat_excl + cancel_commission_vat_excl) AS commission,
           SUM(cogs_total) AS cogs, SUM(shipping_cost_total + packing_cost_total) AS logistics,
           SUM(expenses) AS expenses,
           SUM(cogs_refund - shipping_cost_refund - expenses_refund) AS expenses_refund,
           SUM(reimbursment) AS reimbursment,
           SUM(spend) AS spend, SUM(paid_sales) AS paid_sales, SUM(paid_units) AS paid_units,
           SUM(profit) AS profit, SUM(contribution_profit) AS cp
    FROM {SOURCE}
    WHERE date BETWEEN %(a)s AND %(b)s {{mk}}{_gate()}
    GROUP BY 1, 2, 3, 4, 5
"""


def load_sku(d_from: date, d_to: date, markets: tuple = ()) -> pd.DataFrame:
    """SKU × рынок × день за период — для таблиц по товарам."""
    conn = get_connection()
    try:
        df = pd.read_sql(SKU_SQL.format(mk=_mk(markets)), conn,
                         params={"a": d_from, "b": d_to, "mk": list(markets)})
    finally:
        conn.close()
    if not df.empty:
        df["sales_date"] = pd.to_datetime(df["sales_date"])
    return df


ORDERS_SQL = f"""
    SELECT purchase_date AS sales_date, marketplace, pbi_marketplace AS platform, pbi_country AS country,
           COUNT(*)                     AS orders,
           SUM(order_total_amount_eur)  AS order_total,
           SUM(unique_sku_ordered)      AS unique_skus
    FROM kabinet_data.pbi_orders_report
    WHERE purchase_date BETWEEN %(a)s AND %(b)s {{mk}}{_gate()}
    GROUP BY 1, 2, 3, 4
"""


def load_orders(d_from: date, d_to: date, markets: tuple = ()) -> pd.DataFrame:
    """Заказы как в Power BI (его таблица заказов): Orders Count = число заказов, Average Order Value = сумма заказов /
    их число, Average Basket Depth = среднее число разных SKU в заказе. В модели Power BI заказы связаны с продажами
    только через календарь (дата × страна × площадка) — разреза по категории и SKU у них нет."""
    conn = get_connection()
    try:
        df = pd.read_sql(ORDERS_SQL.format(mk=_mk(markets)), conn,
                         params={"a": d_from, "b": d_to, "mk": list(markets)})
    finally:
        conn.close()
    if not df.empty:
        df["sales_date"] = pd.to_datetime(df["sales_date"])
    return df


def order_totals(df: pd.DataFrame) -> dict:
    n = float(df["orders"].sum()) if not df.empty else 0.0
    return {"orders": n,
            "aov": float(df["order_total"].sum()) / n if n else None,
            "basket_depth": float(df["unique_skus"].sum()) / n if n else None}


def load_categories() -> pd.DataFrame:
    """SKU → название и категории, как в Power BI (его справочник v_sku_names_categories). SKU без кода в дереве ERP
    там получает название «Need to Name» и категорию «Set» — так и показываем, чтобы разрез сходился с Power BI."""
    conn = get_connection()
    try:
        return pd.read_sql("""SELECT sku, name_en, name_ukr, category_level1_en, category_level2_en, category_level3_en
                              FROM kabinet_data.pbi_sku_categories""", conn)
    finally:
        conn.close()


COUNTRY_SQL = f"""
    SELECT pbi_country AS country, pbi_marketplace AS platform,
           SUM(units_sold) AS units, SUM(sales_vat_incl) AS sales_vat_incl, SUM(sales_vat_excl) AS sales_vat_excl,
           SUM(contribution_profit) AS cp,
           SUM(quantity_refund) AS units_refunded, SUM(refund_total_vat_incl) AS refund_vat_incl,
           SUM(spend) AS spend, SUM(packing_cost_total) AS packing, SUM(shipping_cost_total) AS shipping,
           SUM(cancel_commission_vat_excl) AS cancel_commission, SUM(expenses) AS expenses
    FROM {SOURCE}
    WHERE date BETWEEN %(a)s AND %(b)s{_gate()}
    GROUP BY 1, 2
"""


def load_countries(d_from: date, d_to: date) -> pd.DataFrame:
    """Страна × площадка за период — таблица стран Power BI («Spain» = Amazon, Leroy Merlin, ManoMano, Carrefour,
    Wallapop и сайт вместе). Страна — как в витрине, по-английски; подпись на языке интерфейса — `country_names`."""
    conn = get_connection()
    try:
        return pd.read_sql(COUNTRY_SQL, conn, params={"a": d_from, "b": d_to})
    finally:
        conn.close()


def country_names() -> dict:
    """Страна витрины (английское название) → {"code": alpha2, "ru": …, "uk": …, "en": …}. Витрина пишет страну
    словом, а подписи на трёх языках лежат в country_names по коду — связываем через справочник стран."""
    conn = get_connection()
    try:
        df = pd.read_sql("""SELECT c.name, c.alpha2, n.name_ru, n.name_uk, n.name_en
                            FROM kabinet_data.countries c
                            LEFT JOIN kabinet_data.country_names n ON n.alpha2 = c.alpha2""", conn)
    finally:
        conn.close()
    return {str(r["name"]).strip().lower(): {"code": r["alpha2"], "ru": r["name_ru"], "uk": r["name_uk"],
                                             "en": r["name_en"]} for _, r in df.iterrows()}


def country_label(name, lang: str, names: dict) -> str:
    """Подпись страны витрины на языке интерфейса; не нашлась в справочнике — как в витрине."""
    raw = "" if name is None or (isinstance(name, float) and pd.isna(name)) else str(name).strip()
    v = names.get(raw.lower(), {}).get(lang)
    return v if isinstance(v, str) and v else raw


def last_date() -> pd.Timestamp:
    """Последний день с данными в реплике и время последней загрузки."""
    conn = get_connection()
    try:
        r = pd.read_sql(f"SELECT max(date) AS d, max(loaded_at) AS l FROM {SOURCE}", conn).iloc[0]
    finally:
        conn.close()
    return pd.Timestamp(r["d"]) if pd.notna(r["d"]) else pd.NaT


# ── Свежесть реплики (14.10.2026) ────────────────────────────────────────────────────────────────────────
# Реплика запускается по записи в витрину Amazon (~10:20), а экран Power BI тянет витрину сам около 10:35–11:45 —
# поэтому Кабинет утром «впереди» экрана, а днём ещё и с дневными заказами Leroy Merlin, ManoMano и Carrefour
# (их часть витрины считается на лету). Строка под карточками называет обе вещи; если витрина собралась неполной,
# реплика её не копирует (nb/pbi_spiderweb_replica.py), и страница говорит, на какой момент показаны цифры.
def replica_meta():
    """(последний прогон, последняя полная замена) из kabinet_data.pbi_replica_meta; таблицы нет — (None, None)."""
    import streamlit as st

    @st.cache_data(ttl=300, show_spinner=False)
    def _load():
        conn = get_connection()
        try:
            last = pd.read_sql("""SELECT status, source_built_at, shown_as_of, loaded_at, detail, pbi_refresh_until
                                  FROM kabinet_data.pbi_replica_meta ORDER BY loaded_at DESC LIMIT 1""", conn)
            good = pd.read_sql("""SELECT source_built_at, loaded_at FROM kabinet_data.pbi_replica_meta
                                  WHERE status = 'replaced' ORDER BY loaded_at DESC LIMIT 1""", conn)
            amz = pd.read_sql("""SELECT DISTINCT marketplace FROM kabinet_data.pbi_spiderweb_report
                                 WHERE pbi_marketplace = 'Amazon'""", conn)["marketplace"]
            last_d = last.iloc[0].to_dict() if len(last) else None
            if last_d is not None:
                last_d["amazon_codes"] = set(amz)
            return (last_d, good.iloc[0].to_dict() if len(good) else None)
        except Exception:
            return None, None
        finally:
            conn.close()
    return _load()


def _kyiv(v, fmt="%d.%m %H:%M") -> str:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "—"
    ts = pd.Timestamp(v)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert("Europe/Kyiv").strftime(fmt)


def freshness_line() -> str:
    """«Данные на 14.10 10:21. В Power BI цифры обновятся до ~11:45 — до этого там могут быть вчерашние.» (текст
    владельца 14.10.2026). Время Power BI — оценка по журналу доступа (pbi_refresh_until, пишет реплика); вторая фраза
    только сегодня и только до этого времени — после него она ничего не объясняет. Пусто, пока не было ни одной
    полной замены (таблицы ещё нет)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from i18n import t
    last, good = replica_meta()
    if OWN_METHOD or not good:
        return ""
    built = good.get("source_built_at") or good.get("loaded_at")
    line = t("pbi.fresh_line", built=_kyiv(built))
    until = as_text((last or {}).get("pbi_refresh_until"))
    now = datetime.now(ZoneInfo("Europe/Kyiv"))
    if re.fullmatch(r"\d\d:\d\d", until) and _kyiv(built, "%Y-%m-%d") == now.strftime("%Y-%m-%d") \
            and now.strftime("%H:%M") < until:
        line += " " + t("pbi.fresh_pbi", until=until)
    return line


def incomplete_text() -> str:
    """Текст плашки, если последний прогон оставил прежнюю реплику (витрина собралась неполной); иначе пусто."""
    from i18n import t
    last, good = replica_meta()
    if OWN_METHOD or not last or last.get("status") != "kept":
        return ""
    # Текст плашки — решение владельца 14.10.2026: без причин и без слова «бот». «Amazon» — только если неполными
    # вышли одни рынки Amazon (код рынка в начале каждой части detail: «ES: было …; IT: …»); упал канал
    # Mirakl, Wallapop или сайт — без названия площадки, иначе плашка назвала бы не того. Какие коды — Amazon, говорит
    # сама реплика (pbi_marketplace), а не длина кода: у Leroy Merlin код тоже из двух букв (LM).
    codes = re.findall(r"(?:^|;\s*)([A-Z_]+):", as_text(last.get("detail")))
    amz = last.get("amazon_codes") or set()
    key = "pbi.incomplete_amz" if codes and all(c in amz for c in codes) else "pbi.incomplete"
    return t(key, at=_kyiv((good or {}).get("loaded_at") or last.get("shown_as_of")))


def built_at_text() -> str:
    """Время сборки витрины Amazon, на которой стоят цифры, — для подсказки ⓘ в паспорте данных."""
    _, good = replica_meta()
    return _kyiv((good or {}).get("source_built_at")) if good else ""
