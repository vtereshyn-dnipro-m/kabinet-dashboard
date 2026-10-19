-- Проверка прогонов джоб Amazon API (19.10.2026, «закрываем тему квоты», пункт 1). Применять ПОСЛЕ мержа.
-- Права на таблицы — явными грантами ниже; джоба Kabinet - Amazon Run Check идёт под владельцем базы.
-- :check_job_id — id джобы из `databricks jobs create` (nb/jobs/amazon_run_check_2026-10-19).

-- Реестр джоб Amazon API: наши, Дарины, Listing Suite (сканирование кода всех ноутбуков 19.10.2026 — вызовы
-- sellingpartnerapi / dataKiosk / advertising-api). tables — таблицы Unity Catalog, которые джоба пишет (lineage UC за
-- 14 дней, только таблицы); по ним проверяется, был ли коммит этой джобы во время прогона. check_write = false —
-- пишут только в Lakebase, на паузе, доборы или законно пишут не каждый раз (Settlements, SQP): только состояние и 429.
-- Журналы запусков (sync_log, economics_load_runs, amc_run_log) в tables НЕ входят: они пишутся каждым прогоном, даже
-- когда данные не легли, — с ними «записал» было бы всегда «да». У SendCloud — только таблицы заказов Amazon: таблицы
-- SendCloud обновляются и без ответа Amazon.
CREATE TABLE IF NOT EXISTS kabinet_data.amazon_api_jobs (
    job_id      bigint PRIMARY KEY,
    job_name    text NOT NULL,
    owner       text NOT NULL CHECK (owner IN ('kabinet', 'darina', 'listing_suite')),
    check_write boolean NOT NULL DEFAULT false,
    tables      text[],
    is_active   boolean NOT NULL DEFAULT true,
    note        text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.amazon_api_jobs IS
  'Джобы Amazon API (наши, Дарины, Listing Suite) для Kabinet - Amazon Run Check; новую отчётную джобу — сюда же.';

INSERT INTO kabinet_data.amazon_api_jobs (job_id, job_name, owner, check_write, tables) VALUES
  (520728352816387, 'Amazon Ads API for Tableau (First)', 'darina', false, NULL),
  (117677202912960, 'Amazon Ads API for Tableau (Second)', 'darina', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_be', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_de', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_fr', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_campaign_it', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_purchased_product_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_purchased_product_it', 'dnipro_m.dnipro_m.raw_amazon_ads_sd_advertised_product_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sd_campaign_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_advertised_product_de', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_advertised_product_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_advertised_product_fr', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_advertised_product_it', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_de', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_fr', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_campaign_it', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_purchased_product_de', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_purchased_product_es', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_purchased_product_fr', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_purchased_product_it']::text[]),
  (917636032470555, 'FBA Fees + Listings data for Tableau', 'darina', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_fba_fee_preview_report', 'dnipro_m.dnipro_m.raw_amazon_fees_estimate', 'dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data', 'dnipro_m.dnipro_m.raw_amazon_seller_central_pricing_de', 'dnipro_m.dnipro_m.raw_amazon_seller_central_pricing_es', 'dnipro_m.dnipro_m.raw_amazon_seller_central_pricing_fr', 'dnipro_m.dnipro_m.raw_amazon_seller_central_pricing_it']::text[]),
  (697545970063925, 'FBA Inventory Ledger Summary for Tableau', 'darina', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_fba_inventory_ledger_summary']::text[]),
  (450852904255938, 'Sales & Traffic Report for Tableau', 'darina', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_be', 'dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_de', 'dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_es', 'dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_fr', 'dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_it', 'dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_uk']::text[]),
  (240320825848727, 'SendCloud tracking for Tableau', 'darina', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_central_get_order_items', 'dnipro_m.dnipro_m.raw_amazon_seller_central_get_orders']::text[]),
  (990635019399469, 'Kabinet - AMC Collect', 'kabinet', true, ARRAY['dnipro_m.kabinet_data.amc_attribution', 'dnipro_m.kabinet_data.amc_brand_halo', 'dnipro_m.kabinet_data.amc_campaign_asin', 'dnipro_m.kabinet_data.amc_dayparting', 'dnipro_m.kabinet_data.amc_frequency', 'dnipro_m.kabinet_data.amc_halo_relevance', 'dnipro_m.kabinet_data.amc_household', 'dnipro_m.kabinet_data.amc_new_to_brand', 'dnipro_m.kabinet_data.amc_ntb_by_asin', 'dnipro_m.kabinet_data.amc_overlap', 'dnipro_m.kabinet_data.amc_path_to_conversion', 'dnipro_m.kabinet_data.amc_search_terms', 'dnipro_m.kabinet_data.amc_view_vs_click']::text[]),
  (383948740025305, 'Kabinet - Account Health Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_performance']::text[]),
  (973993248085353, 'Kabinet - Amazon Ads Invoices', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_ads_invoice_fees', 'dnipro_m.dnipro_m.raw_amazon_ads_invoices']::text[]),
  (1093891041490814, 'Kabinet - Amazon Ads Reports', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_ads_gross_invalid', 'dnipro_m.dnipro_m.raw_amazon_ads_sb_search_term', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_placement', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_search_term', 'dnipro_m.dnipro_m.raw_amazon_ads_sp_targeting']::text[]),
  (897574936559645, 'Kabinet - Amazon Auth Guard', 'kabinet', false, NULL),
  (1079009893242956, 'Kabinet - Amazon Finances Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_finances_breakdowns', 'dnipro_m.dnipro_m.raw_amazon_finances_transactions']::text[]),
  (907284097553767, 'Kabinet - Amazon Promotions Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_analytics_promotions']::text[]),
  (376510559038967, 'Kabinet - BSR Daily', 'kabinet', false, NULL),
  (807913225672389, 'Kabinet - Brand Analytics Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_ba_market_basket', 'dnipro_m.dnipro_m.raw_amazon_ba_search_terms']::text[]),
  (1086620628061334, 'Kabinet - Buy Box', 'kabinet', false, NULL),
  (141624524256209, 'Kabinet - Economics DK Backfill', 'kabinet', false, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_analytics_promotions', 'dnipro_m.kabinet.economics_daily', 'dnipro_m.kabinet.economics_fees']::text[]),
  (1029400291008022, 'Kabinet - Economics Loader', 'kabinet', true, ARRAY['dnipro_m.kabinet.economics_daily', 'dnipro_m.kabinet.economics_fees']::text[]),
  (1070371622017059, 'Kabinet - FBA Charges Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_fba_reimbursements', 'dnipro_m.dnipro_m.raw_amazon_fba_storage_fees']::text[]),
  (174154625041145, 'Kabinet - FBA Ledger Detail + Listing Cards Sync', 'kabinet', true, ARRAY['dnipro_m.kabinet_data.fba_ledger_detail']::text[]),
  (892524372824225, 'Kabinet - FBA Ledger Detail Loader', 'kabinet', false, NULL),
  (821057250140489, 'Kabinet - FBA Shipments Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_fulfilled_shipments']::text[]),
  (73306181318180, 'Kabinet - Inventory Age Loader', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_fba_inventory_planning']::text[]),
  (182571468632740, 'Kabinet - Listing Issues Loader', 'kabinet', false, NULL),
  (565517931588672, 'Kabinet - MYI Report Collector', 'kabinet', true, ARRAY['dnipro_m.kabinet_data.raw_amazon_fba_myi_inventory']::text[]),
  (32626547834069, 'Kabinet - Plan Matrix Prices', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_listing_offers']::text[]),
  (362902033206612, 'Kabinet - Returns Backfill', 'kabinet', false, NULL),
  (1088358634966851, 'Kabinet - Returns Loader', 'kabinet', true, ARRAY['dnipro_m.kabinet_data.raw_amazon_returns']::text[]),
  (760565204236769, 'Kabinet - Review Requests (ES Evening)', 'kabinet', false, NULL),
  (504383462189415, 'Kabinet - Review Requests (Morning)', 'kabinet', false, NULL),
  (32157082853424, 'Kabinet - Sales & Traffic Replica', 'kabinet', true, ARRAY['dnipro_m.dnipro_m.raw_amazon_seller_analytics_traffic']::text[]),
  (1086798073703615, 'Kabinet - Settlements Loader', 'kabinet', false, ARRAY['dnipro_m.dnipro_m.raw_amazon_settlements']::text[]),
  (73765434361584, 'Kabinet - Storage Fees Backfill', 'kabinet', false, NULL),
  (474477518393306, 'Kabinet - Suppressed Listings Checker', 'kabinet', false, NULL),
  (89677076782805, 'Listing Suite Auto Collector', 'listing_suite', false, NULL),
  (597550726435861, 'Listing Suite SQP Loader', 'listing_suite', false, ARRAY['dnipro_m.kabinet_data.sqp_weekly']::text[]),
  (45883686210360, 'Listing Suite SQP Loader v2', 'listing_suite', false, NULL),
  (735430499286592, 'Listing Suite Sync Catalog Items', 'listing_suite', false, NULL),
  (72724480158998, 'listing-suite-auto-collect', 'listing_suite', false, NULL)
ON CONFLICT (job_id) DO NOTHING;

-- Результат по каждому прогону. wrote: true — коммит в одну из таблиц джобы во время прогона, false — коммитов нет,
-- NULL — не проверялось (check_write false, прогон упал, история не прочиталась). n429 — отказов 429 в выводе
-- (один отказ — одно совпадение), NULL — вывод не прочитан.
CREATE TABLE IF NOT EXISTS kabinet_data.amazon_run_checks (
    run_id      bigint PRIMARY KEY,
    job_id      bigint NOT NULL,
    job_name    text NOT NULL,
    owner       text NOT NULL,
    started_at  timestamptz NOT NULL,
    ended_at    timestamptz,
    state       text NOT NULL,
    wrote       boolean,
    tables      text,
    n429        int,
    kinds_429   text,
    checked_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS amazon_run_checks_job_started_idx ON kabinet_data.amazon_run_checks (job_id, started_at DESC);
COMMENT ON TABLE kabinet_data.amazon_run_checks IS
  'Прогоны джоб Amazon API: успех, запись в таблицы UC (по истории таблиц), 429. Пишет Kabinet - Amazon Run Check.';

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('amazon_check_lag_min', 15, 'Amazon Run Check: прогон проверяется не раньше стольких минут после конца — даём лечь последнему коммиту')
ON CONFLICT (key) DO NOTHING;

-- Тип тревоги «зелёная, но без записи»: два подряд успешных прогона без коммита в таблицы. Ежедневно в сводке сторожа.
-- Задача ClickUp — в тот же список и той же группе исполнителей, что у job_health (то же «джоба не сделала свою
-- работу»), срок 1 день; enabled_since — день применения: тревоги с этого дня получают задачу.
INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, due_days, watch_close, telegram_digest,
                                         clickup_list_id, clickup_list_name, assignee_group_id, assignee_group_name,
                                         enabled_since, title, description, note, updated_by)
SELECT 'silent_success', 'task', 'High', 1, true, 'daily', clickup_list_id, clickup_list_name,
       assignee_group_id, assignee_group_name, DATE '2026-10-19',
       'Джоба Amazon успешна, но не записала данные',
       'Два успешных прогона подряд без единого коммита в таблицы Unity Catalog — данные не обновились (429, пустой ответ, пропуск в try).',
       'Kabinet - Amazon Run Check; закрывается сама, когда следующий прогон записал таблицы', 'claude_code'
FROM kabinet_data.incident_types WHERE incident_type = 'job_health'
ON CONFLICT (incident_type) DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_api_jobs, kabinet_data.amazon_run_checks TO claude_code_rw;
GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_api_jobs, kabinet_data.amazon_run_checks TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.amazon_api_jobs, kabinet_data.amazon_run_checks TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.amazon_api_jobs, kabinet_data.amazon_run_checks TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- ── вторая часть: после `databricks jobs create` ──
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:check_job_id, 'Kabinet - Amazon Run Check', 3, 'каждый час в :50 Kyiv', true,
        'Прогоны джоб Amazon API: успех, запись в таблицы, 429; тревога silent_success')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
