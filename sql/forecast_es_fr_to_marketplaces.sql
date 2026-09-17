-- 18.09.2026, решение владельца: план Испании и Франции лежит на маркетплейсах AMZ-ES (id 1)
-- и AMZ-FR (id 3), а не на пулах Spain (6) и France (7). Лист — «Amazon Product Planning»,
-- это план по Amazon; пул по ТЗ 004 — сумма участников, своего плана у него нет.
-- Пуловые записи снимаются с действия (superseded), документы остаются в истории;
-- новые документы по AMZ-ES / AMZ-FR создаст загрузчик.
BEGIN;
UPDATE kabinet_data.forecast_register
   SET is_current = FALSE, status = 'superseded', superseded_at = now()
 WHERE record_type = 'sales' AND is_current AND object_type = 'pool' AND object_id IN (6, 7);
INSERT INTO kabinet_data.forecast_change_log (document_id, sku, month, field, old_value, new_value, source, actor)
SELECT r.document_id, r.sku, r.month, 'object', 'pool:' || r.object_id,
       CASE r.object_id WHEN 6 THEN 'marketplace:1' ELSE 'marketplace:3' END,
       'manual:owner-decision-2026-09-18', 'kabinet'
  FROM kabinet_data.forecast_register r
 WHERE r.record_type = 'sales' AND r.object_type = 'pool' AND r.object_id IN (6, 7)
   AND r.status = 'superseded' AND r.superseded_at >= now() - interval '1 minute';
UPDATE kabinet_data.forecast_documents
   SET comment = COALESCE(comment, '') || ' — 18.09.2026 переведено на маркетплейс (владелец), записи superseded'
 WHERE object_type = 'pool' AND object_id IN (6, 7);

-- Правила алертов: темп и обеспеченность — по AMZ-ES и AMZ-FR; пулы без собственного плана из правил уходят.
DELETE FROM kabinet_data.forecast_alert_rules WHERE object_type = 'pool' AND object_id IN (6, 7);
INSERT INTO kabinet_data.forecast_alert_rules (object_type, object_id, pace_alert, missing_alert, note) VALUES
 ('marketplace', 1, TRUE, TRUE, 'ES: план листа Amazon Product Planning лежит на маркетплейсе (18.09.2026)'),
 ('marketplace', 3, TRUE, TRUE, 'FR: то же')
ON CONFLICT (object_type, object_id) DO UPDATE SET pace_alert = EXCLUDED.pace_alert, missing_alert = EXCLUDED.missing_alert, note = EXCLUDED.note, updated_at = now();
COMMIT;
SELECT object_type, object_id, count(*) FILTER (WHERE is_current) AS current_rows FROM kabinet_data.forecast_register WHERE record_type='sales' GROUP BY 1,2 ORDER BY 1,2;
