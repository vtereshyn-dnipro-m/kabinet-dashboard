-- Правка вью дрейфа по итогам приёмки сценариев 12 и 21: индикатор не гас после успешной замены.
--
-- Причина: по ТЗ §21 замена касается только текущего и будущих месяцев, прошедшие остаются
-- действующими. После замены у прежнего документа оставались действующие записи за прошлые месяцы,
-- вью видела документ живым, а его сохранённый состав — разошедшимся, и «Требуется пересоздание»
-- горело навсегда. Индикатор должен смотреть только туда, куда смотрит сама замена: на текущий
-- и будущие месяцы. Прошлое пересоздавать нечего, и требовать этого нельзя.
CREATE OR REPLACE VIEW kabinet_data.v_forecast_pool_drift AS
WITH eff AS (          -- действующие записи ЗА ТЕКУЩИЙ И БУДУЩИЕ МЕСЯЦЫ: только их и заменяют
    SELECT d.id AS document_id, d.number, d.object_id AS pool_id, d.pool_snapshot, d.pool_snapshot_date,
           count(*) AS rows_ahead,
           min(r.month) AS first_month_ahead, max(r.month) AS last_month
    FROM kabinet_data.forecast_documents d
    JOIN kabinet_data.forecast_register r ON r.document_id = d.id
                                         AND r.record_type = 'sales' AND r.is_current
                                         AND r.month >= date_trunc('month', current_date)
    WHERE d.object_type = 'pool'
    GROUP BY 1, 2, 3, 4, 5
), snap AS (
    SELECT e.*, ARRAY(SELECT DISTINCT x::int FROM jsonb_array_elements_text(e.pool_snapshot) AS t(x) ORDER BY 1) AS snapshot_ids
    FROM eff e
), members AS (
    SELECT pool_id, ARRAY(SELECT DISTINCT m2.marketplace_id FROM kabinet_data.pool_members m2
                          WHERE m2.pool_id = m.pool_id AND m2.valid_from <= current_date
                            AND (m2.valid_to IS NULL OR m2.valid_to > current_date)
                          ORDER BY 1) AS current_ids
    FROM kabinet_data.pool_members m GROUP BY pool_id
)
SELECT s.document_id, s.number, s.pool_id, p.name AS pool_name,
       s.snapshot_ids, coalesce(mb.current_ids, '{}'::int[]) AS current_ids,
       ARRAY(SELECT x FROM unnest(coalesce(mb.current_ids, '{}'::int[])) AS t(x)
             WHERE NOT x = ANY(s.snapshot_ids) ORDER BY 1) AS added_ids,
       ARRAY(SELECT x FROM unnest(s.snapshot_ids) AS t(x)
             WHERE NOT x = ANY(coalesce(mb.current_ids, '{}'::int[])) ORDER BY 1) AS removed_ids,
       coalesce(array_length(mb.current_ids, 1), 0) = 0 AS disbanded,
       s.rows_ahead, s.first_month_ahead, s.last_month, s.pool_snapshot_date
FROM snap s
JOIN kabinet_data.pools p ON p.id = s.pool_id
LEFT JOIN members mb ON mb.pool_id = s.pool_id
WHERE coalesce(mb.current_ids, '{}'::int[]) <> s.snapshot_ids;

GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO claude_code_ro;

SELECT count(*) AS дрейф_сейчас FROM kabinet_data.v_forecast_pool_drift;
