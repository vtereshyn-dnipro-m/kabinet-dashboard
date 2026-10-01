-- ABC по выручке без НДС (ТЗ «Остатки», пункт 2). Правило 80/15/5, окно 90 дней,
-- по каждому маркетплейсу и общий — решение владельца 01.10.2026.
--
-- Сделано ВЬЮ, а не таблицей с загрузчиком, и это осознанно. Всё нужное —
-- `economics_summary` — уже лежит в Lakebase, считать нечего и неоткуда тянуть.
-- Таблица потребовала бы джобу, пульс, правило свежести и ещё один повод для
-- расхождения «в базе одно, на экране другое»; вью всегда показывает сегодняшнее
-- состояние и устареть не может. Единственная плата — счёт при каждом чтении, но это
-- 90 дней одной таблицы, и страницы его кешируют.
--
-- Единственный источник ABC в хранилище, который существовал до этого, — колонка
-- `abc_category` в `raw_planning_spain_2026`. Брать её нельзя: таблица загружена один
-- раз 31.08.2026, джобы нет (разбор в sql/sku_categories_tree_2026-10-01.sql).

BEGIN;

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('abc_window_days', 90, 'ABC: окно продаж в днях'),
    ('abc_a_pct', 80, 'ABC: доля выручки без НДС, попадающая в группу A'),
    ('abc_b_pct', 15, 'ABC: доля выручки для группы B; остальное — C')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE VIEW kabinet_data.v_sku_abc AS
WITH настройки AS (
    -- Пороги и окно — из справочника, а не константами: правило меняют в базе, и
    -- поведение обязано меняться вместе с ним.
    SELECT COALESCE(max(value) FILTER (WHERE key = 'abc_window_days'), 90)::int     AS окно,
           COALESCE(max(value) FILTER (WHERE key = 'abc_a_pct'),      80)::numeric  AS a_pct,
           COALESCE(max(value) FILTER (WHERE key = 'abc_b_pct'),      15)::numeric  AS b_pct
      FROM kabinet_data.reorder_params
),
продажи AS (
    -- По маркетплейсу и, отдельной строкой, общий итог. Общий считается заново по
    -- сумме, а не складыванием классов: товар может быть A на ES и C на DE, и
    -- «средний класс» не значил бы ничего.
    SELECT e.marketplace AS scope, e.norm_sku AS sku, sum(e.net_product_sales) AS revenue
      FROM kabinet_data.economics_summary e, настройки n
     WHERE e.sales_date >= current_date - n.окно
     GROUP BY 1, 2
    UNION ALL
    SELECT '__ALL__', e.norm_sku, sum(e.net_product_sales)
      FROM kabinet_data.economics_summary e, настройки n
     WHERE e.sales_date >= current_date - n.окно
     GROUP BY 2
),
-- Выручка бывает НЕПОЛОЖИТЕЛЬНОЙ: всё вернули, и за окно вышел минус. Такой товар
-- продавался, значит «нет продаж» про него неправда; но и в накопленную долю его
-- класть нельзя — отрицательные слагаемые ломают саму идею «первые 80 % выручки».
-- Поэтому он получает C напрямую, а долю считаем только по положительным.
ранги AS (
    SELECT scope, sku, revenue,
           sum(revenue) OVER (PARTITION BY scope) AS scope_revenue,
           sum(revenue) OVER (PARTITION BY scope ORDER BY revenue DESC, sku
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_revenue
      FROM продажи
     WHERE revenue > 0
),
классы AS (
    SELECT r.scope, r.sku, r.revenue,
           CASE WHEN r.scope_revenue > 0
                THEN round((100 * r.cum_revenue / r.scope_revenue)::numeric, 2) END AS cum_pct,
           CASE
             WHEN r.scope_revenue <= 0 THEN 'C'
             WHEN (100 * r.cum_revenue / r.scope_revenue)::numeric <= n.a_pct           THEN 'A'
             WHEN (100 * r.cum_revenue / r.scope_revenue)::numeric <= n.a_pct + n.b_pct THEN 'B'
             ELSE 'C'
           END AS abc
      FROM ранги r, настройки n
    UNION ALL
    SELECT scope, sku, revenue, NULL, 'C' FROM продажи WHERE revenue <= 0
),
-- Периметр: каждый SKU справочника против каждого рынка, где вообще были продажи за
-- окно. Товар без продаж получает ОТДЕЛЬНУЮ группу, а не C: «не продавался» и
-- «продавался мало» — разные вещи, и норматив по ним разный (решение владельца).
периметр AS (
    SELECT m.sku, s.scope
      FROM kabinet_data.sku_master m
      CROSS JOIN (SELECT DISTINCT scope FROM продажи) s
)
SELECT p.scope,
       p.sku,
       COALESCE(k.revenue, 0)::numeric(14,2) AS revenue,
       k.cum_pct,
       COALESCE(k.abc, 'no_sales') AS abc
  FROM периметр p
  LEFT JOIN классы k ON k.scope = p.scope AND k.sku = p.sku;

COMMENT ON VIEW kabinet_data.v_sku_abc IS
    'ABC по выручке без НДС за окно из reorder_params. scope = код рынка или __ALL__. abc = A/B/C/no_sales.';

GRANT SELECT ON kabinet_data.v_sku_abc
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

-- Проверка глазами: доли должны сойтись с правилом.
SELECT scope, abc, count(*) AS skus,
       round(sum(revenue)::numeric, 0) AS revenue,
       round((100 * sum(revenue) / NULLIF(sum(sum(revenue)) OVER (PARTITION BY scope), 0))::numeric, 1) AS pct
  FROM kabinet_data.v_sku_abc
 WHERE scope IN ('__ALL__', 'ES')
 GROUP BY scope, abc ORDER BY scope, abc;
