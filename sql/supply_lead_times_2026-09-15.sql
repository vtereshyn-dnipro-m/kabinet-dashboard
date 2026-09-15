-- 15.09.2026, сроки от Дарины: Украина → Польша 14 дней, Польша → Испания 8 дней,
-- плюс до 5 дней ожидания рейса — машина в Мадрид ходит только по средам. Итого 22–27.
-- Кладём в справочник маршрутов, не в код.

-- Piasecznie → Madrid: было экспертное «2 дня», реальность — 8 + ожидание рейса
UPDATE kabinet_data.supply_chains
   SET median_days = 8, lead_source = 'expert', updated_at = now(),
       note = 'PL→ES 8 дней + до 5 дней ожидания рейса (машина в Мадрид по средам); Дарина, 15.09.2026'
 WHERE id = 2;

-- Украина → Польша: плеча в справочнике не было. Источник — основной склад Украины
-- (Тернополь Подольская 21, по имени «Карантин», но по сути основной — Дарина).
INSERT INTO kabinet_data.supply_chains (from_warehouse_id, to_warehouse_id, route_type, median_days, shipment_count, is_active, note, lead_source, sample_size)
SELECT 37, 32, 'internal', 14, 0, TRUE, 'UA→PL 14 дней; Дарина, 15.09.2026. Плечо не считаем сами: его ведёт Дарина в листе Poland-Spain', 'expert', NULL
WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.supply_chains WHERE from_warehouse_id = 37 AND to_warehouse_id = 32);

-- Роль склада: Тернополь Подольская 21 — обычное хранение, не карантин (Дарина, 15.09.2026)
UPDATE kabinet_data.warehouses SET stock_role = 'available',
       note = concat_ws(' | ', note, 'по имени «Карантин», по сути основной склад Украины — Дарина, 15.09.2026')
 WHERE id = 37 AND stock_role <> 'available';

-- Параметры автозаказа, которые люди будут уточнять, — в таблице, не константами
CREATE TABLE IF NOT EXISTS kabinet_data.reorder_params (
    key        TEXT PRIMARY KEY,
    value      NUMERIC NOT NULL,
    note       TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT ON kabinet_data.reorder_params TO claude_code_ro;
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
 ('quarantine_reject_pct', 0, 'доля отсева на карантине Piasecznie, %; Дарина уточнит у снабжения (15.09.2026: ноль)'),
 ('madrid_dispatch_wait_days', 5, 'ожидание рейса Piasecznie → Мадрид: машина по средам, до 5 дней')
ON CONFLICT (key) DO NOTHING;

SELECT s.id, wf.name AS from_wh, wt.name AS to_wh, s.median_days, s.note FROM kabinet_data.supply_chains s
 JOIN kabinet_data.warehouses wf ON wf.id=s.from_warehouse_id JOIN kabinet_data.warehouses wt ON wt.id=s.to_warehouse_id
 WHERE s.id = 2 OR (s.from_warehouse_id = 37 AND s.to_warehouse_id = 32);
