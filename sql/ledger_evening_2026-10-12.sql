-- Страховка вечерней цепочки после Ledger Summary (12.10.2026). Применять после мержа, после создания джоб
-- (job_id запасной джобы вписать вместо :fallback_job_id — его выдаст `databricks jobs create`).

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('ledger_evening', 'task', 'High', 'Вечерние остатки FBA не обновились',
        'До 18:30 не пришла вечерняя запись Ledger Summary (или цепочка после неё не отработала): остатки FBA и покрытие '
        'посчитаны на вчерашних данных. Запасной прогон Stock Loader и Coverage запущен на том, что есть.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:fallback_job_id, 'Kabinet - Запасной прогон после Ledger Summary', 30, 'ежедневно 18:30 Kyiv', true,
        'Страховка вечерней цепочки: нет вечерней записи Ledger Summary — запасной Stock Loader и Coverage, тревога ledger_evening')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
