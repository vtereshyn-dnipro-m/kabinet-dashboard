-- Роль записи для Claude Code. Lakebase, схема kabinet_data.
--
-- Единственный файл, который приходится запускать руками: CREATE ROLE
-- требует rolcreaterole, а у claude_code_ro его нет и быть не должно.
-- Всё остальное после этого выполняется само.
--
-- Пароля роль не заводит. claude_code_rw — NOLOGIN, то есть контейнер
-- прав, а не учётка; права достаются существующему claude_code_ro через
-- членство (у него rolinherit = true, SET ROLE не нужен). Одним паролем
-- в системе меньше, и отзывается всё одной строкой:
--     REVOKE claude_code_rw FROM claude_code_ro;
--
-- Запускать под v.tereshyn@dniprom.com — владельцем таблиц схемы.
-- В psql обязательно с -v ON_ERROR_STOP=1: иначе первая же ошибка
-- уводит транзакцию в abort, COMMIT молча превращается в ROLLBACK,
-- и прогон выглядит успешным. Ровно так потерялся прошлый запуск.

BEGIN;

CREATE ROLE claude_code_rw NOLOGIN;

COMMENT ON ROLE claude_code_rw IS
  'Запись для Claude Code. Заведена 10.09.2026, выдана claude_code_ro. '
  'Область: справочники складов и таблицы наблюдения. Заказы, экономика '
  'и остатки НЕ включены намеренно — их пишут загрузчики, и посторонняя '
  'запись туда не нужна. Отзыв: REVOKE claude_code_rw FROM claude_code_ro;';

GRANT claude_code_rw TO claude_code_ro;

-- Справочники: их ведут люди с экрана, правки бывают и со стороны
GRANT INSERT, UPDATE, DELETE ON
      kabinet_data.warehouses,
      kabinet_data.supply_chains
   TO claude_code_rw;

-- Наблюдение: пороги свежести, здоровье джобов, инциденты
GRANT INSERT, UPDATE, DELETE ON
      kabinet_data.data_freshness_rules,
      kabinet_data.job_health_rules,
      kabinet_data.incidents
   TO claude_code_rw;

-- Новые таблицы справочников и вьюхи контроля
GRANT CREATE ON SCHEMA kabinet_data TO claude_code_rw;

COMMIT;

-- ── Проверка: все пять должны стать true ────────────────────────────
SELECT has_schema_privilege('claude_code_ro','kabinet_data','CREATE')            AS sozdavat,
       has_table_privilege('claude_code_ro','kabinet_data.warehouses','UPDATE')  AS sklady,
       has_table_privilege('claude_code_ro','kabinet_data.supply_chains','UPDATE') AS podpitka,
       has_table_privilege('claude_code_ro','kabinet_data.job_health_rules','UPDATE') AS dzhoby,
       has_table_privilege('claude_code_ro','kabinet_data.incidents','UPDATE')   AS incidenty;
