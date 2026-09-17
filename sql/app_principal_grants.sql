-- 17.09.2026: приложение (Streamlit Cloud) ходит в Lakebase под принципалом
-- 583bf6d1-6cd0-4a89-9c44-b387ec5c21cb, а таблицы, созданные claude_code_rw, для него
-- закрыты по умолчанию — «План месяца» на Обзоре показывал «плана нет» при загруженном
-- реестре. Выдаём SELECT на всё, чем владеет rw, и default privileges на будущее.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'kabinet_data' AND c.relkind IN ('r', 'v', 'p')
             AND pg_get_userbyid(c.relowner) IN ('claude_code_rw', 'claude_code_ro')
  LOOP
    EXECUTE format('GRANT SELECT ON kabinet_data.%I TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb"', r.relname);
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES FOR ROLE claude_code_rw IN SCHEMA kabinet_data
    GRANT SELECT ON TABLES TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
SELECT t, has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.'||t, 'SELECT') AS app_can_select
FROM unnest(ARRAY['v_forecast_current','forecast_register','reorder_params','forecast_alert_rules','clickup_tasks']) t;
