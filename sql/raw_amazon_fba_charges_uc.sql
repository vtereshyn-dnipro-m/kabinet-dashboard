-- Хранение FBA и возмещения FBA — два отчёта SP-API, которых не видит
-- Data Kiosk. Unity Catalog, слой сырья. Загрузчик: Kabinet - FBA Charges Loader.
--
-- Оба отчёта приходят по всему EU-аккаунту сразу, а не по рынку: у хранения
-- страна — в country_code центра, у возмещений — в номере заказа.

CREATE TABLE IF NOT EXISTS dnipro_m.dnipro_m.raw_amazon_fba_storage_fees (
  asin STRING NOT NULL, fnsku STRING NOT NULL, product_name STRING,
  fulfillment_center STRING NOT NULL COMMENT 'код центра без кавычек, в отчёте приходит как ''BRE2''',
  country_code STRING,
  longest_side DECIMAL(10,2), median_side DECIMAL(10,2), shortest_side DECIMAL(10,2), measurement_units STRING,
  weight DECIMAL(10,3), weight_units STRING, item_volume DECIMAL(12,6), volume_units STRING,
  product_size_tier STRING,
  average_quantity_on_hand DECIMAL(12,2), average_quantity_pending_removal DECIMAL(12,2),
  estimated_total_item_volume DECIMAL(14,6),
  month_of_charge STRING NOT NULL COMMENT 'YYYY-MM',
  storage_utilization_ratio DECIMAL(10,2), storage_utilization_ratio_units STRING,
  base_rate DECIMAL(10,4), utilization_surcharge_rate DECIMAL(10,4),
  avg_qty_for_sus DECIMAL(12,2), est_vol_for_sus DECIMAL(14,6), est_base_msf DECIMAL(12,4), est_sus DECIMAL(12,4),
  currency STRING,
  estimated_monthly_storage_fee DECIMAL(12,4) COMMENT 'итог по строке, без НДС',
  category STRING, eligible_for_inventory_discount STRING, qualifies_for_inventory_discount STRING,
  total_incentive_fee_amount DECIMAL(12,4), breakdown_incentive_fee_amount STRING,
  average_quantity_customer_orders DECIMAL(12,2),
  report_id STRING, loaded_at TIMESTAMP,
  CONSTRAINT raw_amazon_fba_storage_fees_pk PRIMARY KEY (asin, fnsku, fulfillment_center, month_of_charge)
) USING DELTA
COMMENT 'GET_FBA_STORAGE_FEE_CHARGES_DATA: помесячное хранение по ASIN и центру. Отчёт за месяц пересчитывается Amazon до середины следующего — загрузчик перезапрашивает два последних месяца.';

CREATE TABLE IF NOT EXISTS dnipro_m.dnipro_m.raw_amazon_fba_reimbursements (
  approval_date TIMESTAMP, reimbursement_id STRING NOT NULL, case_id STRING, amazon_order_id STRING,
  reason STRING, sku STRING NOT NULL, fnsku STRING, asin STRING NOT NULL, product_name STRING, condition STRING,
  currency_unit STRING, amount_per_unit DECIMAL(12,2), amount_total DECIMAL(12,2),
  quantity_reimbursed_cash INT, quantity_reimbursed_inventory INT, quantity_reimbursed_total INT,
  original_reimbursement_id STRING, original_reimbursement_type STRING,
  report_id STRING, loaded_at TIMESTAMP,
  CONSTRAINT raw_amazon_fba_reimbursements_pk PRIMARY KEY (reimbursement_id, sku, asin)
) USING DELTA
COMMENT 'GET_FBA_REIMBURSEMENTS_DATA: возмещения FBA деньгами и товаром — утеря, порча, возвраты. Весь EU-аккаунт.';
