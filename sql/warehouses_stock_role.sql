-- 14.09.2026. Роль склада в расчёте потребности.
--
-- Карантин в Piasecznie — информативный склад: товар пришёл и ждёт проверки,
-- через несколько недель переедет на основной. В обеспечении не участвует
-- (приоритет 0, донором не бывает), но при расчёте «сколько заказать» его
-- надо вычитать — иначе закажем то, что уже лежит за стеной. Это ровно та же
-- логика, что у товара в пути (Inbound Shipments), поэтому в автозаказе они
-- идут одним механизмом: pipeline = в пути + на проверке (Stock Loader, ячейка 5).
--
-- Роль — флаг в справочнике, а не подстрока «Карантин» в имени: имена
-- складов приходят из ERP и меняются без нас.
--
-- DDL (ALTER TABLE warehouses ADD COLUMN stock_role; reorder_recommendations
-- ADD COLUMN in_transit_qty, quarantine_qty) живёт в ячейке 5 Stock Loader:
-- таблицами владеет загрузчик, у claude_code_rw прав на ALTER нет.
UPDATE kabinet_data.warehouses
   SET stock_role = 'quarantine', shipping_priority = 0
 WHERE name IN ('RS Warszawa Piasecznie (Карантин)',
                'RS Warszawa Spain (Карантин)',
                'Тернополь Подольская, 21 Європа (Карантин)');

SELECT id, name, stock_role, shipping_priority, is_active FROM kabinet_data.warehouses WHERE stock_role <> 'available' ORDER BY id;
