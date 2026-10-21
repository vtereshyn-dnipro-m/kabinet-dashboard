-- Сервисный принципал джоб kabinet-jobs-sp (вариант В, 22.10.2026): SQL «только добавить». Ничего не забирает —
-- claude-uc-ro и account users работают как прежде, пока джобы переводятся по одной. Применяет ВЛАДЕЛЕЦ, после мержа и
-- после создания принципала (docs/kabinet-jobs-sp.md, шаги 1–2).
--
-- Часть A — psql под владельцем базы (переменные :sp / :"sp" / :'sp' — только в psql, SQL-редактор Lakebase их не знает):
--   psql "<строка подключения владельца>" -v sp=<APPLICATION_ID> -v ON_ERROR_STOP=1 -1 -f <часть A этого файла>
-- -1 — одна транзакция: упало на любой строке — не применилось ничего.
--
-- Права выгружены из каталога Postgres (aclexplode по pg_class.relacl / pg_namespace.nspacl / pg_default_acl), а НЕ из
-- information_schema.role_table_grants: то видит только гранты с участием спрашивающей роли и 21.10 дало 120 объектов
-- вместо 219 — без system_pulse, orders_history, raw_lm_*/raw_mm_*/raw_cf_*, и все джобы упали бы на первом прогоне.

-- ── Часть A. Lakebase Кабинета ──
-- A1. Роль принципала — функцией Databricks (public.databricks_create_role(text, text), есть в базе). Без роли первый
--     же GRANT упадёт. Если роль уже заведена в интерфейсе Lakebase — эту строку пропустить.
SELECT databricks_create_role(:'sp', 'SERVICE_PRINCIPAL');
-- A2. Схема — как у claude-uc-ro: только USAGE.
GRANT USAGE ON SCHEMA kabinet_data TO :"sp";
-- A3. Таблицы и вью — ровно те права, что у claude-uc-ro (b1698364-…) на 22.10.2026: 219 объектов, из них с
--     записью 66. SELECT на всё, запись — где она есть у него.
GRANT SELECT ON TABLE kabinet_data.amc_attribution_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_campaign_asin_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_dayparting_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_new_to_brand_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_ntb_by_asin_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_overlap_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_search_terms_sync TO :"sp";
GRANT SELECT ON TABLE kabinet_data._sku_sales_lookup TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_actions TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_alerts TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_campaign_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_fees_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_invalid_traffic_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_invoices TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.ads_market_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_placement_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_search_term_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ads_spend TO :"sp";
GRANT SELECT, UPDATE ON TABLE kabinet_data.agent_cycle_reports TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.amazon_api_jobs TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.amazon_dk_query_log TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.amazon_report_log TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.amazon_report_types TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.amazon_run_checks TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.app_action_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.app_permissions TO :"sp";
GRANT SELECT ON TABLE kabinet_data.app_users TO :"sp";
GRANT SELECT ON TABLE kabinet_data.asin_bsr_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.asin_reviews_daily TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.assortment_admissions TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.assortment_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.assortment_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.assortment_representations TO :"sp";
GRANT SELECT ON TABLE kabinet_data.ba_search_term_rules TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.buybox_status TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.category_names TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.clickup_sync_state TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.clickup_tasks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.commercial_roles TO :"sp";
GRANT SELECT ON TABLE kabinet_data.commission_rates TO :"sp";
GRANT SELECT ON TABLE kabinet_data.countries TO :"sp";
GRANT SELECT ON TABLE kabinet_data.country_change_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.country_names TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.coverage_norm_rules TO :"sp";
GRANT SELECT ON TABLE kabinet_data.coverage_norms TO :"sp";
GRANT SELECT ON TABLE kabinet_data.coverage_projection TO :"sp";
GRANT SELECT ON TABLE kabinet_data.coverage_projection_plan TO :"sp";
GRANT SELECT ON TABLE kabinet_data.coverage_summary TO :"sp";
GRANT SELECT ON TABLE kabinet_data.currencies TO :"sp";
GRANT SELECT ON TABLE kabinet_data.daily_availability_history TO :"sp";
GRANT SELECT ON TABLE kabinet_data.data_freshness_rules TO :"sp";
GRANT SELECT, UPDATE ON TABLE kabinet_data.data_source_origins TO :"sp";
GRANT SELECT ON TABLE kabinet_data.draft_orders TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.economics_logistics TO :"sp";
GRANT SELECT ON TABLE kabinet_data.economics_summary TO :"sp";
GRANT SELECT ON TABLE kabinet_data.fba_fulfillment_centers TO :"sp";
GRANT SELECT ON TABLE kabinet_data.fba_inventory TO :"sp";
GRANT SELECT ON TABLE kabinet_data.fba_ledger_detail TO :"sp";
GRANT SELECT ON TABLE kabinet_data.forecast_alert_rules TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.forecast_change_log TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.forecast_composition_snapshot TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.forecast_documents TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.forecast_register TO :"sp";
GRANT SELECT ON TABLE kabinet_data.forecast_replacement_items TO :"sp";
GRANT SELECT ON TABLE kabinet_data.forecast_replacements TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.incident_types TO :"sp";
GRANT SELECT, UPDATE ON TABLE kabinet_data.incidents TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.job_dependencies TO :"sp";
GRANT SELECT ON TABLE kabinet_data.job_health_rules TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.job_schedule_changes TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.job_schedule_snapshot TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.job_systems TO :"sp";
GRANT SELECT ON TABLE kabinet_data.listing_cards TO :"sp";
GRANT SELECT ON TABLE kabinet_data.listing_issues TO :"sp";
GRANT DELETE, INSERT, SELECT ON TABLE kabinet_data.load_day_snapshots TO :"sp";
GRANT SELECT ON TABLE kabinet_data.marketplace_attributes TO :"sp";
GRANT SELECT ON TABLE kabinet_data.marketplace_change_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.marketplaces_legacy TO :"sp";
GRANT SELECT ON TABLE kabinet_data.marketplaces_new TO :"sp";
GRANT SELECT ON TABLE kabinet_data.mirakl_health_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.mm_brands TO :"sp";
GRANT SELECT ON TABLE kabinet_data.mm_categories TO :"sp";
GRANT SELECT ON TABLE kabinet_data.mm_competitiveness TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.morning_reports TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.odoo_return_def_outcomes TO :"sp";
GRANT SELECT ON TABLE kabinet_data.orders_history TO :"sp";
GRANT SELECT ON TABLE kabinet_data.organizations TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pbi_orders_report TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.pbi_replica_meta TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pbi_self_heal_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pbi_sku_categories TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pbi_source_jobs TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pbi_spiderweb_report TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.plan_price_daily TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.plan_price_month TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.plan_price_sheet_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.platform_attributes TO :"sp";
GRANT SELECT ON TABLE kabinet_data.platforms TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pnl_annotations TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pool_change_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pool_members TO :"sp";
GRANT SELECT ON TABLE kabinet_data.pools TO :"sp";
GRANT SELECT ON TABLE kabinet_data.price_parity TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.product_entities TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.product_entity_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.product_entity_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.product_entity_listings TO :"sp";
GRANT SELECT ON TABLE kabinet_data.qa_tokens TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_amazon_fba_inventory_planning TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_amazon_fba_reimbursements TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_amazon_fba_storage_fees TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_amazon_fulfilled_shipments TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_amazon_returns TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_amazon_seller_performance TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.raw_amazon_settlements TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_amazon_sku_catalog TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_cf_offers TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_cf_order_lines TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_cf_orders TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_cf_transactions TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_ecb_fx_rates TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_erp_translation_en TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_lm_offers TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_lm_order_lines TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_lm_orders TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_lm_transactions TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_mm_offers TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_mm_order_lines TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_mm_orders TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_odoo_channel_sales TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.raw_odoo_customer_returns TO :"sp";
GRANT SELECT ON TABLE kabinet_data.raw_odoo_sku_mapping TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.reconciliation_results TO :"sp";
GRANT SELECT ON TABLE kabinet_data.reorder_params TO :"sp";
GRANT SELECT ON TABLE kabinet_data.reorder_recommendations TO :"sp";
GRANT SELECT ON TABLE kabinet_data.report_quota_jobs TO :"sp";
GRANT SELECT ON TABLE kabinet_data.review_request_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sales_plan TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sales_traffic_asin TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.sales_traffic_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sales_velocity TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.shipment_facts TO :"sp";
GRANT SELECT ON TABLE kabinet_data.shipments_history TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_abc TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_asin_map TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_categories TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_category_links TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_category_tree TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_checks TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_cogs_current TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_composition TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_lifecycle TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_lifecycle_manual TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_margin_threshold TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.sku_master TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sku_target_status TO :"sp";
GRANT SELECT ON TABLE kabinet_data.source_job_checks TO :"sp";
GRANT SELECT ON TABLE kabinet_data.stock_local TO :"sp";
GRANT SELECT ON TABLE kabinet_data.supply_chain_change_log TO :"sp";
GRANT SELECT ON TABLE kabinet_data.supply_chains TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.supply_lead_time_facts TO :"sp";
GRANT SELECT ON TABLE kabinet_data.supply_poland_spain TO :"sp";
GRANT SELECT ON TABLE kabinet_data.sync_log TO :"sp";
GRANT INSERT, SELECT, UPDATE ON TABLE kabinet_data.system_pulse TO :"sp";
GRANT SELECT ON TABLE kabinet_data.telegram_subscribers TO :"sp";
GRANT SELECT ON TABLE kabinet_data.transfer_recommendations TO :"sp";
GRANT INSERT, SELECT ON TABLE kabinet_data.variation_group_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.variation_group_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.variation_groups TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON TABLE kabinet_data.warehouse_attributes TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_countries TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_external_ids TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_marketplaces TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_priorities TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_shipping_schedule TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_stock TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouse_supply_links TO :"sp";
GRANT SELECT ON TABLE kabinet_data.warehouses TO :"sp";
GRANT SELECT ON TABLE kabinet_data.watchdog_heartbeat TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_campaign_asin TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_dayparting TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_new_to_brand TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_ntb_by_asin TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_overlap TO :"sp";
GRANT SELECT ON TABLE kabinet_data.amc_search_terms TO :"sp";
GRANT SELECT ON TABLE kabinet_data.fba_inventory_deduped TO :"sp";
GRANT SELECT ON TABLE kabinet_data.marketplaces TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_ads_market_daily_eur TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_ads_spend_margin TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_amc_attribution TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_amc_ntb_cost TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_buybox_current TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_dependent_demand_current TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_economics_amazon TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_economics_lm TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_economics_summary_eur TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_economics_with_ad_days TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_forecast_current TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_forecast_pool_drift TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_load_day_completeness TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_load_day_completeness_30d TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_margin_adjustments TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_marketplace_data_status TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_marketplace_map TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_marketplaces TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_marketplaces_selectable TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_orders_history_eur TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_returns_cogs_credit TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sales_traffic_daily_eur TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sales_vat_incl_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_settlement_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_abc TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_category_tree TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_composition TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_daily_availability TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_lifecycle_current TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_sku_sales_vat_incl_daily TO :"sp";
GRANT SELECT ON TABLE kabinet_data.v_stock_by_channel TO :"sp";
-- A4. Последовательности — ровно как у него (16; UPDATE у него нет ни на одной).
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.app_action_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_admissions_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_representations_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.clickup_tasks_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_change_log_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_documents_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_register_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.morning_reports_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.pbi_replica_meta_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.plan_price_sheet_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.product_entities_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.product_entity_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.sku_change_log_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.variation_group_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.variation_groups_id_seq TO :"sp";
-- A5. Права по умолчанию на НОВЫЕ таблицы kabinet_data — как у него: иначе каждая новая таблица без отдельного гранта.
ALTER DEFAULT PRIVILEGES FOR ROLE claude_code_rw IN SCHEMA kabinet_data GRANT SELECT ON TABLES TO :"sp";
ALTER DEFAULT PRIVILEGES FOR ROLE "v.tereshyn@dniprom.com" IN SCHEMA kabinet_data GRANT SELECT ON TABLES TO :"sp";

-- ── Часть B. Unity Catalog (SQL-склад, Spark SQL; под владельцем каталога — группа администраторов воркспейса) ──
-- B1. Чтение. Явных грантов у claude-uc-ro в UC мало (USE CATALOG и USE SCHEMA + SELECT на kabinet_data), остальное он
--     получает через account users. Новому — явно на все четыре схемы: когда account users станет «только чтение»,
--     у него не пропадёт ничего. Сейчас (account users — ALL PRIVILEGES и MANAGE на каталог) «только чтение» у нового
--     принципала по факту ещё не действует — это шаг после перевода всех джоб.
-- В Spark SQL подстановки нет — `<sp>` заменить application id руками (в обратных кавычках).
-- GRANT USE CATALOG ON CATALOG dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet_data TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.listing_data TO `<sp>`;
-- B2. Запись — НЕ на этом шаге: первые пять джоб в Unity Catalog не пишут. Для девяти пишущих — вторым PR:
-- GRANT CREATE TABLE, MODIFY ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;   -- и передача владения их 14 таблицами
