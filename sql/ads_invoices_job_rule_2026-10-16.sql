-- Правило сторожа для «Kabinet - Amazon Ads Invoices». Выполнять ПОСЛЕ создания джобы
-- (nb/jobs/ads_invoices_2026-10-16/create_ads_invoices.json): вместо <JOB_ID> — id, который вернёт
-- `databricks jobs create`. Имя — символ в символ как в Databricks и в метке system_pulse ноутбука.
-- 26 ч: джоба ежедневная в 08:50 Kyiv. Таблицы — в Unity Catalog (dnipro_m), в Lakebase реплики нет:
-- Кабинет их пока не читает (как сбор попадёт в маржу — отдельное решение владельца).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID>, 'Kabinet - Amazon Ads Invoices', 26, '08:50 Kyiv daily',
        'Счета Amazon Ads и регуляторный сбор по всем профилям (Billing API); источник nb/ads_invoices_loader.py')
ON CONFLICT DO NOTHING;
SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Amazon Ads Invoices';
