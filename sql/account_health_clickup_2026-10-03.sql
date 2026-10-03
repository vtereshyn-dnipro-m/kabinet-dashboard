-- Account Health → ClickUp, только критичные и высокие (решение владельца 03.10.2026:
-- «нарушение здоровья аккаунта — задача, а не просто сообщение»).
--
-- Порог важности — свойство ТИПА алерта, а не код в ClickUp Sync: пусто = все важности,
-- как было у всех типов до сих пор; 'high' = high и critical. Порог действует только на
-- СОЗДАНИЕ задачи: если у открытого инцидента важность упала ниже порога, уже созданная
-- задача живёт дальше — проблема-то не ушла, закрывает её только закрытие инцидента.
ALTER TABLE kabinet_data.incident_types
    ADD COLUMN IF NOT EXISTS clickup_min_severity text
    CHECK (clickup_min_severity IN ('low', 'medium', 'high', 'critical'));
COMMENT ON COLUMN kabinet_data.incident_types.clickup_min_severity IS
    'Минимальная важность инцидента, с которой создаётся задача ClickUp; NULL — любая';

-- Тот же список и та же группа, что у здоровья ManoMano и Carrefour: «5.9 Marketplace Performance»,
-- «Kabinet · Площадки». enabled_since сегодня — тревоги Account Health появились только сегодня.
UPDATE kabinet_data.incident_types
   SET clickup_list_id = 901222107986,
       clickup_list_name = '5. Marketplace Operations / 5.9 Marketplace Performance / 5.9 Marketplace Performance',
       assignee_group_id = 'e22d4135-cd54-4077-a763-19c1c4767f50',
       assignee_group_name = 'Kabinet · Площадки',
       risk = 'High', due_days = 1, watch_close = true,
       clickup_min_severity = 'high',
       enabled_since = DATE '2026-10-03',
       note = 'группа «Площадки»; в ClickUp только high и critical, остальное — Telegram',
       updated_at = now(), updated_by = 'claude-code по указанию v.tereshyn'
 WHERE incident_type = 'account_health';
