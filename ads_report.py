# ads_report.py — раздел «Реклама» по отчётам Amazon Ads API, все рынки (решения владельца 18.10.2026)
"""Запросы раздела: реальная стоимость рекламы, ACOS и TACOS по стране и кампании, пустые траты по поисковым
запросам, плейсменты, недействительный трафик. Источник — реплики в Lakebase (`Kabinet - Ads Replica`,
sql/ads_replica_2026-10-18.sql). Арифметика живёт здесь, на странице её нет.

    Расход           SP + SB + SD по кампаниям, все кампании — включая SB без товара, которых нет в Spend Power BI
    Сбор             регуляторный сбор Amazon Ads по дням (сбор счёта разнесён по дням пропорционально расходу)
    НДС              доля НДС в счетах профиля за год (ES 21 %, IT/FR/DE 0 — обратное начисление); к вычету, в маржу
                     не входит — показываем отдельно
    ACOS             расход / продажи с рекламы (SP — 14 дней атрибуции, SB и SD — как отдаёт кампания)
    TACOS            расход / все продажи Amazon страны с НДС (реплика Power BI, как карточка выше)
    Пустые траты     запросы с clicks ≥ SEARCH_MIN_CLICKS и 0 заказов за 30 дней — главная цифра; общая доля расхода
                     без заказов — мелко: большинство таких запросов набрали 1–2 клика
Суммы переводятся в евро функцией базы kabinet_data.to_eur (курс ЕЦБ на день), Британия — GB.
"""
from datetime import date

import pandas as pd

from db.connection import get_connection

SEARCH_DAYS = 30
SEARCH_MIN_CLICKS = 10      # решение владельца 18.10.2026: «10+ кликов и 0 заказов» — главная цифра пустых трат


def _read(sql: str, params: dict) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def _mk(countries) -> str:
    return "AND country = ANY(%(mk)s)" if countries else ""


def countries(d_from: date, d_to: date) -> list:
    """Страны, где за период был расход на рекламу."""
    df = _read("""SELECT country FROM kabinet_data.ads_campaign_daily
                  WHERE date BETWEEN %(a)s AND %(b)s GROUP BY 1 HAVING sum(cost) > 0
                  ORDER BY sum(cost) DESC""", {"a": d_from, "b": d_to})
    return df["country"].tolist()


def campaigns(d_from: date, d_to: date, mk: tuple = ()) -> pd.DataFrame:
    """Кампания × страна за период, суммы в евро."""
    return _read(f"""
        SELECT country, ad_product, campaign_id, max(campaign_name) AS campaign_name,
               max(campaign_status) AS campaign_status,
               sum(kabinet_data.to_eur(cost::float8, currency, date))  AS cost,
               sum(kabinet_data.to_eur(sales::float8, currency, date)) AS sales,
               sum(orders) AS orders, sum(clicks) AS clicks, sum(impressions) AS impressions
        FROM kabinet_data.ads_campaign_daily
        WHERE date BETWEEN %(a)s AND %(b)s {_mk(mk)}
        GROUP BY 1, 2, 3
        HAVING sum(cost) <> 0 OR sum(sales) <> 0""", {"a": d_from, "b": d_to, "mk": list(mk)})


def real_cost(d_from: date, d_to: date, mk: tuple = ()) -> pd.DataFrame:
    """По стране: расход, сбор, НДС из счетов и реальная стоимость (расход + сбор), всё в евро."""
    spend = _read(f"""
        SELECT country, sum(kabinet_data.to_eur(cost::float8, currency, date)) AS spend,
               sum(kabinet_data.to_eur(cost::float8, currency, date)) FILTER (WHERE ad_product = 'SP') AS sp,
               sum(kabinet_data.to_eur(cost::float8, currency, date)) FILTER (WHERE ad_product = 'SB') AS sb,
               sum(kabinet_data.to_eur(cost::float8, currency, date)) FILTER (WHERE ad_product = 'SD') AS sd
        FROM kabinet_data.ads_campaign_daily WHERE date BETWEEN %(a)s AND %(b)s {_mk(mk)} GROUP BY 1""",
                  {"a": d_from, "b": d_to, "mk": list(mk)})
    fee = _read(f"""
        SELECT profile_country AS country, sum(kabinet_data.to_eur(fee_amount::float8, currency, date)) AS fee
        FROM kabinet_data.ads_fees_daily
        WHERE date BETWEEN %(a)s AND %(b)s {"AND profile_country = ANY(%(mk)s)" if mk else ""} GROUP BY 1""",
                {"a": d_from, "b": d_to, "mk": list(mk)})
    # ставка НДС профиля — по счетам за год: в счёте amount_due без НДС и уже со сбором, tax_amount_due — НДС
    vat = _read("""
        SELECT profile_country AS country, sum(tax_amount_due) / NULLIF(sum(amount_due), 0) AS vat_rate
        FROM kabinet_data.ads_invoices WHERE to_date >= current_date - 365 AND amount_due > 0 GROUP BY 1""", {})
    df = spend.merge(fee, on="country", how="left").merge(vat, on="country", how="left")
    for c in ("spend", "sp", "sb", "sd", "fee", "vat_rate"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["real"] = df["spend"] + df["fee"]
    df["vat"] = df["real"] * df["vat_rate"]
    df["real_incl_vat"] = df["real"] + df["vat"]
    return df.sort_values("spend", ascending=False)


def sales_vat_incl(d_from: date, d_to: date, mk: tuple = ()) -> pd.DataFrame:
    """Все продажи Amazon страны с НДС (реплика Power BI) — знаменатель TACOS. У Amazon код рынка = код страны."""
    return _read(f"""
        SELECT marketplace AS country, sum(sales_vat_incl) AS sales_vat_incl
        FROM kabinet_data.pbi_spiderweb_report
        WHERE date BETWEEN %(a)s AND %(b)s AND pbi_marketplace = 'Amazon'
          {"AND marketplace = ANY(%(mk)s)" if mk else ""}
        GROUP BY 1""", {"a": d_from, "b": d_to, "mk": list(mk)})


def search_terms(mk: tuple = ()) -> tuple:
    """Поисковые запросы за последние SEARCH_DAYS дней с данными: (таблица запросов, сводка, конец окна).
    Окно считается от последнего дня в реплике, а не от «сегодня»: Amazon отдаёт запросы с задержкой."""
    end = _read(f"SELECT max(date) AS d FROM kabinet_data.ads_search_term_daily WHERE true {_mk(mk)}",
                {"mk": list(mk)})["d"].iloc[0]
    if end is None or pd.isna(end):
        return pd.DataFrame(), {}, None
    start = pd.Timestamp(end) - pd.Timedelta(days=SEARCH_DAYS - 1)
    df = _read(f"""
        SELECT country, ad_product, search_term, max(campaign_name) AS campaign_name,
               count(DISTINCT campaign_id) AS campaigns,
               sum(kabinet_data.to_eur(cost::float8, currency, date)) AS cost,
               sum(clicks) AS clicks, sum(impressions) AS impressions, sum(orders) AS orders,
               sum(kabinet_data.to_eur(sales::float8, currency, date)) AS sales
        FROM kabinet_data.ads_search_term_daily
        WHERE date BETWEEN %(a)s AND %(b)s {_mk(mk)}
        GROUP BY 1, 2, 3""", {"a": start.date(), "b": end, "mk": list(mk)})
    for c in ("cost", "clicks", "impressions", "orders", "sales"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    zero = df[(df["orders"] == 0) & (df["cost"] > 0)]
    hot = zero[zero["clicks"] >= SEARCH_MIN_CLICKS]
    s = {"start": start.date(), "end": end, "cost": float(df["cost"].sum()),
         "hot_cost": float(hot["cost"].sum()), "hot_n": int(len(hot)),
         "zero_cost": float(zero["cost"].sum()), "zero_n": int(len(zero)), "n": int(len(df)),
         "zero_small_n": int((zero["clicks"] <= 2).sum())}
    s["zero_pct"] = s["zero_cost"] / s["cost"] * 100 if s["cost"] else None
    return hot.sort_values("cost", ascending=False), s, end


def placements(d_from: date, d_to: date, mk: tuple = ()) -> pd.DataFrame:
    """SP по плейсментам: страна × место показа."""
    df = _read(f"""
        SELECT country, placement, sum(kabinet_data.to_eur(cost::float8, currency, date)) AS cost,
               sum(kabinet_data.to_eur(sales::float8, currency, date)) AS sales,
               sum(clicks) AS clicks, sum(impressions) AS impressions, sum(orders) AS orders
        FROM kabinet_data.ads_placement_daily
        WHERE date BETWEEN %(a)s AND %(b)s {_mk(mk)}
        GROUP BY 1, 2 HAVING sum(cost) <> 0 OR sum(sales) <> 0""", {"a": d_from, "b": d_to, "mk": list(mk)})
    for c in ("cost", "sales", "clicks", "impressions", "orders"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["acos"] = (df["cost"] / df["sales"].where(df["sales"] > 0) * 100)
    return df.sort_values(["country", "cost"], ascending=[True, False])


def invalid_traffic(d_from: date, d_to: date, mk: tuple = ()) -> pd.DataFrame:
    """Недействительный трафик: страна × тип рекламы. Amazon такие клики и показы не списывает."""
    df = _read(f"""
        SELECT country, ad_product, sum(gross_clicks) AS gross_clicks, sum(invalid_clicks) AS invalid_clicks,
               sum(gross_impressions) AS gross_impressions, sum(invalid_impressions) AS invalid_impressions
        FROM kabinet_data.ads_invalid_traffic_daily
        WHERE date BETWEEN %(a)s AND %(b)s {_mk(mk)}
        GROUP BY 1, 2 HAVING sum(gross_clicks) > 0""", {"a": d_from, "b": d_to, "mk": list(mk)})
    for c in ("gross_clicks", "invalid_clicks", "gross_impressions", "invalid_impressions"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["click_pct"] = df["invalid_clicks"] / df["gross_clicks"].where(df["gross_clicks"] > 0) * 100
    df["impr_pct"] = df["invalid_impressions"] / df["gross_impressions"].where(df["gross_impressions"] > 0) * 100
    return df.sort_values("gross_clicks", ascending=False)
