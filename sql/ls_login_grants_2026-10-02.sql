-- Гранты в базе Кабинета принципалу, под которым работает Listing Suite. 02.10.2026.
--
-- ВЫПОЛНЯТЬ НЕ НУЖНО — и это главное, что здесь написано. Listing Suite ходит в
-- Lakebase под ТЕМ ЖЕ сервис-принципалом, что и Кабинет:
-- `583bf6d1-6cd0-4a89-9c44-b387ec5c21cb` (kabinet-dashboard-sp) — так сказано в
-- `AGENTS.md` самого Listing Suite и так показывает список ролей в обеих базах.
-- Значит права у него уже есть, все до одного (проверка — запросом в конце файла).
--
-- Файл всё равно лежит в репозитории по двум причинам. Первая: когда Listing Suite
-- заведут собственного принципала (а это обычный шаг при разделении продуктов),
-- список нужных прав должен быть записан, а не выводиться заново по падениям
-- приложения. Вторая: новые таблицы наследуют default privileges, а СТАРЫЕ — нет,
-- и это уже стоило нам «плана нет» на Обзоре при загруженном реестре.
--
-- Запускать от роли, которая владеет таблицами (`claude_code_ro`), подставив
-- принципала в переменную ниже. Идемпотентно: повторный GRANT ничего не ломает.

\set ls_sp '583bf6d1-6cd0-4a89-9c44-b387ec5c21cb'

-- чтение: кто это, что ему можно, в каком режиме вход
GRANT SELECT ON kabinet_data.app_users          TO :"ls_sp";
GRANT SELECT ON kabinet_data.app_user_countries TO :"ls_sp";
GRANT SELECT ON kabinet_data.app_permissions    TO :"ls_sp";
GRANT SELECT ON kabinet_data.reorder_params     TO :"ls_sp";

-- запись: журналы входов и действий плюс отметка «первый вход» в карточке человека
GRANT INSERT         ON kabinet_data.app_login_log  TO :"ls_sp";
GRANT INSERT         ON kabinet_data.app_action_log TO :"ls_sp";
GRANT INSERT, UPDATE ON kabinet_data.app_users      TO :"ls_sp";

-- тестовый вход QA: приложение сверяет хеш и отмечает, что ссылкой пользовались
GRANT SELECT, UPDATE ON kabinet_data.qa_tokens TO :"ls_sp";

-- последовательности журналов: без них INSERT падает на nextval
GRANT USAGE ON SEQUENCE kabinet_data.app_login_log_id_seq  TO :"ls_sp";
GRANT USAGE ON SEQUENCE kabinet_data.app_action_log_id_seq TO :"ls_sp";

-- ── проверка: одна строка, где всё должно быть true ───────────────────────────
-- Прав не хватает — приложение скажет об этом словом и назовёт грант, а не упадёт
-- молча; но увидеть это лучше здесь.
SELECT has_table_privilege(:'ls_sp', 'kabinet_data.app_users', 'SELECT')          AS users_read,
       has_table_privilege(:'ls_sp', 'kabinet_data.app_users', 'UPDATE')          AS users_write,
       has_table_privilege(:'ls_sp', 'kabinet_data.app_permissions', 'SELECT')    AS perms_read,
       has_table_privilege(:'ls_sp', 'kabinet_data.reorder_params', 'SELECT')     AS params_read,
       has_table_privilege(:'ls_sp', 'kabinet_data.app_login_log', 'INSERT')      AS logins_write,
       has_table_privilege(:'ls_sp', 'kabinet_data.app_action_log', 'INSERT')     AS actions_write,
       has_table_privilege(:'ls_sp', 'kabinet_data.qa_tokens', 'UPDATE')          AS qa_write;
