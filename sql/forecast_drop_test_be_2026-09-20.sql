-- 20.09.2026. Тестовый документ FC-20260920-AMZ-BE (QA страницы «Прогноз» через браузер) проведён и дал
-- «план по Бельгии из ниоткуда»: 132 действующие записи, ни одну прежнюю не заменял (replaces пусты).
-- Убираем целиком по решению владельца — это не история прогноза, а артефакт проверки.
DELETE FROM kabinet_data.forecast_change_log WHERE document_id IN (SELECT id FROM kabinet_data.forecast_documents WHERE number = 'FC-20260920-AMZ-BE');
DELETE FROM kabinet_data.forecast_register WHERE document_id IN (SELECT id FROM kabinet_data.forecast_documents WHERE number = 'FC-20260920-AMZ-BE')
  AND cardinality(replaces) = 0;
DELETE FROM kabinet_data.forecast_documents WHERE number = 'FC-20260920-AMZ-BE'
  AND NOT EXISTS (SELECT 1 FROM kabinet_data.forecast_register r WHERE r.document_id = forecast_documents.id);
SELECT count(*) AS be_current FROM kabinet_data.v_forecast_current WHERE object_type = 'marketplace' AND object_id = 6;
