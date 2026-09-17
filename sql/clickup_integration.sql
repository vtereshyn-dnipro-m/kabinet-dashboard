-- 17.09.2026: интеграция инцидентов Кабинета с ClickUp (workspace 90122017089).
-- Один инцидент — одна задача. Маршрутизация в таблице, не в коде; значения (исполнители,
-- списки) владелец согласует с Ярославом — до тех пор enabled = false у всех типов.

-- Ключ дедупликации. `incidents` принадлежит владельцу, колонку добавить от rw нельзя —
-- ключ выводится из полей детерминированно: у сторожа и listing_pairs первый токен в
-- квадратных скобках ([JOB:…], [PAIR:ASIN/mk], [kabinet_data.table]), у остальных sku:склад.
CREATE OR REPLACE FUNCTION kabinet_data.incident_dedup_key(
    incident_type text, sku text, warehouse_name text, message text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT incident_type || ':' || COALESCE(
        substring(message from '^\[([^\]]+)\]'),
        COALESCE(sku, '') || ':' || COALESCE(warehouse_name, ''))
$$;

-- Маршрутизация: тип инцидента → список ClickUp, исполнитель, поля.
-- mode: task — задача на инцидент; digest — одна задача на тип в день со списком внутри
-- (low_stock: 77 задач никому не нужны — владелец, 17.09.2026).
CREATE TABLE IF NOT EXISTS kabinet_data.clickup_routing (
    incident_type    text PRIMARY KEY,
    enabled          boolean NOT NULL DEFAULT false,
    mode             text NOT NULL DEFAULT 'task' CHECK (mode IN ('task', 'digest')),
    list_id          bigint NOT NULL,
    list_name        text,
    assignee_user_id bigint,              -- пусто = без исполнителя, согласуется с Ярославом
    risk             text CHECK (risk IN ('Low', 'Medium', 'High', 'Critical')),
    due_days         int NOT NULL DEFAULT 3,
    enabled_since    date,                -- в ClickUp уходят инциденты, созданные с этой даты; висящие на момент включения не переносим
    area             text,                -- значение поля «Область», если заполнять
    note             text,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Связь инцидент ↔ задача. Открытая связь на ключ — одна (частичный уникальный индекс);
-- после окончательного закрытия повторное срабатывание даёт новую строку и новую задачу.
CREATE TABLE IF NOT EXISTS kabinet_data.clickup_tasks (
    id              serial PRIMARY KEY,
    dedup_key       text NOT NULL,
    incident_id     int NOT NULL,
    incident_type   text NOT NULL,
    task_id         text NOT NULL UNIQUE,
    task_url        text,
    list_id         bigint,
    opened_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz,          -- инцидент всё ещё открыт на этот прогон
    last_comment_at timestamptz,
    last_comment_hash text,               -- комментарий только если текст изменился
    human_closed_at timestamptz,          -- закрыл человек в ClickUp (done/cancelled)
    human_closed_by text,
    reopened_count  int NOT NULL DEFAULT 0,
    closed_at       timestamptz,          -- окончательно: инцидент resolved
    closed_by       text,                 -- kabinet | human:<user>
    close_reason    text
);
CREATE UNIQUE INDEX IF NOT EXISTS clickup_tasks_open_key
    ON kabinet_data.clickup_tasks (dedup_key) WHERE closed_at IS NULL;

-- Состояние опроса обратной связи: по списку — когда последний раз забирали изменения.
CREATE TABLE IF NOT EXISTS kabinet_data.clickup_sync_state (
    list_id        bigint PRIMARY KEY,
    last_polled_at timestamptz NOT NULL
);

-- Параметры интеграции — там же, где остальные пороги.
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
  ('clickup_reopen_days', '3',
   'задачу, закрытую руками в ClickUp, переоткрываем комментарием, если причина инцидента жива через N дней (владелец, 17.09.2026)', now()),
  ('clickup_comment_min_hours', '24',
   'повторный комментарий «всё ещё висит» в задачу не чаще раза в N часов и только если текст изменился', now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();

-- Черновик маршрутизации: списки из разведки 17.09.2026, всё выключено, исполнители пустые.
INSERT INTO kabinet_data.clickup_routing (incident_type, mode, list_id, list_name, risk, due_days, note) VALUES
  ('out_of_stock',               'task',   901222107434, '3.3 Replenishment',          'High',     3, 'группа «Снабжение»'),
  ('low_stock',                  'digest', 901222107434, '3.3 Replenishment',          'Medium',   5, 'группа «Снабжение», дайджест'),
  ('stale_data',                 'task',   901222107497, '3.8 Data Quality',           'High',     1, 'группа «Данные»'),
  ('job_health',                 'task',   901222107497, '3.8 Data Quality',           'Critical', 1, 'группа «Данные»'),
  ('listing_pair_unreachable',   'digest', 901222107497, '3.8 Data Quality',           'Low',      3, 'группа «Данные»: сбой сборщика, не товар'),
  ('listing_pair_blocked',       'task',   901222107924, '5.6 Listing Publication',    'High',     3, 'группа «Площадки»'),
  ('listing_pair_missing',       'task',   901222107924, '5.6 Listing Publication',    'Medium',   5, 'группа «Площадки»'),
  ('listing_suppressed',         'task',   901222107924, '5.6 Listing Publication',    'High',     3, 'группа «Площадки»'),
  ('manomano_health_degraded',   'task',   901222107986, '5.9 Marketplace Performance','High',     1, 'группа «Площадки»'),
  ('carrefour_health_degraded',  'task',   901222107986, '5.9 Marketplace Performance','High',     1, 'группа «Площадки»'),
  ('lm_order_not_accepted',      'task',   901222107945, '5.7 Marketplace Logistics',  'High',     1, 'группа «Площадки»: заказ ждёт подтверждения'),
  ('leroy_merlin_order_not_accepted','task',901222107945,'5.7 Marketplace Logistics',  'High',     1, 'старое имя типа, встречается в журнале'),
  ('carrefour_order_not_accepted','task',  901222107945, '5.7 Marketplace Logistics',  'High',     1, 'группа «Площадки»: заказ ждёт подтверждения')
ON CONFLICT (incident_type) DO NOTHING;

GRANT SELECT ON kabinet_data.clickup_routing, kabinet_data.clickup_tasks, kabinet_data.clickup_sync_state TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE ON kabinet_data.clickup_routing, kabinet_data.clickup_tasks, kabinet_data.clickup_sync_state TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.clickup_tasks_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Правило здоровья: джоба ходит раз в час, порог 3 ч.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (1088220719651633, 'Kabinet - ClickUp Sync', 3, 'hourly at :20 Kyiv', 'сбои по отдельным задачам роняют прогон после пульса — красный здесь значит «ClickUp не принял»')
ON CONFLICT DO NOTHING;
