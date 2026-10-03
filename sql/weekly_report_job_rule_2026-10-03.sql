-- Недельный отчёт в Telegram (Kabinet - Weekly Report, понедельник 14:00 Kyiv).
-- Метка в пульсе без правила — джоба, которую никто не проверяет; имя одно в трёх местах.
-- Интервал 8 суток: прогон раз в неделю плюс сутки запаса.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (219517488147334, 'Kabinet - Weekly Report', 192, 'понедельник 14:00 Kyiv', true,
        'Недельный отчёт в Telegram в формате отчёта Романа: план/факт месяца, неделя к неделе, реклама, конверсия')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
