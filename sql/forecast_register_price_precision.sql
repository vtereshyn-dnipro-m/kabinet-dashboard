-- 17.09.2026: план в листе задан парой «штуки / евро» на SKU-месяц, а в реестре выручка —
-- генерируемая колонка quantity × target_price. Цена в 2 знака теряла до 0,005 € × штуки
-- на строке; 4 знака восстанавливают выручку листа с точностью до цента.
-- Тип колонки под генерируемой не меняется — пересобираем колонку и зависимую вью.
BEGIN;
DROP VIEW kabinet_data.v_forecast_current;
ALTER TABLE kabinet_data.forecast_register DROP COLUMN forecast_revenue;
ALTER TABLE kabinet_data.forecast_register ALTER COLUMN target_price TYPE numeric(12,4);
ALTER TABLE kabinet_data.forecast_register
    ADD COLUMN forecast_revenue numeric(14,2) GENERATED ALWAYS AS ((quantity)::numeric * target_price) STORED;
CREATE VIEW kabinet_data.v_forecast_current AS
 SELECT r.id, r.object_type, r.object_id,
        CASE WHEN r.object_type = 'marketplace' THEN m.code::text ELSE p.name END AS object_name,
        r.sku, r.month, r.quantity, r.target_price, r.forecast_revenue, r.document_id,
        d.pool_snapshot, d.posted_at
   FROM kabinet_data.forecast_register r
   JOIN kabinet_data.forecast_documents d ON d.id = r.document_id
   LEFT JOIN kabinet_data.marketplaces_new m ON r.object_type = 'marketplace' AND m.id = r.object_id
   LEFT JOIN kabinet_data.pools p ON r.object_type = 'pool' AND p.id = r.object_id
  WHERE r.record_type = 'sales' AND r.is_current;
GRANT SELECT ON kabinet_data.v_forecast_current TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
COMMIT;
SELECT column_name, numeric_scale, generation_expression FROM information_schema.columns
 WHERE table_schema='kabinet_data' AND table_name='forecast_register' AND column_name IN ('target_price','forecast_revenue');
