-- Живость джобы снимка расписания (Kabinet - Job Schedule Snapshot, 123340359216077, ежечасно в :10 Kyiv).
-- Метка в system_pulse без правила — джоба, которую никто не проверяет (AGENTS.md, «Одно имя джоба в трёх местах»).
-- 3 ч: два пропущенных прогона подряд. Сторож по снимку старше 3 ч порядок не судит — эта же граница.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (123340359216077, 'Kabinet - Job Schedule Snapshot', 3, 'ежечасно в :10 Kyiv', true,
        'Расписание джоб, зависимости и изменения → вкладка «Расписание» в паспорте данных и тревога schedule_order')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
