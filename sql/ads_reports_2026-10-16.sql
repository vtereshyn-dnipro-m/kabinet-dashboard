-- Отчёты Amazon Ads (nb/ads_reports_loader.py, джоба «Kabinet - Amazon Ads Reports»). Выполнять ПОСЛЕ создания джобы
-- (nb/jobs/ads_reports_2026-10-16/create_ads_reports.json): вместо <JOB_ID> — id, который вернёт `databricks jobs create`.
-- Имя — символ в символ как в Databricks и в метке system_pulse ноутбука.
-- 26 ч: джоба ежедневная в 07:10 Kyiv. Пропуск дороже обычного: Amazon хранит поисковые запросы SP 95 дней, SB 60 —
-- что не забрали, потеряно навсегда.
BEGIN;
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('ads_reports_reread_days', 30,
  'Отчёты Amazon Ads: сколько последних дней перечитывать каждым прогоном (атрибуция продаж закрывается за 14 дней)', now())
ON CONFLICT (key) DO NOTHING;
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID>, 'Kabinet - Amazon Ads Reports', 26, '07:10 Kyiv daily',
        'Отчёты Amazon Ads: таргетинг, плейсменты, поисковые запросы SP/SB, невалидный трафик; источник nb/ads_reports_loader.py')
ON CONFLICT DO NOTHING;
COMMIT;
SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Amazon Ads Reports';
SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'ads_reports_reread_days';
