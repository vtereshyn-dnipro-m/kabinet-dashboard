-- Дневной вид регуляторного сбора Amazon Ads для аналитика (Unity Catalog, Spark SQL). Выполнять ПОСЛЕ мержа в Databricks
-- (SQL-редактор или ноутбук; через MCP-запрос CREATE не проходит).
--
-- Счёт Amazon Ads выставляется по порогу (~500 €), а не по дню: его период — от дня до месяца. Вид раскладывает сбор
-- каждого счёта (строка raw_amazon_ads_invoice_fees: тип × страна показа) по дням периода счёта ПРОПОРЦИОНАЛЬНО расходу
-- на рекламу из Ads API за эти дни (SP + SB + SD по кампаниям, таблицы raw_amazon_ads_*_campaign_<рынок>). Дней без
-- данных о расходе (раньше 06.02.2026 — таблиц кампаний тогда ещё не было) — поровну по дням, колонка allocation
-- это называет. Сумма по счёту равна сбору счёта до цента; приблизителен только раздел между днями. Граничный день,
-- общий для двух соседних счетов, получает долю от обоих — по расходу этого дня целиком.
-- Валюта — профиля (UK — фунты), в евро не пересчитано. Набирающийся счёт (ACCUMULATING) — по сегодня.
-- Проверено 16.10.2026 на пяти счетах (ES 1119252MUPA26, IT 1267217MTPA26, FR 1630863G5PA26, DE 4578476M5PA26,
-- ES DRJFZJMF4-4 из 2024 г.): сумма по дням = сбор счёта; по дням ES 1119252MUPA26 — как ручной расчёт.
CREATE OR REPLACE VIEW dnipro_m.dnipro_m.v_amazon_ads_fees_daily
COMMENT 'Регуляторный сбор Amazon Ads по дням: сбор счёта разнесён по дням его периода пропорционально расходу на рекламу (allocation = by_ads_spend) или поровну, если расхода за дни нет (even_by_days). Источник — raw_amazon_ads_invoices / raw_amazon_ads_invoice_fees (Kabinet - Amazon Ads Invoices). Валюта профиля.'
AS
WITH cost AS (
  SELECT 'ES' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_es UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_es UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_es) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'IT' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_it UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_it UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_it) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'FR' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_fr UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_fr UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_fr) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'DE' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_de UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_de UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_de) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'NL' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_nl UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_nl UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_nl) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'BE' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_be UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_be UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_be) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'PL' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_pl UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_pl UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_pl) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'SE' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_se UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_se UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_se) GROUP BY CAST(date AS DATE)
  UNION ALL
  SELECT 'UK' AS country, CAST(date AS DATE) AS d, SUM(cost) AS c FROM (SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_uk UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_uk UNION ALL SELECT date, cost FROM dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_uk) GROUP BY CAST(date AS DATE)
),
inv AS (
  SELECT profile_id, profile_country, invoice_key, invoice_id, status, from_date,
         COALESCE(to_date, current_date()) AS to_d, currency
  FROM dnipro_m.dnipro_m.raw_amazon_ads_invoices
  WHERE from_date IS NOT NULL
),
days AS (
  SELECT i.*, explode(sequence(i.from_date, i.to_d)) AS d FROM inv i
),
w AS (
  SELECT dy.*, COALESCE(c.c, 0) AS c,
         SUM(COALESCE(c.c, 0)) OVER (PARTITION BY dy.profile_id, dy.invoice_key) AS c_tot,
         COUNT(*) OVER (PARTITION BY dy.profile_id, dy.invoice_key) AS n_days
  FROM days dy LEFT JOIN cost c ON c.country = dy.profile_country AND c.d = dy.d
)
SELECT w.d AS date,
       w.profile_country,
       f.fee_country,
       f.fee_type,
       w.currency,
       f.amount * CASE WHEN w.c_tot > 0 THEN w.c / w.c_tot ELSE 1.0 / w.n_days END AS fee_amount,
       w.invoice_id,
       w.invoice_key,
       w.status AS invoice_status,
       w.from_date AS invoice_from,
       w.to_d AS invoice_to,
       CASE WHEN w.c_tot > 0 THEN 'by_ads_spend' ELSE 'even_by_days' END AS allocation
FROM w
JOIN dnipro_m.dnipro_m.raw_amazon_ads_invoice_fees f
  ON f.profile_id = w.profile_id AND f.invoice_key = w.invoice_key
WHERE f.amount <> 0
;
