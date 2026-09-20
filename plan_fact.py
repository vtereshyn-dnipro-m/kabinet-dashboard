# plan_fact.py — факт против действующего прогноза по объектам реестра (ТЗ 010 §13)
"""Один расчёт на «Обзор» и «Деньги».

Объект прогноза — marketplace или пул (`v_forecast_current`), факт — продажи
`economics_summary` по кодам рынков объекта: у marketplace один код, у пула —
коды участников из `pool_members`. План месяца сравнивается с фактом только за
ту часть месяца, по которой есть данные: доля календарных дней (ТЗ §13 —
равномерное потребление, рабочие дни не подставляются). Поэтому ожидание —
это `план × дней_с_данными / дней_в_месяце`, а не весь план.

Факт — продажи по заказам **с НДС**, как план в листе и как карточка «Продажи
по заказам» на Обзоре: только Amazon, `sales_traffic_daily.ordered_sales` (сходится
с кабинетом Amazon). Каналы Mirakl в блок не входят — план есть только по Amazon,
а с ними (19–20.09.2026) факт блока расходился с карточкой на их продажи: 48 720
против 43 547 €. Одна цифра — один источник. Чистые продажи без НДС и возвратов
(`net_product_sales`) здесь не годятся: 18.09.2026 они давали −63 % к плану при
реальных −40 %. Факт по дате заказа, не отгрузки; отгрузочный факт по ТЗ живёт
в алертах темпа.
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
    daily AS (   -- только Amazon: тот же источник, что у карточки «Продажи по заказам»
        SELECT marketplace, snapshot_date AS d, units_ordered, ordered_sales AS gross
        FROM kabinet_data.sales_traffic_daily WHERE snapshot_date BETWEEN %(d0)s AND %(d1)s
    ),
    fact AS (
        SELECT c.object_type, c.object_id,
               date_trunc('month', e.d)::date AS month,
               SUM(e.units_ordered)::int    AS fact_units,
               SUM(e.gross)                 AS fact_rev,
               MAX(e.d)                     AS data_through
        FROM daily e
        JOIN codes c ON c.code = CASE WHEN e.marketplace = 'GB' THEN 'CO.UK' ELSE e.marketplace END
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
    (факт / ожидание − 1) — и в штуках, и в евро (`*_rev_*`). Без ожидания
    (план 0) отклонение не считается. Выручка плана — `forecast_revenue`
    реестра (штуки × целевая цена из листа), факт — `net_product_sales`."""
    if df.empty:
        return df
    g = (df.groupby("object_name", as_index=False)
           .agg(plan_units=("plan_units", "sum"), expected_units=("expected_units", "sum"),
                fact_units=("fact_units", "sum"), plan_rev=("plan_rev", "sum"),
                expected_rev=("expected_rev", "sum"), fact_rev=("fact_rev", "sum"),
                plan_skus=("plan_skus", "max"), data_through=("data_through", "max"),
                days_covered=("days_covered", "sum"), days_in_month=("days_in_month", "sum"),
                months=("month", "nunique")))
    def _ratio(num, den, shift):
        return [((n / d - 1 + shift) * 100) if d and d > 0 else None for n, d in zip(num, den)]
    g["pace_pct"] = _ratio(g["fact_units"], g["expected_units"], 0)
    g["done_pct"] = _ratio(g["fact_units"], g["plan_units"], 1)
    g["pace_rev_pct"] = _ratio(g["fact_rev"], g["expected_rev"], 0)
    g["done_rev_pct"] = _ratio(g["fact_rev"], g["plan_rev"], 1)
    return g.sort_values("plan_rev", ascending=False)


def two_rows(g: pd.DataFrame) -> pd.DataFrame:
    """Свод в две строки на объект: евро первой, штуки второй — клиент читает деньги,
    штуки нужны рядом для проверки. Колонки одинаковые, единица — отдельным полем."""
    rows = []
    for _, r in g.iterrows():
        rows.append(dict(obj=r["object_name"], unit="€", plan=r["plan_rev"], expected=r["expected_rev"],
                         fact=r["fact_rev"], done=r["done_rev_pct"], pace=r["pace_rev_pct"], skus=r["plan_skus"]))
        rows.append(dict(obj="", unit="шт", plan=r["plan_units"], expected=r["expected_units"],
                         fact=r["fact_units"], done=r["done_pct"], pace=r["pace_pct"], skus=None))
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# План текущего месяца в трёх разрезах (Обзор): страна / страна с маркетплейсами /
# площадка с маркетплейсами. Всегда текущий месяц — от периода страницы не зависит.
# ═══════════════════════════════════════════════════════════════════════════

SQL_MONTH = """
    WITH mp AS (
        SELECT id, code, platform_short, country_alpha2, name,
               CASE WHEN upper(legacy_code) = 'CO.UK' THEN 'GB' ELSE upper(legacy_code) END AS econ_code
        FROM kabinet_data.marketplaces_new
    ),
    fact AS (   -- только Amazon: тот же источник и та же сумма, что у карточки «Продажи по заказам»
        SELECT marketplace AS econ_code, SUM(units_ordered)::int AS fact_units, SUM(ordered_sales) AS fact_rev,
               MAX(snapshot_date) AS data_through
        FROM kabinet_data.sales_traffic_daily WHERE snapshot_date >= %(m0)s AND snapshot_date <= %(d1)s
        GROUP BY 1
    ),
    plan AS (
        SELECT object_type, object_id, object_name, SUM(quantity)::int AS plan_units,
               SUM(forecast_revenue) AS plan_rev, COUNT(*) FILTER (WHERE quantity > 0) AS plan_skus
        FROM kabinet_data.v_forecast_current WHERE month = %(m0)s
        GROUP BY 1, 2, 3
    ),
    pool_country AS (
        SELECT pm.pool_id, MIN(m.country_alpha2) AS country, array_agg(m.code ORDER BY m.code) AS members
        FROM kabinet_data.pool_members pm JOIN mp m ON m.id = pm.marketplace_id GROUP BY pm.pool_id
    )
    SELECT 'marketplace' AS kind, mp.id, mp.code, mp.name, mp.platform_short AS platform, mp.country_alpha2 AS country,
           NULL::text[] AS members,
           COALESCE(f.fact_units, 0) AS fact_units, COALESCE(f.fact_rev, 0) AS fact_rev, f.data_through,
           p.plan_units, p.plan_rev, p.plan_skus,
           EXISTS (SELECT 1 FROM kabinet_data.pool_members pm WHERE pm.marketplace_id = mp.id) AS in_pool
    FROM mp LEFT JOIN fact f USING (econ_code)
    LEFT JOIN plan p ON p.object_type = 'marketplace' AND p.object_id = mp.id
    WHERE mp.platform_short = 'AMZ'
    UNION ALL
    SELECT 'pool', p.object_id, p.object_name, p.object_name, NULL, pc.country, pc.members,
           0, 0, NULL, p.plan_units, p.plan_rev, p.plan_skus, true
    FROM plan p JOIN pool_country pc ON pc.pool_id = p.object_id WHERE p.object_type = 'pool'
"""


def load_month(conn, today: date) -> pd.DataFrame:
    """Маркетплейсы (факт с начала месяца + собственный план) и пулы (план) за текущий месяц."""
    df = pd.read_sql(SQL_MONTH, conn, params={"m0": today.replace(day=1), "d1": today})
    if df.empty:
        return df
    df["data_through"] = pd.to_datetime(df["data_through"]).dt.date
    return df


def _agg(rows: pd.DataFrame, pools: pd.DataFrame, share: float) -> dict:
    """Узел или лист таблицы «План месяца».

    Факт — по всем строкам узла (сходится с карточкой «Продажи по заказам»);
    план, ожидание, выполнение и темп — только по строкам, у которых план есть.
    У маркетплейса без плана план и ожидание 0, выполнение и темп не считаются
    (решение Ярослава, 18.09.2026): строка видна, факт виден, сравнивать нечего."""
    planned = rows[rows["plan_units"].notna()]
    has_plan = bool(len(planned) or len(pools))
    plan_u = float(planned["plan_units"].sum() + pools["plan_units"].fillna(0).sum())
    plan_r = float(planned["plan_rev"].fillna(0).sum() + pools["plan_rev"].fillna(0).sum())
    # факт против плана — только у тех, у кого план есть (иначе Amazon-план сравнивался бы с продажами LM)
    pf_u, pf_r = float(planned["fact_units"].sum()), float(planned["fact_rev"].sum())
    exp_u, exp_r = plan_u * share, plan_r * share
    return dict(plan_units=plan_u, plan_rev=plan_r, expected_units=exp_u, expected_rev=exp_r,
                fact_units=float(rows["fact_units"].sum()), fact_rev=float(rows["fact_rev"].sum()),
                done_units=(pf_u / plan_u * 100) if plan_u else None, done_rev=(pf_r / plan_r * 100) if plan_r else None,
                pace_units=(pf_u / exp_u - 1) * 100 if exp_u else None, pace_rev=(pf_r / exp_r - 1) * 100 if exp_r else None,
                plan_skus=int(planned["plan_skus"].fillna(0).sum() + pools["plan_skus"].fillna(0).sum()) if has_plan else 0,
                has_plan=has_plan)


def month_view(df: pd.DataFrame, mode: str, today: date) -> tuple:
    """Строки для таблицы «План месяца».

    mode: 'country' — страна одной строкой; 'country_mp' — страна и её маркетплейсы;
    'platform' — площадка и её маркетплейсы по странам. Возвращает (строки, итог, share):
    итог — по всем объектам плана текущего месяца, одинаковый во всех разрезах.
    Узел считает план и факт по одному набору маркетплейсов — тем, у кого план есть;
    остальные видны детьми со своим фактом. Пул (если у него ещё есть свой план)
    прибавляется к стране целиком.
    """
    if df.empty:
        return pd.DataFrame(), {}, 0.0
    mps, pools = df[df["kind"] == "marketplace"], df[df["kind"] == "pool"]
    dim = calendar.monthrange(today.year, today.month)[1]
    dt = mps["data_through"].dropna()
    covered = min(today, max(dt)).day if len(dt) else 0
    share = covered / dim
    pool_countries = set(pools["country"].dropna())
    # периметр — рынки Amazon с планом ИЛИ с продажами в этом месяце: страны без плана (BE, GB)
    # отдельными строками с нулевым планом. Каналов Mirakl здесь нет: план только по Amazon,
    # и факт блока обязан совпадать с карточкой «Продажи по заказам» (20.09.2026, третье расхождение)
    in_scope = mps[mps["plan_units"].notna() | (mps["fact_units"] > 0) | (mps["fact_rev"] > 0)]
    plan_countries = set(in_scope["country"].dropna()) | pool_countries

    rows = []
    def add(level, name, sub, r, parent=None):
        # parent — узел (страна/площадка) у каждой строки: таблица на экране сортируется
        # по любой колонке, и без него дочерние строки теряют страну (CF-ES «под Бельгией»)
        rows.append(dict(level=level, parent=parent or name, name=name, sub=sub, **r))

    def node(level, name, group, pool_rows):
        """Узел (страна или площадка): факт — по всем маркетплейсам узла, выполнение и темп —
        по тем, у кого есть план (см. _agg). В составе видно, по кому считается темп."""
        planned = sorted(group.loc[group["plan_units"].notna(), "code"])
        unplanned = sorted(group.loc[group["plan_units"].isna(), "code"])
        sub = ("план: " + ", ".join(planned)) if planned else ""
        if unplanned: sub += (" · " if sub else "") + "без плана: " + ", ".join(unplanned)
        add(level, name, sub, _agg(group, pool_rows, share))

    if mode in ("country", "country_mp"):
        for c in sorted(plan_countries):
            m_c, p_c = in_scope[in_scope["country"] == c], pools[pools["country"] == c]
            # узел из одного маркетплейса и без пула — одна строка, не «итого» плюс тот же маркетплейс под ним:
            # после перевода блока на только-Amazon (20.09) у каждой страны ровно один рынок, и строки задваивались
            if mode == "country_mp" and len(m_c) == 1 and p_c.empty:
                m = m_c.iloc[0]
                add(1, m["code"], m["name"], _agg(m_c, p_c, share), parent=c)
                continue
            node(0, c, m_c, p_c)
            if mode == "country_mp":
                for _, m in m_c.sort_values("code").iterrows():
                    add(1, m["code"], m["name"], _agg(m.to_frame().T, pools.iloc[0:0], share), parent=c)
    else:
        for pf in sorted(in_scope["platform"].dropna().unique()):
            m_p = in_scope[in_scope["platform"] == pf]
            if len(m_p) == 1:
                m = m_p.iloc[0]
                add(1, m["code"], m["name"], _agg(m_p, pools.iloc[0:0], share), parent=pf)
                continue
            node(0, pf, m_p, pools.iloc[0:0])
            for _, m in m_p.sort_values("code").iterrows():
                add(1, m["code"], m["name"], _agg(m.to_frame().T, pools.iloc[0:0], share), parent=pf)
    out = pd.DataFrame(rows)
    # итог: факт по всем строкам периметра, темп — по строкам с планом (одинаково в любом разрезе)
    total = _agg(in_scope, pools, share)
    total["covered"], total["days_in_month"] = covered, dim
    total["data_through"] = max(dt) if len(dt) else None
    total["pool_note"] = sorted(f"{p['name']} ({', '.join(p['members'] or [])})" for _, p in pools.iterrows())
    return out, total, share
