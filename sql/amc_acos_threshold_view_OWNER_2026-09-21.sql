-- Страница «Реклама» с 03.09.2026 (#54) ждёт во вью колонку acos_threshold — порог ACOS кампании,
-- посчитанный от маржи её товаров, — а во вью её никогда не было: страница с тех пор показывала
-- «нет колонок». Вью принадлежит владельцу (v.tereshyn@dniprom.com) — выполняет владелец.
--
-- Порог = маржа до рекламы товаров кампании за reorder_params.ads_margin_window_days дней на ES
-- (инстанс AMC — Испания): (net_proceeds_total − COGS − упаковка − доставка) / продажи с НДС.
-- Знаменатель с НДС намеренно: ACOS = spend / sales_14d, а sales_14d у Amazon с НДС.
-- Товары кампании: tracked_asin из amc_campaign_asin (AMC отдаёт не всем — __MASKED__) плюс ASIN
-- из названия кампании; ASIN → SKU через product_entity_listings (AMZ-ES), SKU приводится к форме
-- norm_sku экономики (без S_/S2_, без -FBA/-FBM и хвоста «_», цифры до 8). Кампания без
-- товаров или без себестоимости — порог NULL, статус no_margin_data («маржа неизвестна»).
-- Константа 25 в campaign_status убрана: она и была тем, что #54 обещал убрать.
CREATE OR REPLACE VIEW kabinet_data.v_amc_attribution AS
WITH win AS (
    SELECT COALESCE((SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'ads_margin_window_days'), 90) AS days
),
camp_asin AS (
    SELECT DISTINCT campaign_id, tracked_asin AS asin
    FROM kabinet_data.amc_campaign_asin WHERE tracked_asin <> '__MASKED__'
    UNION
    SELECT DISTINCT campaign_id, (regexp_match(campaign_name, 'B0[A-Z0-9]{8}'))[1]
    FROM kabinet_data.amc_attribution_sync WHERE campaign_name ~ 'B0[A-Z0-9]{8}'
),
asin_sku AS (
    SELECT DISTINCT peid AS asin,
           CASE WHEN s ~ '^\d+$' THEN lpad(s, 8, '0') ELSE s END AS norm_sku
    FROM (SELECT peid, regexp_replace(regexp_replace(regexp_replace(sku, '^S\d?_', ''), '[-_]?(FBA|FBM)$', ''), '_$', '') AS s
          FROM kabinet_data.product_entity_listings WHERE marketplace_id = 1 AND sku IS NOT NULL) x
),
sku_margin AS (
    SELECT e.norm_sku,
           SUM(e.ordered_product_sales) AS sales,
           SUM(e.net_proceeds_total - e.cogs * e.net_units_sold - COALESCE(l.packing_cost, 0) - COALESCE(l.shipping_cost, 0)) AS profit_before_ads
    FROM kabinet_data.economics_summary e
    LEFT JOIN kabinet_data.economics_logistics l
           ON l.sales_date = e.sales_date AND l.marketplace = e.marketplace AND l.norm_sku = e.norm_sku
    CROSS JOIN win
    WHERE e.marketplace = 'ES' AND e.sales_date >= current_date - win.days AND e.cogs IS NOT NULL
    GROUP BY 1
),
camp_threshold AS (
    SELECT ca.campaign_id,
           round((100 * SUM(m.profit_before_ads) / NULLIF(SUM(m.sales), 0))::numeric, 1) AS acos_threshold
    FROM camp_asin ca
    JOIN asin_sku s ON s.asin = ca.asin
    JOIN sku_margin m ON m.norm_sku = s.norm_sku
    GROUP BY 1
),
base AS (
    SELECT a.report_date, a.campaign_id, a.campaign_name, a.ad_product_name, a.spend, a.impressions, a.clicks,
           a.purchases_14d, a.sales_14d, a.units_sold, a.reach, a.window_days, a.loaded_at, a.instance_id,
           a.amazon_marketplace_id,
           CASE WHEN a.spend > 0::numeric THEN round(a.sales_14d / a.spend, 2) END                                        AS roas,
           CASE WHEN a.sales_14d > 0::numeric THEN round(a.spend * 100.0 / a.sales_14d, 2) END                             AS acos_pct,
           CASE WHEN a.clicks > 0 THEN round(a.spend / a.clicks::numeric, 4) END                                           AS cpc,
           CASE WHEN a.impressions > 0 THEN round(a.clicks::numeric * 100.0 / a.impressions::numeric, 2) END               AS ctr_pct,
           t.acos_threshold
    FROM kabinet_data.amc_attribution_sync a
    LEFT JOIN camp_threshold t ON t.campaign_id = a.campaign_id
)
SELECT report_date, campaign_id, campaign_name, ad_product_name, spend, impressions, clicks, purchases_14d, sales_14d,
       units_sold, reach, window_days, loaded_at, instance_id, amazon_marketplace_id, roas, acos_pct, cpc, ctr_pct,
       CASE
           WHEN spend = 0::numeric AND clicks = 0 THEN 'no_traffic'
           WHEN campaign_name = '__MASKED__' THEN 'masked'
           WHEN sales_14d = 0::numeric AND clicks >= 1 AND ctr_pct >= 0.3 THEN 'no_conversion'
           WHEN sales_14d = 0::numeric THEN 'weak_targeting'
           WHEN acos_threshold IS NULL THEN 'no_margin_data'
           WHEN acos_pct > acos_threshold THEN 'high_acos'
           ELSE 'ok'
       END AS campaign_status,
       acos_threshold
FROM base;
-- проверка
SELECT campaign_status, count(*), count(DISTINCT campaign_id) FROM kabinet_data.v_amc_attribution GROUP BY 1 ORDER BY 1;
