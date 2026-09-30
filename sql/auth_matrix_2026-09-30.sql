-- «Доступ»: матрица прав в таблице, срок доступа, порог простоя.
--
-- Матрица переезжает из кода в базу по общему правилу репозитория: правило, которое
-- меняют, живёт в БД, а не константой в коде, иначе его правят в одном месте, а
-- поведение остаётся из другого, и расхождение не видно ниоткуда.
--
-- Что НЕ переезжает: страновое ограничение действия (`_COUNTRY_SCOPED` в auth.py).
-- Это не право, а смысл действия — для каких действий «свои страны» вообще значат
-- что-то. Галочкой его переключать нечего: таблица отвечает «кому что можно», код —
-- «что это действие означает».

BEGIN;

-- ---------- кто что может ----------
CREATE TABLE IF NOT EXISTS kabinet_data.app_permissions (
    action     text        NOT NULL,
    role       text        NOT NULL
               CHECK (role IN ('viewer', 'country_manager', 'demand_planner', 'admin')),
    allowed    boolean     NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text,
    PRIMARY KEY (action, role)
);

COMMENT ON TABLE kabinet_data.app_permissions IS
    'Матрица прав: строка на пару «действие × роль». Пустая таблица = правила берутся из кода.';

-- Пара «админ × админка» существует и включена всегда: снять её значило бы закрыть
-- экран доступа самому себе, а открыть обратно было бы уже неоткуда — только прямым
-- запросом в базу. Держится триггером, а не уговором в интерфейсе: править таблицу
-- можно и мимо экрана.
CREATE OR REPLACE FUNCTION kabinet_data.app_permissions_keep_admin()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.action = 'admin' AND OLD.role = 'admin' THEN
            RAISE EXCEPTION 'Право «админ × админка» снять нельзя: иначе в «Доступ» не войдёт никто, и вернуть его можно будет только запросом в базу';
        END IF;
        RETURN OLD;
    END IF;
    IF NEW.action = 'admin' AND NEW.role = 'admin' AND NOT NEW.allowed THEN
        RAISE EXCEPTION 'Право «админ × админка» снять нельзя: иначе в «Доступ» не войдёт никто, и вернуть его можно будет только запросом в базу';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS app_permissions_keep_admin ON kabinet_data.app_permissions;
CREATE TRIGGER app_permissions_keep_admin
    BEFORE INSERT OR UPDATE OR DELETE ON kabinet_data.app_permissions
    FOR EACH ROW EXECUTE FUNCTION kabinet_data.app_permissions_keep_admin();

-- ---------- засев ровно тем, что сейчас в коде ----------
-- Значения те же, что в `_MATRIX`: включение таблицы не должно ничего поменять в
-- поведении. Проверяется после прогона тестом матрицы.
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by) VALUES
    ('forecast.edit',    'viewer',          false, 'seed:2026-09-30'),
    ('forecast.edit',    'country_manager', true,  'seed:2026-09-30'),
    ('forecast.edit',    'demand_planner',  true,  'seed:2026-09-30'),
    ('forecast.edit',    'admin',           true,  'seed:2026-09-30'),
    ('forecast.approve', 'viewer',          false, 'seed:2026-09-30'),
    ('forecast.approve', 'country_manager', true,  'seed:2026-09-30'),
    ('forecast.approve', 'demand_planner',  true,  'seed:2026-09-30'),
    ('forecast.approve', 'admin',           true,  'seed:2026-09-30'),
    ('forecast.upload',  'viewer',          false, 'seed:2026-09-30'),
    ('forecast.upload',  'country_manager', true,  'seed:2026-09-30'),
    ('forecast.upload',  'demand_planner',  true,  'seed:2026-09-30'),
    ('forecast.upload',  'admin',           true,  'seed:2026-09-30'),
    ('forecast.post',    'viewer',          false, 'seed:2026-09-30'),
    ('forecast.post',    'country_manager', false, 'seed:2026-09-30'),
    ('forecast.post',    'demand_planner',  true,  'seed:2026-09-30'),
    ('forecast.post',    'admin',           true,  'seed:2026-09-30'),
    ('forecast.replace', 'viewer',          false, 'seed:2026-09-30'),
    ('forecast.replace', 'country_manager', false, 'seed:2026-09-30'),
    ('forecast.replace', 'demand_planner',  true,  'seed:2026-09-30'),
    ('forecast.replace', 'admin',           true,  'seed:2026-09-30'),
    ('ads.act',          'viewer',          false, 'seed:2026-09-30'),
    ('ads.act',          'country_manager', false, 'seed:2026-09-30'),
    ('ads.act',          'demand_planner',  false, 'seed:2026-09-30'),
    ('ads.act',          'admin',           true,  'seed:2026-09-30'),
    ('dict.edit',        'viewer',          false, 'seed:2026-09-30'),
    ('dict.edit',        'country_manager', false, 'seed:2026-09-30'),
    ('dict.edit',        'demand_planner',  true,  'seed:2026-09-30'),
    ('dict.edit',        'admin',           true,  'seed:2026-09-30'),
    ('reorder.act',      'viewer',          false, 'seed:2026-09-30'),
    ('reorder.act',      'country_manager', false, 'seed:2026-09-30'),
    ('reorder.act',      'demand_planner',  true,  'seed:2026-09-30'),
    ('reorder.act',      'admin',           true,  'seed:2026-09-30'),
    ('incident.act',     'viewer',          false, 'seed:2026-09-30'),
    ('incident.act',     'country_manager', true,  'seed:2026-09-30'),
    ('incident.act',     'demand_planner',  true,  'seed:2026-09-30'),
    ('incident.act',     'admin',           true,  'seed:2026-09-30'),
    ('admin',            'viewer',          false, 'seed:2026-09-30'),
    ('admin',            'country_manager', false, 'seed:2026-09-30'),
    ('admin',            'demand_planner',  false, 'seed:2026-09-30'),
    ('admin',            'admin',           true,  'seed:2026-09-30')
ON CONFLICT (action, role) DO NOTHING;

-- ---------- доступ до даты ----------
-- Дата включительно: «до 31.10» значит, что 31-го человек ещё работает, а 1-го уже нет.
-- Закрытие считается, а не записывается: срок виден в карточке и снимается возвратом
-- даты, а не «переоткрытием» записи, которую кто-то молча выключил.
ALTER TABLE kabinet_data.app_users ADD COLUMN IF NOT EXISTS access_until date;

COMMENT ON COLUMN kabinet_data.app_users.access_until IS
    'Последний день доступа включительно. NULL — без срока.';

-- ---------- порог простоя ----------
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('auth_idle_days', 30, 'Сколько дней без входа, чтобы человек попал в список «давно не заходил»')
ON CONFLICT (key) DO NOTHING;

-- ---------- гранты ----------
GRANT SELECT, INSERT, UPDATE ON kabinet_data.app_permissions TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT                 ON kabinet_data.app_permissions TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

-- Проверка глазами: матрица должна совпасть с тем, что было в коде.
SELECT action,
       bool_or(allowed) FILTER (WHERE role = 'viewer')          AS просмотр,
       bool_or(allowed) FILTER (WHERE role = 'country_manager') AS страновой,
       bool_or(allowed) FILTER (WHERE role = 'demand_planner')  AS планировщик,
       bool_or(allowed) FILTER (WHERE role = 'admin')           AS админ
  FROM kabinet_data.app_permissions GROUP BY action ORDER BY action;
