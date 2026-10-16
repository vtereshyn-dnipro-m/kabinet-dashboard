-- Правило сторожа для «Kabinet - Alert Close on Write». Выполнять ПОСЛЕ создания джобы
-- (nb/jobs/alert_close_2026-10-16/create_alert_close.json): вместо <JOB_ID> — id из `databricks jobs create`.
-- 26 ч: джоба запускается по записи в Ledger Summary, а он пишет дважды в день (10:20 и 16:20).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID>, 'Kabinet - Alert Close on Write', 26, 'по записи в таблицы source_job_checks',
        'Закрывает тревоги «таблица не обновилась» по записи в таблицу; источник nb/alert_close_on_write.py')
ON CONFLICT DO NOTHING;
SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Alert Close on Write';
