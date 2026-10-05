-- Сверка → ClickUp (решение владельца 05.10.2026): тот же список, что у остальных алертов о качестве
-- данных Кабинета (job_health, stale_data, report_quota) — «3.8 Data Quality & Analytics», группа
-- «Kabinet · Данные». Уходит только НЕобъяснённое расхождение: объяснённое сторож не заводит вовсе.
UPDATE kabinet_data.incident_types
   SET clickup_list_id = 901222107497,
       clickup_list_name = '3. Demand & Supply / 3.8 Data Quality & Analytics / 3.8 Data Quality & Analytics',
       assignee_group_id = '5e544aa4-050d-46cf-bc28-f952cdb839aa',
       assignee_group_name = 'Kabinet · Данные',
       risk = 'High', due_days = 3, watch_close = true,
       enabled_since = DATE '2026-10-05',
       note = 'группа «Данные»; только необъяснённое расхождение сверки',
       updated_at = now(), updated_by = 'claude-code по указанию v.tereshyn'
 WHERE incident_type = 'reconciliation';
