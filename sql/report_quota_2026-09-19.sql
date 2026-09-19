-- 19.09.2026: квота createReport — отдельный тип инцидента и разведённые расписания.
INSERT INTO kabinet_data.incident_types (incident_type, title, description, mode, risk, due_days, assignee_group_id, assignee_group_name, clickup_list_id, clickup_list_name, enabled_since)
VALUES ('report_quota', 'Квота отчётов SP-API', 'Загрузчик упал, потому что createReport отвечал 429 дольше 40 минут — общая квота аккаунта занята другими отчётами. Не поломка кода: сработает при следующем прогоне; если повторяется — двигать расписание.',
        'digest', 'Low', 2, '5e544aa4-050d-46cf-bc28-f952cdb839aa', 'Kabinet · Данные', 901222107497, '3. Demand & Supply / 3.8 Data Quality & Analytics / List', '2026-09-19')
ON CONFLICT (incident_type) DO UPDATE SET title = EXCLUDED.title, description = EXCLUDED.description;

UPDATE kabinet_data.job_health_rules SET schedule_description = '07:00 Kyiv daily' WHERE job_id = 565517931588672;
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:15 Kyiv daily' WHERE job_id = 85948015331467 AND job_name LIKE '%FBA Charges%';
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:15 Kyiv daily' WHERE job_name = 'Kabinet - FBA Charges Loader';
UPDATE kabinet_data.job_health_rules SET schedule_description = '11:00 Kyiv daily' WHERE job_id = 174154625041145;
UPDATE kabinet_data.job_health_rules SET schedule_description = '02:30, 06:30, 11:30, 15:30, 19:30, 23:30 Kyiv' WHERE job_id = 597550726435861;
SELECT job_name, schedule_description FROM kabinet_data.job_health_rules WHERE job_id IN (565517931588672, 174154625041145, 597550726435861) OR job_name = 'Kabinet - FBA Charges Loader';
