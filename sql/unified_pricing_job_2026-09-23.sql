-- Правило сторожа для загрузчика таблицы Unified Pricing. Имя — символ в символ как в Databricks
-- и в метке system_pulse: расхождение даёт либо ложный алерт, либо джобу без присмотра.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (840251218452465, 'Kabinet - Unified Pricing Loader', 30, '16:00 Kyiv daily',
        'Блок Amazon ES листа Step 1 таблицы Unified Pricing; после реплики снимков витрины в 15:30')
ON CONFLICT DO NOTHING;
SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name LIKE '%Unified%';
