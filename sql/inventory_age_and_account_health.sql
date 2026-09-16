-- 15.09.2026. Реплики двух новых источников (сырьё — в dnipro_m.raw_*, это копии для страниц).
-- Таблицы создаёт claude_code_rw, пишет сервис-принципал (джобы run_as SP), читает claude_code_ro.

CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_fba_inventory_planning (
    marketplace TEXT NOT NULL, snapshot_date DATE NOT NULL, sku TEXT NOT NULL, fnsku TEXT, asin TEXT, product_name TEXT, condition TEXT,
    available INT, pending_removal_qty INT,
    age_0_90 INT, age_91_180 INT, age_181_270 INT, age_271_365 INT, age_366_455 INT, age_456_plus INT,
    currency TEXT, units_shipped_t30 INT, units_shipped_t90 INT, your_price NUMERIC(12,2),
    recommended_action TEXT, recommended_removal_qty INT, sell_through NUMERIC(10,4), days_of_supply INT, estimated_excess_qty INT,
    est_storage_cost_next_month NUMERIC(12,2),
    ais_qty_271_300 INT, ais_est_271_300 NUMERIC(12,2), ais_qty_301_330 INT, ais_est_301_330 NUMERIC(12,2),
    ais_qty_331_365 INT, ais_est_331_365 NUMERIC(12,2), ais_qty_366_455 INT, ais_est_366_455 NUMERIC(12,2),
    ais_qty_456_plus INT, ais_est_456_plus NUMERIC(12,2),
    alert TEXT, inventory_health_status TEXT, unfulfillable_qty INT, reserved_qty INT,
    report_id TEXT, loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (marketplace, snapshot_date, sku)
);
COMMENT ON TABLE kabinet_data.raw_amazon_fba_inventory_planning IS
  'Реплика GET_FBA_INVENTORY_PLANNING_DATA (Kabinet - Inventory Age Loader): возраст запасов FBA по корзинам, надбавка за возраст (AIS), плата за хранение. Первоисточник dnipro_m.raw_amazon_fba_inventory_planning';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_seller_performance (
    report_date DATE NOT NULL, marketplace TEXT NOT NULL, account_status TEXT,
    ahr_status TEXT, ahr_score NUMERIC(8,2),
    odr_afn_rate NUMERIC(10,6), odr_afn_status TEXT, odr_afn_orders INT, odr_afn_defects INT,
    odr_mfn_rate NUMERIC(10,6), odr_mfn_status TEXT, odr_mfn_orders INT, odr_mfn_defects INT, odr_mfn_claims INT, odr_mfn_negative_feedback INT,
    late_shipment_rate NUMERIC(10,6), late_shipment_status TEXT, late_shipment_count INT, late_shipment_orders INT,
    cancellation_rate NUMERIC(10,6), cancellation_status TEXT, cancellation_count INT,
    on_time_delivery_rate NUMERIC(10,6), on_time_delivery_status TEXT,
    valid_tracking_rate NUMERIC(10,6), valid_tracking_status TEXT,
    invoice_defect_rate NUMERIC(10,6), invoice_defect_status TEXT,
    listing_policy_violations INT, listing_policy_status TEXT,
    ip_complaints_received INT, ip_violations_suspected INT, authenticity_complaints INT, condition_complaints INT,
    safety_complaints INT, food_safety_issues INT, restricted_product_violations INT, review_policy_violations INT,
    other_policy_violations INT, document_requests INT, policy_warnings INT,
    warning_states TEXT, report_id TEXT, loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (report_date, marketplace)
);
COMMENT ON TABLE kabinet_data.raw_amazon_seller_performance IS
  'Реплика GET_V2_SELLER_PERFORMANCE_REPORT (Kabinet - Account Health Loader): статус аккаунта, AHR, ODR/LSR/отмены/трекинг/доставка, нарушения политик по рынкам. Первоисточник dnipro_m.raw_amazon_seller_performance';

GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.raw_amazon_fba_inventory_planning, kabinet_data.raw_amazon_seller_performance
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.raw_amazon_fba_inventory_planning, kabinet_data.raw_amazon_seller_performance TO claude_code_ro;

-- Джобы созданы сервис-принципалом 15.09.2026, тихое окно квоты createReport.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note) VALUES
 (73306181318180,  'Kabinet - Inventory Age Loader',   30, '04:15 Kyiv daily', 'GET_FBA_INVENTORY_PLANNING_DATA по ES/DE/FR/IT: возраст запасов, AIS, хранение'),
 (383948740025305, 'Kabinet - Account Health Loader',  30, '04:45 Kyiv daily', 'GET_V2_SELLER_PERFORMANCE_REPORT по 8 рынкам: AHR, ODR, нарушения политик')
ON CONFLICT DO NOTHING;
