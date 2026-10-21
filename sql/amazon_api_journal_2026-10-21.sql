-- Журнал Amazon API (21.10.2026, «закрываем тему квоты», пункт 4): getReports и Data Kiosk getQueries раз в час.
-- Применять ПОСЛЕ мержа и ДО создания джобы. :journal_job_id — id джобы из nb/jobs/amazon_api_journal_2026-10-21.

-- Типы отчётов, которые журнал спрашивает у getReports (Amazon требует список, не больше 10 за запрос). Список —
-- по коду ноутбуков всех джоб из amazon_api_jobs (21.10.2026); jobs — кто создаёт (по коду, справка, не связь).
-- Новый отчётный загрузчик — его тип строкой сюда, иначе журнал его отчётов не увидит.
CREATE TABLE IF NOT EXISTS kabinet_data.amazon_report_types (
    report_type text PRIMARY KEY,
    jobs        text,
    is_active   boolean NOT NULL DEFAULT true,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.amazon_report_types IS
  'Типы отчётов SP-API, которые Kabinet - Amazon API Journal спрашивает у getReports; новый загрузчик — тип сюда.';
INSERT INTO kabinet_data.amazon_report_types (report_type, jobs) VALUES
  ('GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL', 'kabinet:Kabinet - FBA Shipments Loader'),
  ('GET_BRAND_ANALYTICS_MARKET_BASKET_REPORT', 'kabinet:Kabinet - Brand Analytics Loader'),
  ('GET_BRAND_ANALYTICS_SEARCH_CATALOG_PERFORMANCE_REPORT', 'listing_suite:Listing Suite SQP Loader v2'),
  ('GET_BRAND_ANALYTICS_SEARCH_QUERY_PERFORMANCE_REPORT', 'listing_suite:Listing Suite SQP Loader; listing_suite:Listing Suite SQP Loader v2'),
  ('GET_BRAND_ANALYTICS_SEARCH_TERMS_REPORT', 'kabinet:Kabinet - Brand Analytics Loader'),
  ('GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA', 'darina:FBA Fees + Listings data for Tableau'),
  ('GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA', 'kabinet:Kabinet - FBA Charges Loader; kabinet:Kabinet - Returns Backfill; kabinet:Kabinet - Returns Loader; kabinet:Kabinet - Storage Fees Backfill'),
  ('GET_FBA_INVENTORY_AGED_DATA', 'kabinet:Kabinet - Inventory Age Loader'),
  ('GET_FBA_INVENTORY_PLANNING_DATA', 'kabinet:Kabinet - Inventory Age Loader'),
  ('GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA', 'kabinet:Kabinet - MYI Report Collector'),
  ('GET_FBA_REIMBURSEMENTS_DATA', 'kabinet:Kabinet - FBA Charges Loader; kabinet:Kabinet - Storage Fees Backfill'),
  ('GET_FBA_STORAGE_FEE_CHARGES_DATA', 'kabinet:Kabinet - FBA Charges Loader; kabinet:Kabinet - Storage Fees Backfill'),
  ('GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE', 'kabinet:Kabinet - FBA Charges Loader; kabinet:Kabinet - Returns Backfill; kabinet:Kabinet - Returns Loader; kabinet:Kabinet - Storage Fees Backfill'),
  ('GET_LEDGER_DETAIL_VIEW_DATA', 'kabinet:Kabinet - FBA Ledger Detail + Listing Cards Sync; kabinet:Kabinet - FBA Ledger Detail Loader'),
  ('GET_LEDGER_SUMMARY_VIEW_DATA', 'darina:FBA Inventory Ledger Summary for Tableau'),
  ('GET_MERCHANT_LISTINGS_ALL_DATA', 'darina:FBA Fees + Listings data for Tableau; kabinet:Kabinet - Plan Matrix Prices'),
  ('GET_MERCHANT_LISTINGS_INACTIVE_DATA', 'kabinet:Kabinet - Suppressed Listings Checker'),
  ('GET_SALES_AND_TRAFFIC_REPORT', 'darina:Sales & Traffic Report for Tableau; kabinet:Kabinet - Economics Loader; kabinet:Kabinet - Sales & Traffic Replica'),
  ('GET_V2_SELLER_PERFORMANCE_REPORT', 'kabinet:Kabinet - Account Health Loader'),
  ('GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2', 'kabinet:Kabinet - Settlements Loader')
ON CONFLICT (report_type) DO NOTHING;

-- Отчёты SP-API на аккаунте продавца — кем бы ни созданы. Статус обновляется, пока отчёт виден в окне журнала.
CREATE TABLE IF NOT EXISTS kabinet_data.amazon_report_log (
    report_id         text PRIMARY KEY,
    report_type       text NOT NULL,
    processing_status text,
    created_time      timestamptz,
    processing_start  timestamptz,
    processing_end    timestamptz,
    marketplace_ids   text,
    data_start        timestamptz,
    data_end          timestamptz,
    schedule_id       text,
    seen_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS amazon_report_log_created_idx ON kabinet_data.amazon_report_log (created_time DESC);
COMMENT ON TABLE kabinet_data.amazon_report_log IS
  'Журнал getReports: отчёты SP-API аккаунта (наши, витрины, Listing Suite), статус и время. Пишет Kabinet - Amazon API Journal.';

-- Запросы Data Kiosk: набор (dataset) — из текста запроса, сам запрос не храним.
CREATE TABLE IF NOT EXISTS kabinet_data.amazon_dk_query_log (
    query_id          text PRIMARY KEY,
    processing_status text,
    created_time      timestamptz,
    processing_start  timestamptz,
    processing_end    timestamptz,
    dataset           text,
    seen_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS amazon_dk_query_log_created_idx ON kabinet_data.amazon_dk_query_log (created_time DESC);
COMMENT ON TABLE kabinet_data.amazon_dk_query_log IS
  'Журнал Data Kiosk getQueries: запросы аккаунта, статус и время. Пишет Kabinet - Amazon API Journal.';

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('amazon_journal_window_h', 26, 'Amazon API Journal: окно getReports/getQueries — каждый прогон целиком за столько часов (долгие отчёты и 429 не теряются, статусы дозревают)')
ON CONFLICT (key) DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_report_types, kabinet_data.amazon_report_log,
    kabinet_data.amazon_dk_query_log TO claude_code_rw;
GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_report_types, kabinet_data.amazon_report_log,
    kabinet_data.amazon_dk_query_log TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.amazon_report_types, kabinet_data.amazon_report_log,
    kabinet_data.amazon_dk_query_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_report_types, kabinet_data.amazon_report_log,
    kabinet_data.amazon_dk_query_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- ── вторая часть: после `databricks jobs create` ──
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:journal_job_id, 'Kabinet - Amazon API Journal', 3, 'каждый час в :40 Kyiv', true,
        'Журнал getReports и Data Kiosk getQueries: какие отчёты и запросы созданы на аккаунте, кем бы ни были')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;

-- Сама джоба — тоже джоба Amazon API (docs/facts/monitoring.md: новую заводить в реестр тем же PR): её видит Amazon Run
-- Check и утренняя сводка. Запись — по seen_at журнала: его обновляет каждый прогон (upsert), без записи значит «не опросил»
INSERT INTO kabinet_data.amazon_api_jobs (job_id, job_name, owner, check_write, pg_db, pg_table, pg_ts_col, note)
VALUES (:journal_job_id, 'Kabinet - Amazon API Journal', 'kabinet', true, 'kabinet', 'kabinet_data.amazon_report_log',
        'seen_at', 'журнал getReports / getQueries с 21.10.2026')
ON CONFLICT (job_id) DO NOTHING;
