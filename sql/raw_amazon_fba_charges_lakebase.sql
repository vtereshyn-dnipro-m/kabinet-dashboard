-- Реплики хранения и возмещений FBA для страниц. Lakebase, kabinet_data.
-- Первоисточник — dnipro_m.raw_amazon_fba_storage_fees / _reimbursements.
CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_fba_storage_fees (
  asin text NOT NULL, fnsku text NOT NULL, product_name text, fulfillment_center text NOT NULL, country_code text,
  longest_side numeric(10,2), median_side numeric(10,2), shortest_side numeric(10,2), measurement_units text,
  weight numeric(10,3), weight_units text, item_volume numeric(12,6), volume_units text, product_size_tier text,
  average_quantity_on_hand numeric(12,2), average_quantity_pending_removal numeric(12,2), estimated_total_item_volume numeric(14,6),
  month_of_charge text NOT NULL, storage_utilization_ratio numeric(10,2), storage_utilization_ratio_units text,
  base_rate numeric(10,4), utilization_surcharge_rate numeric(10,4), avg_qty_for_sus numeric(12,2), est_vol_for_sus numeric(14,6),
  est_base_msf numeric(12,4), est_sus numeric(12,4), currency text, estimated_monthly_storage_fee numeric(12,4),
  category text, eligible_for_inventory_discount text, qualifies_for_inventory_discount text,
  total_incentive_fee_amount numeric(12,4), breakdown_incentive_fee_amount text, average_quantity_customer_orders numeric(12,2),
  report_id text, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (asin, fnsku, fulfillment_center, month_of_charge)
);
CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_fba_reimbursements (
  approval_date timestamptz, reimbursement_id text NOT NULL, case_id text, amazon_order_id text, reason text,
  sku text NOT NULL, fnsku text, asin text NOT NULL, product_name text, condition text, currency_unit text,
  amount_per_unit numeric(12,2), amount_total numeric(12,2),
  quantity_reimbursed_cash integer, quantity_reimbursed_inventory integer, quantity_reimbursed_total integer,
  original_reimbursement_id text, original_reimbursement_type text,
  report_id text, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (reimbursement_id, sku, asin)
);
CREATE INDEX IF NOT EXISTS raw_fba_storage_month_idx ON kabinet_data.raw_amazon_fba_storage_fees (month_of_charge, country_code);
CREATE INDEX IF NOT EXISTS raw_fba_reimb_date_idx ON kabinet_data.raw_amazon_fba_reimbursements (approval_date);
-- джоб бежит под принципалом Claude Code, страницы — под принципалом Кабинета
GRANT SELECT, INSERT, UPDATE ON kabinet_data.raw_amazon_fba_storage_fees, kabinet_data.raw_amazon_fba_reimbursements
   TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.raw_amazon_fba_storage_fees, kabinet_data.raw_amazon_fba_reimbursements
   TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
