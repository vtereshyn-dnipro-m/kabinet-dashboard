-- Сервисный принципал джоб kabinet-jobs-sp (вариант В): SQL «только добавить», МИНИМАЛЬНЫЕ права — только то, что нужно
-- загрузчикам TikTok (решение владельца 26.10.2026, вариант а). Ничего не забирает — claude-uc-ro и account users
-- работают как прежде. Применяет ВЛАДЕЛЕЦ (или агент по «применяй» под его учёткой), после создания принципала.
--
-- Было (22–25.10.2026): копия всех прав claude-uc-ro — 223 объекта, запись на 66, включая INSERT на app_action_log
-- (журнал системы входа). Владелец это отклонил: принципал получает только нужное; запись для первых пяти джоб из
-- docs/kabinet-jobs-sp.md придёт отдельным SQL при их переводе. Лишние права самого claude-uc-ro — TASKS.md (T-31).
--
-- Запуск — psql под владельцем базы, одной транзакцией:
--   psql "<строка подключения владельца>" -v sp=<APPLICATION_ID> -v ON_ERROR_STOP=1 -1 -f sql/kabinet_jobs_sp_2026-10-22.sql
-- Файл sql/kabinet_jobs_sp_2026-10-22_ro.sql (последовательности и права по умолчанию за claude_code_rw) сейчас НЕ
-- применяется: у таблиц TikTok последовательностей нет, а писать через claude_code_ro владелец запретил.
--
-- Таблицы — из кода загрузчиков (nb/tiktok_loader.py, nb/tiktok_analytics_loader.py), сверено 26.10.2026:
--   reorder_params             SELECT                  — настройки tiktok_* (оба загрузчика);
--   system_pulse               SELECT, INSERT, UPDATE  — пульс, INSERT … ON CONFLICT DO UPDATE (оба);
--   raw_tiktok_orders,
--   raw_tiktok_order_lines,
--   raw_tiktok_finance_tx      SELECT, INSERT, UPDATE  — реплика, INSERT … ON CONFLICT DO UPDATE (загрузчик заказов).
-- DELETE не нужен нигде. Последовательностей у этих таблиц нет. Остальное (сырьё, sync_state) — в Unity Catalog,
-- dnipro_m.tiktok — не здесь. SELECT нужен для ON CONFLICT DO UPDATE (чтение конфликтующей строки и EXCLUDED).
-- reorder_params принадлежит claude_code_ro; владелец выдаёт SELECT на неё через databricks_superuser (у той SELECT с
-- правом передачи, владелец состоит в ней с INHERIT) — грантующим запишется databricks_superuser.

-- ── Часть A. Lakebase Кабинета ──
-- A1. Роль принципала — функцией Databricks (public.databricks_create_role(text, text), есть в базе). Если роль уже
--     заведена в интерфейсе Lakebase — эту строку пропустить. Если функция откажет внутри транзакции (-1) — завести роль
--     в интерфейсе Lakebase (Roles → Add → сервисный принципал), строку закомментировать и запустить файл заново.
SELECT databricks_create_role(:'sp', 'SERVICE_PRINCIPAL');
-- A2. Схема — только USAGE.
GRANT USAGE ON SCHEMA kabinet_data TO :"sp";
-- A3. Таблицы загрузчиков TikTok — только они.
GRANT SELECT ON TABLE kabinet_data.reorder_params TO :"sp";
GRANT SELECT, INSERT, UPDATE ON TABLE kabinet_data.system_pulse TO :"sp";
GRANT SELECT, INSERT, UPDATE ON TABLE kabinet_data.raw_tiktok_orders TO :"sp";
GRANT SELECT, INSERT, UPDATE ON TABLE kabinet_data.raw_tiktok_order_lines TO :"sp";
GRANT SELECT, INSERT, UPDATE ON TABLE kabinet_data.raw_tiktok_finance_tx TO :"sp";
-- A4. Последовательности — нет (у таблиц из A3 их нет).
-- A5. Права по умолчанию на НОВЫЕ таблицы, которые создаёт сам владелец: только SELECT.
ALTER DEFAULT PRIVILEGES FOR ROLE "v.tereshyn@dniprom.com" IN SCHEMA kabinet_data GRANT SELECT ON TABLES TO :"sp";

-- Проверка чтением (после применения; любым подключением). Ожидается 5 строк:
--   reorder_params — SELECT; system_pulse, raw_tiktok_* — INSERT, SELECT, UPDATE; и ни одной строки по app_* .
-- SELECT c.relname, string_agg(DISTINCT a.privilege_type, ', ' ORDER BY a.privilege_type)
--   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, aclexplode(c.relacl) a
--  WHERE n.nspname = 'kabinet_data' AND a.grantee = '<APPLICATION_ID>'::regrole GROUP BY 1 ORDER BY 1;
-- SELECT pg_get_userbyid(d.defaclrole), a.privilege_type FROM pg_default_acl d, aclexplode(d.defaclacl) a
--  WHERE a.grantee = '<APPLICATION_ID>'::regrole;                                                        -- 1 строка: SELECT

-- ── Часть B. Unity Catalog (SQL-склад, Spark SQL; под владельцем каталога — группа администраторов воркспейса) ──
-- B1. Чтение. Явных грантов у claude-uc-ro в UC мало (USE CATALOG и USE SCHEMA + SELECT на kabinet_data), остальное он
--     получает через account users. Новому — явно на все четыре схемы: когда account users станет «только чтение»,
--     у него не пропадёт ничего. Сейчас (account users — ALL PRIVILEGES и MANAGE на каталог) «только чтение» у нового
--     принципала по факту ещё не действует — это шаг после перевода всех джоб.
-- В Spark SQL подстановки нет — `<sp>` заменить application id руками (в обратных кавычках).
-- GRANT USE CATALOG ON CATALOG dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.kabinet_data TO `<sp>`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA dnipro_m.listing_data TO `<sp>`;
-- B2. Запись — НЕ на этом шаге: первые пять джоб в Unity Catalog не пишут. Для девяти пишущих — вторым PR:
-- GRANT CREATE TABLE, MODIFY ON SCHEMA dnipro_m.dnipro_m TO `<sp>`;   -- и передача владения их 14 таблицами
