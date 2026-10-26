-- НЕ ПРИМЕНЯТЬ (решение владельца 26.10.2026): писать через claude_code_ro нельзя, а загрузчикам TikTok этот файл не нужен.
-- Как выдать эти права при переводе первых пяти джоб без claude_code_ro — открытый вопрос (docs/kabinet-jobs-sp.md, шаг 2).
-- Сервисный принципал джоб kabinet-jobs-sp, часть A, второй файл (22.10.2026): то, что может выдать только claude_code_ro.
-- Запуск — ПОСЛЕ первого файла (sql/kabinet_jobs_sp_2026-10-22.sql: там создаётся роль), под подключением claude_code_ro:
--   psql "<строка подключения claude_code_ro>" -v sp=<APPLICATION_ID> -v ON_ERROR_STOP=1 -1 -f sql/kabinet_jobs_sp_2026-10-22_ro.sql
-- Почему не под владельцем базы: все 16 последовательностей принадлежат claude_code_ro, а владелец состоит в claude_code_ro и
-- claude_code_rw только с ADMIN (без INHERIT и SET) — его GRANT на них молча выдаст «no privileges were granted», а смена
-- прав по умолчанию за claude_code_rw упадёт. claude_code_ro состоит в claude_code_rw с INHERIT и SET — ему можно.
-- Только добавить: ничего не отзывается.

-- A4. Последовательности — ровно как у claude-uc-ro (16; UPDATE у него нет ни на одной).
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.app_action_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_admissions_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.assortment_representations_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.clickup_tasks_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_change_log_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_documents_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_register_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.morning_reports_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.pbi_replica_meta_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.plan_price_sheet_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.product_entities_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.product_entity_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.sku_change_log_id_seq TO :"sp";
GRANT USAGE ON SEQUENCE kabinet_data.variation_group_change_log_id_seq TO :"sp";
GRANT SELECT, USAGE ON SEQUENCE kabinet_data.variation_groups_id_seq TO :"sp";
-- A5 (вторая строка). Права по умолчанию на новые таблицы, которые создаёт claude_code_rw.
ALTER DEFAULT PRIVILEGES FOR ROLE claude_code_rw IN SCHEMA kabinet_data GRANT SELECT ON TABLES TO :"sp";

-- Проверка чтением (после обоих файлов; любым подключением). Ожидается: 239 строк — 223 таблицы и вью плюс 16
-- последовательностей — и пустой результат сравнения с claude-uc-ro; затем 2 строки прав по умолчанию.
-- SELECT c.relname, c.relkind, a.privilege_type FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace,
--        aclexplode(c.relacl) a WHERE n.nspname = 'kabinet_data' AND a.grantee = 'b1698364-6ec5-4240-8cd6-e06dd6e60856'::regrole
-- EXCEPT
-- SELECT c.relname, c.relkind, a.privilege_type FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace,
--        aclexplode(c.relacl) a WHERE n.nspname = 'kabinet_data' AND a.grantee = '<APPLICATION_ID>'::regrole;
-- SELECT count(DISTINCT c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, aclexplode(c.relacl) a
--  WHERE n.nspname = 'kabinet_data' AND a.grantee = '<APPLICATION_ID>'::regrole;                          -- 239
-- SELECT pg_get_userbyid(d.defaclrole), a.privilege_type FROM pg_default_acl d, aclexplode(d.defaclacl) a
--  WHERE a.grantee = '<APPLICATION_ID>'::regrole;                                                          -- 2 строки
