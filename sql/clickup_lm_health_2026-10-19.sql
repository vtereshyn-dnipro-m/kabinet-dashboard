-- Тревога «Leroy Merlin: приёмка заказов» (leroy_merlin_health_degraded) — в ClickUp, как у ManoMano и Carrefour
-- (решение владельца 19.10.2026). Тип появился в журнале 19.10.2026 (проверка здоровья Mirakl); строку справочника
-- ClickUp Sync завёл сам пустой — без списка задачи не создаются. Настройка — копия manomano_health_degraded /
-- carrefour_health_degraded: список «5.9 Marketplace Performance», группа «Kabinet · Площадки», High, срок 1 день,
-- закрытие отслеживается. enabled_since — сегодня: открытая сегодня тревога тоже получит задачу.
-- Применять ПОСЛЕ мержа. Задача появится на ближайшем прогоне Kabinet - ClickUp Sync (раз в час, :20).
UPDATE kabinet_data.incident_types t SET
    mode                = 'task',
    clickup_list_id     = s.clickup_list_id,
    clickup_list_name   = s.clickup_list_name,
    risk                = s.risk,
    due_days            = s.due_days,
    watch_close         = s.watch_close,
    assignee_group_id   = s.assignee_group_id,
    assignee_group_name = s.assignee_group_name,
    enabled_since       = DATE '2026-10-19',
    title               = 'Leroy Merlin: приёмка заказов',
    description         = 'Доля принятых заказов ниже порога.',
    note                = 'группа «Площадки»; как manomano_health_degraded и carrefour_health_degraded (19.10.2026)',
    updated_by          = 'kabinet',
    updated_at          = now()
FROM kabinet_data.incident_types s
WHERE t.incident_type = 'leroy_merlin_health_degraded'
  AND s.incident_type = 'manomano_health_degraded';

-- проверка: строка одна и совпадает с образцом по маршруту
SELECT incident_type, mode, clickup_list_id, risk, due_days, watch_close, assignee_group_name, enabled_since
FROM kabinet_data.incident_types
WHERE incident_type IN ('leroy_merlin_health_degraded', 'manomano_health_degraded', 'carrefour_health_degraded');
