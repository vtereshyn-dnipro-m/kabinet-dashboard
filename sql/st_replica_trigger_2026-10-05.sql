-- Sales & Traffic: джоба Дарины с 06.10.2026 стартует в 07:00 Kyiv (было 08:00, согласовано с ней),
-- наша реплика запускается по изменению её таблиц (table update trigger, 20 минут тишины после
-- последней записи), запасной запуск — отдельная джоба в 11:00, которая запускает основную с
-- mode=fallback и ничего не копирует, если основная уже забрала всё записанное.
-- Одна джоба — одна метка и одно правило: у запасной своя метка «(запасной)».
UPDATE kabinet_data.job_health_rules
   SET schedule_description = 'по изменению таблиц Дарины (её джоба с 07:00 Kyiv); запасной 11:00',
       note = 'Реплика Sales & Traffic из сырья Дарины; запуск триггером по таблицам, не по часам'
 WHERE job_id = 32157082853424;
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (628912100968280, 'Kabinet - Sales & Traffic Replica (запасной)', 26, '11:00 Kyiv', true,
        'Запускает основную реплику с mode=fallback; пропускает, если основная уже скопировала всё')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
