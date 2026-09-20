-- 20.09.2026. Экран документа прогноза (ТЗ 010): приложение пишет в реестр от своего принципала.
-- Документ в Кабинете — источник истины (Ярослав, 20.09.2026); загрузчик листа с этого дня создаёт
-- черновики, а не проведённые документы — утверждает и проводит человек.
GRANT SELECT, INSERT, UPDATE ON kabinet_data.forecast_documents, kabinet_data.forecast_register, kabinet_data.forecast_change_log
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_documents_id_seq, kabinet_data.forecast_register_id_seq, kabinet_data.forecast_change_log_id_seq
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
-- журнал: snapshot состояния значения на момент действия — утверждение/снятие/проведение пишутся туда же (field = approval / post)
SELECT has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.forecast_register', 'INSERT') AS ins_app,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.forecast_documents', 'UPDATE') AS upd_doc_app;
