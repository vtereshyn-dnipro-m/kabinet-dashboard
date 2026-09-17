-- 17.09.2026. Джоб Listing Suite - Snapshots Replica (695543348458182): listing_data.listing_snapshots (Lakebase listing-suite)
-- → dnipro_m.raw_amazon_listing_snapshots, ежедневно 15:30 Kyiv, инкремент по fetched_at, MERGE по id.
-- Пишет сервис-принципал — ему нужна роль в Lakebase listing-suite (ноутбук grant_listing_suite_role.py у владельца).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (695543348458182, 'Listing Suite - Snapshots Replica', 30, '15:30 Kyiv daily', 'реплика listing_data.listing_snapshots → dnipro_m.raw_amazon_listing_snapshots для Дарины')
ON CONFLICT DO NOTHING;
