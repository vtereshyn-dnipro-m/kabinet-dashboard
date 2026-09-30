-- Вход через Google и роли (ТЗ 010). Выполняет роль Кабинета: таблицы наши.
--
-- Гранты стоят В ЭТОМ ЖЕ файле, а не «потом отдельно»: таблицу создаёт claude_code_rw,
-- а ходят в неё принципал приложения (583bf6d1-…) и принципал джоб (b1698364-…), и
-- первый же прогон без грантов падает на «permission denied» — так было с buybox_status.
--
-- Почему это наши таблицы, а не колонки в чужих: справочника людей в базе не было вовсе,
-- заводим с нуля. Внешнего ключа на `countries` нет намеренно — она принадлежит владельцу,
-- и REFERENCES на неё роли Кабинета не выдан (выдан только на marketplaces_new, warehouses,
-- pools). Код страны сверяется кодом, а не ключом.

BEGIN;

-- ---------- кто имеет доступ ----------
CREATE TABLE IF NOT EXISTS kabinet_data.app_users (
    email          text PRIMARY KEY,
    role           text        NOT NULL DEFAULT 'viewer'
                   CHECK (role IN ('viewer', 'country_manager', 'demand_planner', 'admin')),
    is_active      boolean     NOT NULL DEFAULT true,
    note           text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    created_by     text,
    first_login_at timestamptz,
    last_login_at  timestamptz,
    -- почта хранится в нижнем регистре: Google отдаёт её как заведена у человека, а
    -- сравнение по-разному написанных адресов молча пустило бы двойника
    CONSTRAINT app_users_email_lower CHECK (email = lower(email))
);

COMMENT ON TABLE kabinet_data.app_users IS
    'Люди с доступом в Кабинет. Строка здесь при неактивном домене = исключение из правила домена.';

-- ---------- страны странового менеджера ----------
-- Отдельная таблица, а не колонка: стран у человека N. Код — alpha2, тот же, что в
-- marketplaces_new.country_alpha2, чтобы сравнение шло без второго написания правила.
CREATE TABLE IF NOT EXISTS kabinet_data.app_user_countries (
    email   text NOT NULL REFERENCES kabinet_data.app_users(email) ON DELETE CASCADE,
    country text NOT NULL CHECK (country = upper(country) AND length(country) = 2),
    PRIMARY KEY (email, country)
);

-- ---------- журнал входов ----------
-- Отказ пишется наравне с успехом: «чужой домен постучался» — это событие, а пустой
-- журнал отказов читался бы как «никто не пытался».
CREATE TABLE IF NOT EXISTS kabinet_data.app_login_log (
    id     bigserial   PRIMARY KEY,
    ts     timestamptz NOT NULL DEFAULT now(),
    email  text,
    result text        NOT NULL
           CHECK (result IN ('ok', 'first_login', 'denied_domain', 'denied_disabled', 'logout')),
    reason text
);
CREATE INDEX IF NOT EXISTS app_login_log_ts_idx ON kabinet_data.app_login_log (ts DESC);

-- ---------- журнал действий ----------
-- Пишем и РАЗРЕШЁННЫЕ, и отклонённые: попытка сделать то, на что нет права, — это ровно
-- то, ради чего проверка стоит в обработчике, а не только на кнопке, и след от неё нужен.
-- У действий, где свой журнал уже есть (forecast_change_log, ads_actions,
-- assortment_change_log), дублей тут не заводим — там теперь стоит реальная почта.
CREATE TABLE IF NOT EXISTS kabinet_data.app_action_log (
    id          bigserial   PRIMARY KEY,
    ts          timestamptz NOT NULL DEFAULT now(),
    email       text,
    role        text,
    action      text        NOT NULL,
    object_type text,
    object_id   text,
    allowed     boolean     NOT NULL,
    details     text
);
CREATE INDEX IF NOT EXISTS app_action_log_ts_idx    ON kabinet_data.app_action_log (ts DESC);
CREATE INDEX IF NOT EXISTS app_action_log_email_idx ON kabinet_data.app_action_log (email, ts DESC);

-- ---------- админы ----------
-- Пятеро по решению владельца 30.09.2026. Артём — и администратор, и единственное пока
-- исключение из правила домена: почта вне @dniprom.com, поэтому строка тут ему и пропуск.
INSERT INTO kabinet_data.app_users (email, role, note, created_by) VALUES
    ('v.tereshyn@dniprom.com',      'admin', 'владелец', 'seed:auth-2026-09-30'),
    ('y.stepchenkov@dniprom.com',   'admin', NULL,       'seed:auth-2026-09-30'),
    ('r.herasymchuk@dniprom.com',   'admin', NULL,       'seed:auth-2026-09-30'),
    ('darina.korotkova@dniprom.com','admin', NULL,       'seed:auth-2026-09-30'),
    ('artem.kolesnik1@gmail.com',   'admin', 'исключение вне домена', 'seed:auth-2026-09-30')
ON CONFLICT (email) DO NOTHING;

-- ---------- режим входа ----------
-- Три значения, и среднее нужно именно для раскатки (поправка владельца 30.09.2026):
--   2 — как сейчас: входа нет, кнопки у всех. Иначе в момент деплоя кнопки пропали бы
--       у всех ещё до того, как вход вообще включили;
--   1 — вход обязателен, роли работают;
--   0 — авария: входа нет, у всех «Просмотр», кнопок нет. Сюда переводят, если ляжет
--       Google OAuth, — людей это не останавливает, но и лишнего сделать не даёт.
-- Раскатываемся на 2, проверяем, переводим на 1.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('auth_enabled', 2,
     'Режим входа: 2 раскатка (без входа, кнопки есть), 1 вход обязателен, 0 авария (у всех Просмотр)')
ON CONFLICT (key) DO NOTHING;

-- ---------- гранты ----------
-- Приложение: читает всех, заводит новичка, правит роли и страны из админки, пишет журналы.
GRANT SELECT, INSERT, UPDATE ON kabinet_data.app_users           TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, DELETE ON kabinet_data.app_user_countries  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT         ON kabinet_data.app_login_log       TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT         ON kabinet_data.app_action_log      TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.app_login_log_id_seq  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.app_action_log_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Джобы: сторожу надо знать админов (кому слать) и писать смену режима входа.
GRANT SELECT          ON kabinet_data.app_users      TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT  ON kabinet_data.app_action_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.app_action_log_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

-- Проверка глазами после прогона.
SELECT email, role, is_active, note FROM kabinet_data.app_users ORDER BY email;
SELECT key, value, note FROM kabinet_data.reorder_params WHERE key = 'auth_enabled';
SELECT has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'kabinet_data.app_users', 'SELECT') AS app_видит_людей,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb',
                           'kabinet_data.app_action_log', 'INSERT') AS app_пишет_журнал,
       has_table_privilege('b1698364-6ec5-4240-8cd6-e06dd6e60856',
                           'kabinet_data.app_users', 'SELECT') AS сторож_видит_людей;
