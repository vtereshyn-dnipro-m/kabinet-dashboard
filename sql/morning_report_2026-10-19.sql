-- Утренняя сводка ночи в бот (19.10.2026, «закрываем тему квоты», пункт 2). Применять ПОСЛЕ мержа и ПОСЛЕ
-- sql/amazon_run_check_2026-10-19.sql (сводка читает kabinet_data.amazon_api_jobs и amazon_run_checks; своих таблиц нет).
-- :report_job_id — id джобы из `databricks jobs create` (nb/jobs/morning_report_2026-10-19).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:report_job_id, 'Kabinet - Morning Report', 26, 'ежедневно 08:00 Kyiv', true,
        'Утренняя сводка ночи в бот: джобы Amazon API, 429, открытые тревоги; не ушла — прогон красный')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
