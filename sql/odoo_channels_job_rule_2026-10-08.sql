-- Живость джобы Kabinet - Odoo Channels Loader (job 89270271625477, 10:30 Kyiv): метка в пульсе без правила — джоба,
-- которую никто не проверяет. 30 ч = сутки плюс запас на один сдвиг прогона.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (89270271625477, 'Kabinet - Odoo Channels Loader', 30, '10:30 Kyiv daily', true,
        'Wallapop и сайт из Odoo: реплика raw_odoo_channel_sales и экономика WP_ES / WEB_ES')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
