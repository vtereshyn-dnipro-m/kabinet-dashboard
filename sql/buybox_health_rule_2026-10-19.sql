-- Правило здоровья для Kabinet - Buy Box (19.10.2026). Джоба пишет метку system_pulse каждый день (14:00 Kyiv), а
-- правила не было — «метка без правила»: умерла бы молча. Найдено при разборе 429: 29.09 Buy Box упал на 32 батчах
-- Product Pricing 429, и сторож его не видел. С правилом новый блок «Квота Amazon» в стороже видит и его упавшие прогоны.
-- Применять ПОСЛЕ мержа, вместе с патчем сторожа.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, created_at, note)
VALUES (1086620628061334, 'Kabinet - Buy Box', 30, 'ежедневно 14:00 Kyiv', true, now(),
        'Buy Box из SP-API Product Pricing (getItemOffersBatch). Квота Product Pricing своя, не createReport.')
ON CONFLICT DO NOTHING;
