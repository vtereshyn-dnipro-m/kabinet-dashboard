-- ТЗ 011: правило сторожа на ночной пересчёт и тип алерта на негодный вход расчёта.
-- Имя джобы, метка в system_pulse и job_name правила — одна строка символ в символ.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (80981047732046, 'Kabinet - Dependent Demand', 30, '08:05 Kyiv daily', true,
        'ТЗ 011: страховочный пересчёт зависимой потребности. Основной триггер — проведение документа на странице «Прогноз».')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
        schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;

-- Ошибка входа расчёта — качество данных, а не живость джобы: канал тот же, что у прочих инцидентов
-- (Кабинет → Telegram → ClickUp), отдельного не заводим. Список — «Demand Planning», как у прогнозных алертов.
INSERT INTO kabinet_data.incident_types (incident_type, mode, clickup_list_id, clickup_list_name, risk, due_days,
                                         enabled_since, title, description, watch_close, assignee_group_id, assignee_group_name, updated_by)
SELECT 'dependent_demand', 'task', t.clickup_list_id, t.clickup_list_name, 'High', 3, CURRENT_DATE,
       'Зависимая потребность не рассчитана',
       'ТЗ 011: у действующего прогноза набора не раскрылся состав — потребность базовых SKU неизвестна '
       'и в обеспечение не попадает. Исправляет DATA_OWNER: состав набора в справочнике SKU или сам прогноз.',
       true, t.assignee_group_id, t.assignee_group_name, 'kabinet'
FROM kabinet_data.incident_types t WHERE t.incident_type = 'missing_forecast'
ON CONFLICT (incident_type) DO NOTHING;
