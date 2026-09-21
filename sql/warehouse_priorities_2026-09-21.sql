-- 21.09.2026. Доработки справочника складов (Ярослав, 17.09): приоритет — свойство связи «склад × маркетплейс/пул»,
-- а не склада. Раньше приоритет лежал одним числом в warehouses.shipping_priority, и при выборе второго
-- маркетплейса он «стирал» первый, а несколько маркетплейсов получали одну цифру — по-другому эта модель и не могла.
CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_priorities (
    id           SERIAL PRIMARY KEY,
    warehouse_id INT  NOT NULL REFERENCES kabinet_data.warehouses(id),
    priority     INT  NOT NULL CHECK (priority BETWEEN 1 AND 10),
    target_type  TEXT NOT NULL CHECK (target_type IN ('marketplace', 'pool')),
    target_id    INT  NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT NOT NULL DEFAULT 'kabinet',
    UNIQUE (warehouse_id, priority),
    UNIQUE (warehouse_id, target_type, target_id)
);
COMMENT ON TABLE kabinet_data.warehouse_priorities IS 'ТЗ Warehouse Directory п.7: у склада продаж до 10 приоритетов, в каждом — один маркетплейс или пул из справочников.';
GRANT SELECT ON kabinet_data.warehouse_priorities TO claude_code_ro, "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.warehouse_priorities TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE ON SEQUENCE kabinet_data.warehouse_priorities_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
-- перенос того, что уже проставлено: связь есть — приоритет из склада, если он 1..10, иначе по порядку кода
INSERT INTO kabinet_data.warehouse_priorities (warehouse_id, priority, target_type, target_id, updated_by)
SELECT l.warehouse_id,
       CASE WHEN w.shipping_priority BETWEEN 1 AND 10 AND COUNT(*) OVER (PARTITION BY l.warehouse_id) = 1 THEN w.shipping_priority
            ELSE ROW_NUMBER() OVER (PARTITION BY l.warehouse_id ORDER BY m.code) END,
       'marketplace', l.marketplace_id, 'migration-2026-09-21'
FROM kabinet_data.warehouse_marketplaces l
JOIN kabinet_data.warehouses w ON w.id = l.warehouse_id
JOIN kabinet_data.marketplaces_new m ON m.id = l.marketplace_id
ON CONFLICT DO NOTHING;
SELECT w.name, p.priority, p.target_type, p.target_id FROM kabinet_data.warehouse_priorities p JOIN kabinet_data.warehouses w ON w.id = p.warehouse_id ORDER BY w.name, p.priority;
