-- Worten в сводных вью витрины (30.10.2026): блок `worten` в v_all_marketplaces_spiderweb_report и блок `wrt` в
-- v_all_marketplaces_orders_enriched. Применять ПОСЛЕ sql/worten_vitrina_2026-10-30.sql. Текст обеих вью — ДОСЛОВНО
-- текущий (снят 30.10.2026 из information_schema.views), добавлены только блоки Worten; 30 колонок и 8 колонок не
-- меняются. ALTER VIEW … AS, а не CREATE OR REPLACE: владелец, права и комментарии вью остаются как есть.
-- Отпечатки текущего текста (sha256, первые 16 знаков) — скрипт применения сверяет их перед ALTER и останавливается,
-- если аналитик витрины успел поменять вью: тогда текст снимается заново.
--   v_all_marketplaces_spiderweb_report  было 75eb99597d505dce
--   v_all_marketplaces_orders_enriched   было 65fe642c98264aaf
-- Откат — тот же ALTER VIEW с прежним текстом (scratchpad-копия снята вместе с отпечатком).

ALTER VIEW dnipro_m.dnipro_m.v_all_marketplaces_spiderweb_report AS
WITH amazon AS (
  SELECT
    date,
    'Amazon' AS marketplace,    
    country,
    sku,
    asin AS product_marketplace_id,
    COALESCE(unitsOrdered, 0) AS units_sold,
    COALESCE(orderedProductSales, 0) AS sales_vat_incl,
    COALESCE(orderedProductSales, 0) / (1 + CASE
        WHEN country IN ('Spain') THEN 0.21
        WHEN country IN ('Italy') THEN 0.22
        WHEN country IN ('France') THEN 0.20
        WHEN country IN ('Germany') THEN 0.19
        WHEN country IN ('Belgium') THEN 0.21
        WHEN country IN ('Netherlands') THEN 0.21
        WHEN country IN ('United Kingdom') THEN 0.20
        WHEN country IN ('Sweden') THEN 0.25
        WHEN country IN ('Poland') THEN 0.23
        WHEN country IN ('Ireland') THEN 0.23
        ELSE 0
    END) AS sales_vat_excl,
    COALESCE(orderedProductSales, 0)
      - (COALESCE(orderedProductSales, 0) / (1 + CASE
          WHEN country IN ('Spain') THEN 0.21
          WHEN country IN ('Italy') THEN 0.22
          WHEN country IN ('France') THEN 0.20
          WHEN country IN ('Germany') THEN 0.19
          WHEN country IN ('Belgium') THEN 0.21
          WHEN country IN ('Netherlands') THEN 0.21
          WHEN country IN ('United Kingdom') THEN 0.20
          WHEN country IN ('Sweden') THEN 0.25
          WHEN country IN ('Poland') THEN 0.23
          WHEN country IN ('Ireland') THEN 0.23
          ELSE 0
      END)) AS tax_amount,
    COALESCE(referal_fee, 0) + COALESCE(digital_fee, 0) + COALESCE(fba_fee, 0) AS commission_fee_vat_excl,
    0 AS cancel_commission_vat_excl,    
    COALESCE(cogs, 0) AS cogs_total,
    COALESCE(shipping_cost, 0) AS shipping_cost_total,
    COALESCE(packing_cost, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(refund_total_vat_incl, 0) AS refund_total_vat_incl,
    COALESCE(refund_total_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(refunds_commissions_vat_excl, 0) AS refunds_commissions_vat_excl,    
    COALESCE(refunds_calculated, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,    
    COALESCE(other_net_result, 0) AS reimbursment,
    COALESCE(impressions, 0) AS impressions,
    COALESCE(clicks, 0) AS clicks,
    COALESCE(spend, 0) AS spend,
    COALESCE(units14d, 0) AS paidUnits,
    COALESCE(sales14d, 0) AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - COALESCE(spend, 0) AS contribution_profit
  FROM dnipro_m.raw_amazon_spiderweb_report
  WHERE date >= '2026-03-13'    
),

leroy_merlin AS (
  SELECT
    date,
    'Leroy Merlin' AS marketplace,    
    country,
    sku,
    product_sku AS product_marketplace_id,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(price, 0) AS sales_vat_incl,
    COALESCE(price_vat_excl, 0) AS sales_vat_excl,
    COALESCE(tax_amount, 0) AS tax_amount,
    COALESCE(commission_fee, 0) AS commission_fee_vat_excl,
    0 AS cancel_commission_vat_excl,    
    COALESCE(cogs_total, 0) AS cogs_total,
    COALESCE(shipping_cost_total, 0) AS shipping_cost_total,
    COALESCE(packing_cost_total, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(price_refund, 0) AS refund_total_vat_incl,
    COALESCE(price_refund_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(commission_fee_refund, 0) AS refunds_commissions_vat_excl,    
    COALESCE(expenses_refund, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,
    0 AS reimbursment,
    COALESCE(impressions, 0) AS impressions,
    COALESCE(clicks, 0) AS clicks,
    COALESCE(spend, 0) AS spend,
    COALESCE(paidUnits, 0) AS paidUnits,
    COALESCE(paidSales, 0) AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - COALESCE(spend, 0) AS contribution_profit
  FROM dnipro_m.v_lm_spiderweb_report
  WHERE date >= '2026-03-13'
),

carrefour AS (
  SELECT
    date,
    'Carrefour' AS marketplace,    
    country,
    sku,
    product_sku AS product_marketplace_id,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(price, 0) AS sales_vat_incl,
    COALESCE(price_vat_excl, 0) AS sales_vat_excl,
    COALESCE(tax_amount, 0) AS tax_amount,
    COALESCE(commission_fee, 0) AS commission_fee_vat_excl,
    COALESCE(cancel_commission, 0) AS cancel_commission_vat_excl,    
    COALESCE(cogs_total, 0) AS cogs_total,
    COALESCE(shipping_cost_total, 0) AS shipping_cost_total,
    COALESCE(packing_cost_total, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(price_refund, 0) AS refund_total_vat_incl,
    COALESCE(price_refund_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(commission_fee_refund, 0) AS refunds_commissions_vat_excl,    
    COALESCE(expenses_refund, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,
    0 AS reimbursment,
    0 AS impressions,
    0 AS clicks,
    0 AS spend,
    0 AS paidUnits,
    0 AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - 0 AS contribution_profit
  FROM dnipro_m.v_cf_spiderweb_report
  WHERE date >= '2026-03-13'
),

manomano AS (
  SELECT
    date,
    'ManoMano' AS marketplace,    
    country,
    sku,
    product_sku AS product_marketplace_id,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(price, 0) AS sales_vat_incl,
    COALESCE(price_vat_excl, 0) AS sales_vat_excl,
    COALESCE(tax_amount, 0) AS tax_amount,
    COALESCE(commission_fee, 0) AS commission_fee_vat_excl,
    0 AS cancel_commission_vat_excl,    
    COALESCE(cogs_total, 0) AS cogs_total,
    COALESCE(shipping_cost_total, 0) AS shipping_cost_total,
    COALESCE(packing_cost_total, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(price_refund, 0) AS refund_total_vat_incl,
    COALESCE(price_refund_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(commission_fee_refund, 0) AS refunds_commissions_vat_excl,    
    COALESCE(expenses_refund, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,
    0 AS reimbursment,
    COALESCE(impressions, 0) AS impressions,
    COALESCE(clicks, 0) AS clicks,
    COALESCE(spend, 0) AS spend,
    COALESCE(paidUnits, 0) AS paidUnits,
    COALESCE(paidSales, 0) AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - COALESCE(spend, 0) AS contribution_profit
  FROM dnipro_m.v_mm_spiderweb_report
  WHERE date >= '2026-03-13'
),

odoo AS (
  SELECT
    date,
    sales_team AS marketplace,    
    country,
    sku,
    'without_product_id' AS product_marketplace_id,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(price, 0) AS sales_vat_incl,
    COALESCE(price_vat_excl, 0) AS sales_vat_excl,
    COALESCE(price, 0) - COALESCE(price_vat_excl, 0) AS tax_amount,
    COALESCE(fees_total, 0) AS commission_fee_vat_excl,
    0 AS cancel_commission_vat_excl,    
    COALESCE(cogs_total, 0) AS cogs_total,
    COALESCE(shipping_cost_total, 0) AS shipping_cost_total,
    COALESCE(packing_cost_total, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(price_refund, 0) AS refund_total_vat_incl,
    COALESCE(price_refund_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(fees_total_refund, 0) AS refunds_commissions_vat_excl,    
    COALESCE(expenses_refund, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,
    0 AS reimbursment,
    0 AS impressions,
    0 AS clicks,
    0 AS spend,
    0 AS paidUnits,
    0 AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - 0 AS contribution_profit
  FROM dnipro_m.v_odoo_spiderweb_report
  WHERE date >= '2026-03-13'
),

worten AS (
  SELECT
    date,
    'Worten' AS marketplace,
    country,
    sku,
    product_sku AS product_marketplace_id,
    COALESCE(units_sold, 0) AS units_sold,
    COALESCE(price, 0) AS sales_vat_incl,
    COALESCE(price_vat_excl, 0) AS sales_vat_excl,
    COALESCE(tax_amount, 0) AS tax_amount,
    COALESCE(commission_fee, 0) AS commission_fee_vat_excl,
    0 AS cancel_commission_vat_excl,
    COALESCE(cogs_total, 0) AS cogs_total,
    COALESCE(shipping_cost_total, 0) AS shipping_cost_total,
    COALESCE(packing_cost_total, 0) AS packing_cost_total,
    COALESCE(expenses, 0) AS expenses,
    COALESCE(quantity_refund, 0) AS quantity_refund,
    COALESCE(price_refund, 0) AS refund_total_vat_incl,
    COALESCE(price_refund_vat_excl, 0) AS refund_total_vat_excl,
    COALESCE(commission_fee_refund, 0) AS refunds_commissions_vat_excl,
    COALESCE(expenses_refund, 0) AS expenses_refund,
    COALESCE(cogs_refund, 0) AS cogs_refund,
    COALESCE(shipping_cost_refund, 0) AS shipping_cost_refund,
    0 AS reimbursment,
    0 AS impressions,
    0 AS clicks,
    0 AS spend,
    0 AS paidUnits,
    0 AS paidSales,
    COALESCE(profit, 0) AS profit,
    COALESCE(profit, 0) - 0 AS contribution_profit
  FROM dnipro_m.v_wrt_spiderweb_report
  WHERE date >= '2026-03-13'
)

SELECT * FROM amazon
UNION ALL
SELECT * FROM leroy_merlin
UNION ALL
SELECT * FROM carrefour
UNION ALL
SELECT * FROM manomano
UNION ALL
SELECT * FROM odoo
UNION ALL
SELECT * FROM worten
ORDER BY date, marketplace;


ALTER VIEW dnipro_m.dnipro_m.v_all_marketplaces_orders_enriched AS
SELECT
    'amazon' AS source,
    purchase_date,
    amazon_order_id          AS order_id,
    marketplace,
    country,
    order_total_amount_eur,
    units_ordered_orders_table AS items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_amazon_orders_enriched
WHERE purchase_date >= '2026-03-13'

UNION ALL

SELECT
    'lm' AS source,
    purchase_date,
    order_id,
    marketplace,
    country,
    order_total_amount_eur,
    items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_lm_orders_enriched
WHERE purchase_date >= '2026-03-13'

UNION ALL

SELECT
    'cf' AS source,
    purchase_date,
    order_id,
    marketplace,
    country,
    order_total_amount_eur,
    items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_cf_orders_enriched
WHERE purchase_date >= '2026-03-13'

UNION ALL

SELECT
    'mm' AS source,
    purchase_date,
    order_id,
    marketplace,
    country,
    order_total_amount_eur,
    items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_mm_orders_enriched
WHERE purchase_date >= '2026-03-13'

UNION ALL

SELECT
    'odoo' AS source,
    purchase_date,
    order_id,
    marketplace,
    country,
    order_total_amount_eur,
    items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_odoo_orders_enriched
WHERE purchase_date >= '2026-03-13'

UNION ALL

SELECT
    'wrt' AS source,
    purchase_date,
    order_id,
    marketplace,
    country,
    order_total_amount_eur,
    items_quantity_ordered,
    unique_sku_ordered
FROM dnipro_m.v_wrt_orders_enriched
WHERE purchase_date >= '2026-03-13';
