# plan_fact.py — факт против действующего прогноза по объектам реестра (ТЗ 010 §13)
"""Один расчёт на «Обзор» и «Деньги».

Объект прогноза — marketplace или пул (`v_forecast_current`), факт — продажи
`economics_summary` по кодам рынков объекта: у marketplace один код, у пула —
коды участников из `pool_members`. План месяца сравнивается с фактом только за
ту часть месяца, по которой есть данные: доля календарных дней (ТЗ §13 —
равномерное потребление, рабочие дни не подставляются). Поэтому ожидание —
это `план × дней_с_данными / дней_в_месяце`, а не весь план.

Факт здесь — по дате заказа (`sales_date`), а не отгрузки: страницы целиком
считаются на этой витрине, и второй, отгрузочный факт рядом с ней читался бы
как расхождение в данных. Отгрузочный факт по ТЗ применяется в алертах темпа
сторожа, где он и обязан быть.
"""
import calendar
from datetime import date

import pandas as pd

SQL = """
    WITH obj AS (
        SELECT DISTINCT object_type, object_id, object_name
        FROM kabinet_data.v_forecast_current
        WHERE month BETWEEN %(m0)s AND %(m1)s
    ),
    codes AS (
        SELECT o.object_type, o.object_id, upper(m.legacy_code) AS code
        FROM obj o JOIN kabinet_data.marketplaces_new m
               ON o.object_type = 'marketplace' AND m.id = o.object_id
        UNION ALL
        SELECT o.object_type, o.object_id, upper(m.legacy_code)
        FROM obj o JOIN kabinet_data.pool_members pm
               ON o.object_type = 'pool' AND pm.pool_id = o.object_id
             JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id
    ),
    plan AS (
        SELECT object_type, object_id, object_name, month,
               SUM(quantity)::int AS plan_units,
               SUM(COALESCE(forecast_revenue, quantity * target_price)) AS plan_rev,
               COUNT(*) FILTER (WHERE quantity > 0) AS plan_skus
        FROM kabinet_data.v_forecast_current
        WHERE month BETWEEN %(m0)s AND %(m1)s
        GROUP BY 1, 2, 3, 4
    ),
    fact AS (
        SELECT c.object_type, c.object_id,
               date_trunc('month', e.sales_date)::date AS month,
               SUM(e.units_ordered)::int    AS fact_units,
               SUM(e.net_product_sales)     AS fact_rev,
               MAX(e.sales_date)            AS data_through
        FROM kabinet_data.economics_summary e
        JOIN codes c ON c.code = CASE WHEN e.marketplace = 'GB' THEN 'CO.UK' ELSE e.marketplace END
        WHERE e.sales_date BETWEEN %(d0)s AND %(d1)s
        GROUP BY 1, 2, 3
    )
    SELECT p.object_type, p.object_id, p.object_name, p.month, p.plan_units, p.plan_rev, p.plan_skus,
           COALESCE(f.fact_units, 0) AS fact_units, COALESCE(f.fact_rev, 0) AS fact_rev, f.data_through
    FROM plan p LEFT JOIN fact f USING (object_type, object_id, month)
    ORDER BY p.object_name, p.month
"""


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def load(conn, d_from: date, d_to: date) -> pd.DataFrame:
    """Факт и план по месяцам объектов, попавших в период [d_from, d_to].

    Колонки: object_name, month, plan_units, plan_rev, plan_skus, fact_units,
    fact_rev, data_through, days_in_month, days_covered, expected_units,
    expected_rev. `days_covered` — календарных дней месяца внутри периода И не
    позже последней даты с данными: план за дни, по которым факта ещё нет,
    в ожидание не входит.
    """
    if d_from > d_to:
        return pd.DataFrame()
    df = pd.read_sql(SQL, conn, params={"m0": _month_start(d_from), "m1": _month_start(d_to),
                                        "d0": d_from, "d1": d_to})
    if df.empty:
        return df
    df["month"] = pd.to_datetime(df["month"]).dt.date
    df["data_through"] = pd.to_datetime(df["data_through"]).dt.date
    dim, cov = [], []
    for _, r in df.iterrows():
        m0, m1 = r["month"], _month_end(r["month"])
        lo, hi = max(m0, d_from), min(m1, d_to)
        if pd.notna(r["data_through"]):
            hi = min(hi, r["data_through"])
        dim.append((m1 - m0).days + 1)
        cov.append(max(0, (hi - lo).days + 1))
    df["days_in_month"] = dim
    df["days_covered"] = cov
    share = df["days_covered"] / df["days_in_month"]
    df["expected_units"] = df["plan_units"] * share
    df["expected_rev"] = df["plan_rev"] * share
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Свод по объекту за весь период: план (пропорционально дням с данными),
    факт, выполнение и относительное отклонение темпа по ТЗ §13
    (факт / ожидание − 1). Без ожидания (план 0) отклонение не считается."""
    if df.empty:
        return df
    g = (df.groupby("object_name", as_index=False)
           .agg(plan_units=("plan_units", "sum"), expected_units=("expected_units", "sum"),
                fact_units=("fact_units", "sum"), plan_rev=("plan_rev", "sum"),
                expected_rev=("expected_rev", "sum"), fact_rev=("fact_rev", "sum"),
                plan_skus=("plan_skus", "max"), data_through=("data_through", "max"),
                days_covered=("days_covered", "sum"), days_in_month=("days_in_month", "sum"),
                months=("month", "nunique")))
    g["pace_pct"] = [((f / e - 1) * 100) if e and e > 0 else None
                     for f, e in zip(g["fact_units"], g["expected_units"])]
    g["done_pct"] = [((f / p) * 100) if p and p > 0 else None
                     for f, p in zip(g["fact_units"], g["plan_units"])]
    return g.sort_values("plan_units", ascending=False)
