-- Партнёрские точки «Партнер ФМ …» (решение 25.09.2026).
--
-- Правило: остаток партнёрской точки нужен для пополнения САМОЙ точки, но он не наш доступный товар —
-- ни в обеспечение других каналов, ни в переброску, ни донором. Признак — `warehouse_attributes.is_partner`,
-- загрузчики читают его оттуда; отдельного списка в коде нет.
--
-- Что важно знать перед тем, как считать по ним пополнение: остатка партнёрских точек у нас НЕТ ни в одном
-- источнике. ERP (`raw_erp_inventory_stock_auto`) за всю историю знает одиннадцать складов — Piasecznie,
-- Тернополь и три «RS Warszawa Spain»; Odoo отдаёт Мадрид и одиннадцать «Tienda …». Партнёрских точек нет
-- ни там, ни там, и склад Odoo «Partners» (код PR) пуст. Пока источник не появится, считать пополнение
-- точки нечем — механизм готов, данных нет.
UPDATE kabinet_data.warehouses
   SET note = COALESCE(NULLIF(note, ''), 'Партнёрская точка: остаток не наш, учитывается только для пополнения самой точки (25.09.2026)')
 WHERE name ILIKE 'Партнер ФМ%';

INSERT INTO kabinet_data.warehouse_attributes (warehouse_id, is_partner, updated_by)
SELECT id, true, 'kabinet' FROM kabinet_data.warehouses WHERE name ILIKE 'Партнер ФМ%'
ON CONFLICT (warehouse_id) DO UPDATE SET is_partner = true, updated_at = now(), updated_by = 'kabinet';

-- Что вышло: партнёрские точки, их маршруты и наличие остатка
