-- Резервный у рубильника входа: Дарина (просьба Ярослава, 30.09.2026).
--
-- ВЫПОЛНЯЕТ ВЛАДЕЛЕЦ (v.tereshyn@dniprom.com): завести роль в Postgres может только
-- тот, у кого есть право заводить роли. У `claude_code_rw` его нет — проверено,
-- `rolcreaterole = false`; у `v.tereshyn@dniprom.com` есть.
--
-- Прежде чем давать права, выяснилось главное: **роли Дарины в базе нет вовсе.** Она
-- никогда не подключалась к Lakebase напрямую — её джобы работают со Spark и Unity
-- Catalog. То есть вопрос «может ли она обновлять reorder_params» имеет ответ «не
-- может, и дело не в правах, а в том, что её в базе не существует».
--
-- И права даются НЕ на таблицу. В `reorder_params` лежат все пороги Кабинета — горизонт
-- автозаказа, пол ставки по рекламе, окна свежести, пороги сторожа. GRANT UPDATE ради
-- одного переключателя дал бы право менять их все, причём молча. Поэтому доступ —
-- ровно к двум функциям: посмотреть режим и переключить его. Функции уже заведены
-- (`sql/auth_switch_functions_2026-09-30.sql`), они SECURITY DEFINER и пишут в журнал,
-- КТО переключил.

BEGIN;

-- 1. роль. Форма скопирована с уже работающих ролей-личностей в этой базе: вход есть,
--    наследование есть, права заводить роли НЕТ, членства ни в чём — всё выдаётся явно.
CREATE ROLE "darina.korotkova@dniprom.com" WITH LOGIN INHERIT;

-- 2. добраться до схемы. CONNECT на базу у PUBLIC уже есть, а USAGE на схему — нет.
GRANT USAGE ON SCHEMA kabinet_data TO "darina.korotkova@dniprom.com";

-- 3. ровно две возможности и ничего больше
GRANT EXECUTE ON FUNCTION kabinet_data.get_auth_mode()      TO "darina.korotkova@dniprom.com";
GRANT EXECUTE ON FUNCTION kabinet_data.set_auth_mode(int)   TO "darina.korotkova@dniprom.com";

COMMIT;

-- Проверка глазами после прогона: прав на саму таблицу быть НЕ должно.
SELECT 'может смотреть режим'      AS что,
       has_function_privilege('darina.korotkova@dniprom.com',
                              'kabinet_data.get_auth_mode()', 'EXECUTE')::text AS ответ
UNION ALL
SELECT 'может переключать',
       has_function_privilege('darina.korotkova@dniprom.com',
                              'kabinet_data.set_auth_mode(int)', 'EXECUTE')::text
UNION ALL
SELECT 'МОЖЕТ ЛИ ПИСАТЬ В ПОРОГИ НАПРЯМУЮ (должно быть false)',
       has_table_privilege('darina.korotkova@dniprom.com',
                           'kabinet_data.reorder_params', 'UPDATE')::text
UNION ALL
SELECT 'может ли читать пороги напрямую (должно быть false)',
       has_table_privilege('darina.korotkova@dniprom.com',
                           'kabinet_data.reorder_params', 'SELECT')::text;
