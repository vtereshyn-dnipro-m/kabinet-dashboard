-- Снимок сумм по дню × площадке при каждой загрузке (решение владельца 06.10.2026).
--
-- Зачем: задержку «день полон» выбрали по замеру на истории версий сырья, а Delta хранит её 7 дней — на
-- неделе. Amazon поставили 1 (на D+1 у дня ~98,7 % окончательной суммы). Через месяц долю на D+1 надо
-- пересчитать по 30 дням: хуже 97 % — возвращаем 2. Для этого каждая загрузка оставляет здесь свои суммы.
--
-- Пишет джоба `Kabinet - Load Day Snapshots` (ежечасно 07:20–22:20 Kyiv): читает только нашу
-- `economics_summary`, данные Дарины не трогает. Снимок берётся, когда последняя запись площадки старше
-- 20 минут (загрузчик дописал) и такого `load_at` ещё нет — каждая загрузка ровно один раз.
--
-- load_at — max(economics_summary.updated_at) площадки, UTC без зоны, как в источнике.

CREATE TABLE IF NOT EXISTS kabinet_data.load_day_snapshots (
    platform      text             NOT NULL,  -- amz / lm / mm / cf (platforms.short_name)
    marketplace   text             NOT NULL,  -- код рынка экономики (ES, MM_ES, LM …)
    load_at       timestamp        NOT NULL,  -- время загрузки площадки, UTC
    sales_date    date             NOT NULL,
    units         integer,
    ordered_sales double precision,           -- ordered_product_sales как в экономике
    net_sales     double precision,           -- net_product_sales — «Выручка» на Обзоре
    net_proceeds  double precision,
    n_rows        integer,
    snapped_at    timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (platform, load_at, marketplace, sales_date)
);
COMMENT ON TABLE kabinet_data.load_day_snapshots IS
  'Суммы экономики по дню × рынку на момент каждой загрузки площадки (06.10.2026). Нужны, чтобы пересчитать, какую долю окончательной суммы день имеет на D+1, D+2 — история версий сырья живёт 7 дней.';

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('kpi_day_final_days', 3, 'Запасное «день окончателен на загрузке D + N» для площадки без своей строки kpi_day_final_days_<площадка>; по нему v_load_day_completeness выбирает окончательную сумму.')
ON CONFLICT (key) DO NOTHING;

-- Доля окончательной суммы у каждого дня на каждой загрузке. Берётся ПЕРВАЯ загрузка дня-загрузки: именно её
-- видит страница сразу после прогона, худший случай. Окончательная — последняя загрузка не раньше D + final.
CREATE OR REPLACE VIEW kabinet_data.v_load_day_completeness AS
WITH s AS (
    SELECT platform, sales_date, load_at,
           (load_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::date AS load_day,
           sum(units) AS units, sum(net_sales) AS net_sales, sum(ordered_sales) AS ordered_sales
      FROM kabinet_data.load_day_snapshots
     GROUP BY 1, 2, 3),
fin_days AS (
    SELECT p.plat, COALESCE(
               (SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'kpi_day_final_days_' || p.plat),
               (SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'kpi_day_final_days'), 3) AS final_days
      FROM (SELECT DISTINCT platform AS plat FROM kabinet_data.load_day_snapshots) p),
first_of_day AS (
    SELECT DISTINCT ON (platform, sales_date, load_day) *
      FROM s ORDER BY platform, sales_date, load_day, load_at),
fin AS (
    SELECT DISTINCT ON (s.platform, s.sales_date) s.platform, s.sales_date,
           s.net_sales AS final_net, s.ordered_sales AS final_ordered, s.units AS final_units
      FROM s JOIN fin_days f ON f.plat = s.platform
     WHERE s.load_day - s.sales_date >= f.final_days
     ORDER BY s.platform, s.sales_date, s.load_at DESC)
SELECT d.platform, d.sales_date, d.load_day, d.load_day - d.sales_date AS lag_days,
       d.net_sales, f.final_net,
       CASE WHEN f.final_net > 0 THEN round((d.net_sales / f.final_net)::numeric, 4) END AS net_share,
       CASE WHEN f.final_ordered > 0 THEN round((d.ordered_sales / f.final_ordered)::numeric, 4) END AS ordered_share,
       d.units, f.final_units
  FROM first_of_day d
  LEFT JOIN fin f USING (platform, sales_date)
 WHERE d.load_day > d.sales_date;

-- Итог для решения: по площадке и задержке за последние 30 дней продаж с окончательной суммой.
-- Решение владельца: Amazon на D+1 (lag_days = 1) медиана хуже 97 % — kpi_day_settle_days_amz обратно 2.
CREATE OR REPLACE VIEW kabinet_data.v_load_day_completeness_30d AS
SELECT platform, lag_days,
       count(*) FILTER (WHERE net_share IS NOT NULL)                      AS days,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY net_share)             AS median_net_share,
       min(net_share)                                                      AS worst_net_share,
       round(avg((net_share >= 0.97)::int)::numeric, 3)                   AS share_of_days_ge_97pct,
       sum(net_sales) / NULLIF(sum(final_net), 0)                          AS total_net_share
  FROM kabinet_data.v_load_day_completeness
 WHERE final_net IS NOT NULL AND sales_date >= CURRENT_DATE - 33
 GROUP BY 1, 2;

-- Джоба идёт под владельцем; страницам и принципалу джоб — чтение.
GRANT SELECT, INSERT, DELETE ON kabinet_data.load_day_snapshots TO "v.tereshyn@dniprom.com";
GRANT SELECT, INSERT, DELETE ON kabinet_data.load_day_snapshots TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.load_day_snapshots, kabinet_data.v_load_day_completeness,
                kabinet_data.v_load_day_completeness_30d TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_load_day_completeness, kabinet_data.v_load_day_completeness_30d
             TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
