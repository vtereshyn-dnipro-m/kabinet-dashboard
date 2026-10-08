-- Живость джобы Kabinet - Power BI Replica (job 813933040777378, 12:45 и 16:45 Kyiv): метка в пульсе без правила —
-- джоба, которую никто не проверяет. 26 ч = сутки плюс запас; дневной прогон пропасть может, но не оба подряд.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (813933040777378, 'Kabinet - Power BI Replica', 26, '12:45 и 16:45 Kyiv daily', true,
        'Реплика витрины Power BI в kabinet_data.pbi_spiderweb_report: из неё Кабинет показывает те же цифры, что Power BI')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
