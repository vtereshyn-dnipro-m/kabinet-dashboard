-- 17.09.2026, уточнение клиента: справочник типов алертов с полем «список ClickUp».
-- Список есть — задачи уходят; списка нет — тип живёт только в Кабинете. Никаких
-- отдельных флагов «включено»: одно поле, одно правило. Исполнители — роли ClickUp
-- (user group), а не люди; пока пусто. Флаг watch_close: контролируем ли закрытие
-- (закрываем задачу сами, переоткрываем, если закрыли руками при живой причине) или
-- отдали в ClickUp и дальше не следим. Экран — «Справочники → Алерты».
-- Таблица создана как clickup_routing (17.09 утром) — переименована, а не пересоздана,
-- чтобы не потерять черновики маршрутов и гранты.

ALTER TABLE kabinet_data.clickup_routing RENAME TO incident_types;
ALTER TABLE kabinet_data.incident_types RENAME COLUMN list_id TO clickup_list_id;
ALTER TABLE kabinet_data.incident_types RENAME COLUMN list_name TO clickup_list_name;
ALTER TABLE kabinet_data.incident_types ALTER COLUMN clickup_list_id DROP NOT NULL;
ALTER TABLE kabinet_data.incident_types
    ADD COLUMN IF NOT EXISTS title               text,
    ADD COLUMN IF NOT EXISTS description         text,
    ADD COLUMN IF NOT EXISTS watch_close         boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS assignee_group_id   text,     -- id роли (user group) в ClickUp; заведёт Владислав
    ADD COLUMN IF NOT EXISTS assignee_group_name text,
    ADD COLUMN IF NOT EXISTS last_check_at       timestamptz,  -- джоба синка: когда и что нашла по списку
    ADD COLUMN IF NOT EXISTS last_check_note     text,
    ADD COLUMN IF NOT EXISTS updated_by          text;

-- Черновые списки у выключенных типов — в примечание, а поле списка пустое:
-- иначе после снятия флага enabled все тринадцать типов включились бы разом.
UPDATE kabinet_data.incident_types
   SET note = COALESCE(note || '; ', '') || 'предложен список: ' || clickup_list_name || ' (' || clickup_list_id || ')',
       clickup_list_id = NULL, clickup_list_name = NULL
 WHERE NOT enabled;
ALTER TABLE kabinet_data.incident_types DROP COLUMN enabled;
ALTER TABLE kabinet_data.incident_types DROP COLUMN assignee_user_id;

-- Названия и смысл типов — чтобы экран читался без кода.
UPDATE kabinet_data.incident_types t SET title = v.title, description = v.descr
FROM (VALUES
  ('out_of_stock',                'Нет остатка на канале',        'Остаток 0 на складе канала (FBA-пул или ManoMano) у SKU, который продавался за окно или лежит в FBA. Закрывается сам, когда остаток вернулся.'),
  ('low_stock',                   'Мало остатка',                 'Остаток 1..N на складе канала у наблюдаемого SKU. Порог — reorder_params.low_stock_threshold.'),
  ('stale_data',                  'Данные устарели',              'Таблица не обновлялась дольше порога из data_freshness_rules. Сторож пересчитывает ежедневно.'),
  ('job_health',                  'Джоба не отработала',          'Джоба Databricks без успешного прогона дольше порога из job_health_rules.'),
  ('listing_pair_blocked',        'Листинг заблокирован',         'Ни одного активного оффера по ASIN на рынке при FBM-остатке на складе.'),
  ('listing_pair_missing',        'ASIN не найден',               'Карточка на рынке не существует (404 несколько попыток подряд).'),
  ('listing_pair_unreachable',    'Снимок не собран',             'Сборщик витрины не смог снять карточку — сбой сборщика, не товар.'),
  ('listing_suppressed',          'Листинг подавлен Amazon',      'Amazon скрыл листинг (коды из Listing Issues), сток заморожен.'),
  ('manomano_health_degraded',    'ManoMano: приёмка заказов',    'Доля принятых заказов ниже порога.'),
  ('carrefour_health_degraded',   'Carrefour: приёмка заказов',   'Доля принятых заказов ниже порога.'),
  ('lm_order_not_accepted',       'LM: заказ ждёт подтверждения', 'Заказ Leroy Merlin в WAITING_ACCEPTANCE дольше порога.'),
  ('leroy_merlin_order_not_accepted','LM: заказ ждёт подтверждения (старое имя)', 'Старое имя того же типа, встречается в журнале до 09.2026.'),
  ('carrefour_order_not_accepted','Carrefour: заказ ждёт подтверждения', 'Заказ Carrefour в WAITING_ACCEPTANCE дольше порога.')
) AS v(itype, title, descr) WHERE t.incident_type = v.itype;

-- Типы, встречающиеся в журнале, но без строки в справочнике — заводим пустыми (список NULL).
INSERT INTO kabinet_data.incident_types (incident_type)
SELECT DISTINCT incident_type FROM kabinet_data.incidents
ON CONFLICT (incident_type) DO NOTHING;

-- Связи: идентификатор алерта пишется в поле задачи; отмечаем, у каких уже записан.
ALTER TABLE kabinet_data.clickup_tasks ADD COLUMN IF NOT EXISTS alert_field_set boolean NOT NULL DEFAULT false;

-- Права: экран правит справочник под принципалом приложения, джоба пишет last_check.
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.incident_types TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.clickup_tasks TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.incident_types TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.incident_types TO claude_code_ro;

SELECT incident_type, title, clickup_list_id, mode, watch_close, risk, due_days, enabled_since FROM kabinet_data.incident_types ORDER BY clickup_list_id NULLS LAST, incident_type;
