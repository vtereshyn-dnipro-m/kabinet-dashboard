# ad_ratios.py — ACOS и TACOS по формулам Дарины (Power BI), один расчёт на «Рекламу» и «Обзор»
"""ACOS = расход на ВСЮ рекламу (SP + SB + SD) / продажи с рекламы (SP + SB + SD).
TACOS = весь расход на рекламу / все продажи С НДС.

Формулы прислала Дарина 05.10.2026 — так считает её Power BI. Сентябрь 2026 по всем каналам:
ACOS 28,0 % у обоих, TACOS 9,6 % против её 9 % (в её знаменателе ещё Wallapop и сайт, 446 €,
которых в Кабинете нет).

Источники — день × рынок, а не SKU: продажи с рекламы у SB есть только по КУПЛЕННОМУ ASIN, и в
`ads_spend` (строка = SKU) их нет. Расход и продажи с рекламы — `v_ads_market_daily_eur` (пишет
Economics Loader, ячейка 3b), все продажи с НДС — `v_sales_vat_incl_daily` (Amazon — витрина Sales &
Traffic, Mirakl — строки заказов с НДС). Порог окупаемости кампаний на «Рекламе» — другое число:
он считается от маржи, и этот модуль его не касается.

Пустой знаменатель — None, а не ноль и не бесконечность: «рекламы не было» и «продаж не было» —
разные ответы, и страница говорит их словами.
"""
from datetime import date

import pandas as pd

from db.connection import get_connection

SQL = """
    WITH a AS (SELECT SUM(spend) AS spend, SUM(ad_sales) AS ad_sales
               FROM kabinet_data.v_ads_market_daily_eur
               WHERE date BETWEEN %(a)s AND %(b)s {mk}),
         s AS (SELECT SUM(sales_vat_incl) AS sales_vat_incl
               FROM kabinet_data.v_sales_vat_incl_daily
               WHERE date BETWEEN %(a)s AND %(b)s {mk})
    SELECT a.spend::float, a.ad_sales::float, s.sales_vat_incl::float FROM a, s
"""


def load(d_from: date, d_to: date, markets: tuple = ()) -> dict:
    """Расход, продажи с рекламы, все продажи с НДС, ACOS и TACOS за период.

    `markets` — коды рынков как в экономике (ES, GB, MM_ES …); пусто — все каналы, как у Дарины."""
    mk = "AND marketplace = ANY(%(mk)s)" if markets else ""
    conn = get_connection()
    try:
        df = pd.read_sql(SQL.format(mk=mk), conn,
                         params={"a": d_from, "b": d_to, "mk": list(markets)})
    finally:
        conn.close()
    spend, ad_sales, sales = (None if pd.isna(v) else float(v) for v in df.iloc[0])
    return {
        "spend": spend, "ad_sales": ad_sales, "sales_vat_incl": sales,
        "acos": (spend / ad_sales * 100) if spend is not None and ad_sales else None,
        "tacos": (spend / sales * 100) if spend is not None and sales else None,
    }
