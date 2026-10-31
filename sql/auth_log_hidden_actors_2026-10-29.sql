-- Журнал действий экрана «Доступ»: записи разработки — служебные (29.10.2026, решение владельца: «шум Claude не нужен…
-- разработчик я… надо и меня убрать»). Применяет владелец или агент по прямому «применяй», ПОД УЧЁТКОЙ ВЛАДЕЛЬЦА, в
-- Lakebase Кабинета: psql "<строка владельца>" -v ON_ERROR_STOP=1 -f sql/auth_log_hidden_actors_2026-10-29.sql
-- Только добавляет. Почта разработчика в репозиторий не пишется: строку добавляет current_user — тот, кто применяет.
--
-- Экран (access_screen.py, общий с Listing Suite) прячет по умолчанию действия этих людей и правки агента напрямую в
-- базе (актор «claude-code по указанию …»); галочка «Показать служебные записи и записи разработки» возвращает всё.
-- Записи журнала не удаляются и не меняются: это аудит. Добавить или убрать разработчика — строкой здесь.
-- Гранты: приложению (тот же принципал у Кабинета и Listing Suite) и claude_code_ro — SELECT; джобы таблицу не читают —
-- отступление от правила «гранты обоим принципалам» названо здесь.

BEGIN;

-- под ролью, а не под человеком строка легла бы чужим именем и молча не скрыла бы ничего
DO $$
BEGIN
  IF position('@' IN current_user) = 0 THEN
    RAISE EXCEPTION 'применять под учёткой владельца (почтой), а не под ролью %', current_user;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS kabinet_data.auth_log_hidden_actors (
  email     text PRIMARY KEY,
  note      text,
  added_at  timestamptz NOT NULL DEFAULT now(),
  added_by  text NOT NULL DEFAULT current_user);
COMMENT ON TABLE kabinet_data.auth_log_hidden_actors IS
  'Разработчики: их действия в журнале действий экрана «Доступ» — служебные, по умолчанию скрыты (галочка возвращает).';

GRANT SELECT ON kabinet_data.auth_log_hidden_actors TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;

INSERT INTO kabinet_data.auth_log_hidden_actors (email, note)
VALUES (lower(current_user), 'разработчик Кабинета (решение владельца 29.10.2026)')
ON CONFLICT (email) DO NOTHING;

COMMIT;

-- Проверка чтением: SELECT email, note FROM kabinet_data.auth_log_hidden_actors;   -- одна строка — почта применившего
