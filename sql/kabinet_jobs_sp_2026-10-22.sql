-- Сервисный принципал джоб kabinet-jobs-sp (вариант В, 22.10.2026): SQL «только добавить». Ничего не забирает —
-- claude-uc-ro и account users работают как прежде, пока джобы переводятся по одной. Применяет ВЛАДЕЛЕЦ, после мержа и
-- после создания принципала (docs/kabinet-jobs-sp.md, шаги 1–2). Порядок частей — как в плане.
-- :sp — application id нового принципала (UUID) — подставить перед выполнением.

-- ── Часть A. Lakebase Кабинета (psql / SQL-редактор Lakebase, под владельцем базы) ──
-- A1. Роль принципала. В Lakebase роль сервисного принципала заводит функция Databricks; без неё GRANT некому выдавать.
--     Если роль уже создана через «Lakebase → Roles» в интерфейсе — пропустить.
-- SELECT databricks_create_role(:'sp', 'SERVICE_PRINCIPAL');
GRANT USAGE ON SCHEMA kabinet_data TO :"sp";
-- A2. Те же права, что у claude-uc-ro (b1698364-…) на 21.10.2026: 120 таблиц и вью kabinet_data, выгружено из
--     information_schema.role_table_grants. Новые таблицы с 22.10 — по образцу: гранты «обоим принципалам» в SQL каждого PR
--     теперь значат «приложению и kabinet-jobs-sp» (до конца перехода — и claude-uc-ro).
GRANT SELECT ON kabinet_data.ads_actions TO :"sp";
GRANT SELECT ON kabinet_data.ads_campaign_daily TO :"sp";
GRANT SELECT ON kabinet_data.ads_fees_daily TO :"sp";
GRANT SELECT ON kabinet_data.ads_invalid_traffic_daily TO :"sp";
GRANT SELECT ON kabinet_data.ads_invoices TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.ads_market_daily TO :"sp";
GRANT SELECT ON kabinet_data.ads_placement_daily TO :"sp";
GRANT SELECT ON kabinet_data.ads_search_term_daily TO :"sp";
GRANT SELECT, UPDATE ON kabinet_data.agent_cycle_reports TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.amazon_api_jobs TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.amazon_dk_query_log TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.amazon_report_log TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.amazon_report_types TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.amazon_run_checks TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.app_action_log TO :"sp";
GRANT SELECT ON kabinet_data.app_permissions TO :"sp";
GRANT SELECT ON kabinet_data.app_users TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.assortment_admissions TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.assortment_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.assortment_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.assortment_representations TO :"sp";
GRANT SELECT ON kabinet_data.ba_search_term_rules TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.buybox_status TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.category_names TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.clickup_sync_state TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.clickup_tasks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.commercial_roles TO :"sp";
GRANT SELECT ON kabinet_data.country_change_log TO :"sp";
GRANT SELECT ON kabinet_data.country_names TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.coverage_norm_rules TO :"sp";
GRANT SELECT ON kabinet_data.currencies TO :"sp";
GRANT SELECT, UPDATE ON kabinet_data.data_source_origins TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.economics_logistics TO :"sp";
GRANT SELECT ON kabinet_data.forecast_alert_rules TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.forecast_change_log TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.forecast_composition_snapshot TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.forecast_documents TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.forecast_register TO :"sp";
GRANT SELECT ON kabinet_data.forecast_replacement_items TO :"sp";
GRANT SELECT ON kabinet_data.forecast_replacements TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.incident_types TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.job_dependencies TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.job_schedule_changes TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.job_schedule_snapshot TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.job_systems TO :"sp";
GRANT DELETE, INSERT, SELECT ON kabinet_data.load_day_snapshots TO :"sp";
GRANT SELECT ON kabinet_data.marketplace_attributes TO :"sp";
GRANT SELECT ON kabinet_data.marketplace_change_log TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.morning_reports TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.odoo_return_def_outcomes TO :"sp";
GRANT SELECT ON kabinet_data.pbi_orders_report TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.pbi_replica_meta TO :"sp";
GRANT SELECT ON kabinet_data.pbi_self_heal_log TO :"sp";
GRANT SELECT ON kabinet_data.pbi_sku_categories TO :"sp";
GRANT SELECT ON kabinet_data.pbi_source_jobs TO :"sp";
GRANT SELECT ON kabinet_data.pbi_spiderweb_report TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.plan_price_daily TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.plan_price_month TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.plan_price_sheet_log TO :"sp";
GRANT SELECT ON kabinet_data.platform_attributes TO :"sp";
GRANT SELECT ON kabinet_data.pool_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.product_entities TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.product_entity_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.product_entity_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.product_entity_listings TO :"sp";
GRANT SELECT ON kabinet_data.qa_tokens TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.raw_amazon_fba_inventory_planning TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.raw_amazon_fba_reimbursements TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.raw_amazon_fba_storage_fees TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.raw_amazon_fulfilled_shipments TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.raw_amazon_seller_performance TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.raw_erp_translation_en TO :"sp";
GRANT SELECT ON kabinet_data.raw_odoo_channel_sales TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.raw_odoo_customer_returns TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.reconciliation_results TO :"sp";
GRANT SELECT ON kabinet_data.reorder_params TO :"sp";
GRANT SELECT ON kabinet_data.report_quota_jobs TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sales_traffic_asin TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.shipment_facts TO :"sp";
GRANT INSERT, SELECT, UPDATE ON kabinet_data.sku_categories TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_category_links TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_category_tree TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_checks TO :"sp";
GRANT SELECT ON kabinet_data.sku_cogs_current TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_composition TO :"sp";
GRANT SELECT ON kabinet_data.sku_lifecycle_manual TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.sku_master TO :"sp";
GRANT SELECT ON kabinet_data.source_job_checks TO :"sp";
GRANT SELECT ON kabinet_data.supply_chain_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.supply_lead_time_facts TO :"sp";
GRANT SELECT ON kabinet_data.telegram_subscribers TO :"sp";
GRANT SELECT ON kabinet_data.v_ads_market_daily_eur TO :"sp";
GRANT SELECT ON kabinet_data.v_ads_spend_margin TO :"sp";
GRANT SELECT ON kabinet_data.v_buybox_current TO :"sp";
GRANT SELECT ON kabinet_data.v_dependent_demand_current TO :"sp";
GRANT SELECT ON kabinet_data.v_economics_summary_eur TO :"sp";
GRANT SELECT ON kabinet_data.v_economics_with_ad_days TO :"sp";
GRANT SELECT ON kabinet_data.v_forecast_current TO :"sp";
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO :"sp";
GRANT SELECT ON kabinet_data.v_load_day_completeness TO :"sp";
GRANT SELECT ON kabinet_data.v_load_day_completeness_30d TO :"sp";
GRANT SELECT ON kabinet_data.v_marketplace_data_status TO :"sp";
GRANT SELECT ON kabinet_data.v_marketplaces_selectable TO :"sp";
GRANT SELECT ON kabinet_data.v_orders_history_eur TO :"sp";
GRANT SELECT ON kabinet_data.v_returns_cogs_credit TO :"sp";
GRANT SELECT ON kabinet_data.v_sales_traffic_daily_eur TO :"sp";
GRANT SELECT ON kabinet_data.v_sales_vat_incl_daily TO :"sp";
GRANT SELECT ON kabinet_data.v_sku_abc TO :"sp";
GRANT SELECT ON kabinet_data.v_sku_category_tree TO :"sp";
GRANT SELECT ON kabinet_data.v_sku_lifecycle_current TO :"sp";
GRANT SELECT ON kabinet_data.v_sku_sales_vat_incl_daily TO :"sp";
GRANT INSERT, SELECT ON kabinet_data.variation_group_change_log TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.variation_group_checks TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.variation_groups TO :"sp";
GRANT DELETE, INSERT, SELECT, UPDATE ON kabinet_data.warehouse_attributes TO :"sp";
GRANT SELECT ON kabinet_data.warehouse_countries TO :"sp";
GRANT SELECT ON kabinet_data.warehouse_external_ids TO :"sp";
GRANT SELECT ON kabinet_data.warehouse_priorities TO :"sp";
GRANT SELECT ON kabinet_data.warehouse_shipping_schedule TO :"sp";
-- A3. Последовательности таблиц с автоинкрементом — без USAGE вставка падает на nextval
GRANT USAGE, UPDATE ON SEQUENCE kabinet_data.app_action_log_id_seq, kabinet_data.assortment_admissions_id_seq, kabinet_data.assortment_change_log_id_seq, kabinet_data.assortment_representations_id_seq, kabinet_data.clickup_tasks_id_seq, kabinet_data.forecast_change_log_id_seq, kabinet_data.forecast_documents_id_seq, kabinet_data.forecast_register_id_seq, kabinet_data.morning_reports_id_seq, kabinet_data.pbi_replica_meta_id_seq, kabinet_data.plan_price_sheet_log_id_seq, kabinet_data.product_entities_id_seq, kabinet_data.product_entity_change_log_id_seq, kabinet_data.sku_change_log_id_seq, kabinet_data.variation_group_change_log_id_seq, kabinet_data.variation_groups_id_seq TO :"sp";

-- ── Часть B. Unity Catalog (SQL-склад, Spark SQL; под владельцем каталога — группа администраторов воркспейса) ──
-- B1. Чтение — всем пяти джобам первого шага и остальным: каталог и схемы, как у claude-uc-ro явными грантами.
-- GRANT USE CATALOG ON CATALOG dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet_data TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.listing_data TO `<sp>`;
-- B2. Запись — НЕ на первом шаге: первые пять джоб в Unity Catalog не пишут. Для девяти пишущих (второй шаг, отдельный PR):
-- GRANT CREATE TABLE, MODIFY ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;   -- и передача владения их 14 таблицами
-- В Spark SQL нет подстановки :sp — `<sp>` заменить application id руками (в обратных кавычках).
