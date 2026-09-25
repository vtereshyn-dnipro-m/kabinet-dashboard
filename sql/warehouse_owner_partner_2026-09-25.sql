-- Владелец складов и партнёрский склад (уточнения Дарины, 25.09.2026).
--
-- 1. Владелец. Odoo знает 22 склада и две компании; наш справочник — 51 склад, и у 39 владелец был пуст
--    (FBA по странам, Piasecznie, Тернополь, фирменные магазины — Odoo их не содержит). Решение Дарины:
--    все склады Dnipro-M; у испанских юрлицо DNIPRO-M STORES SOCIEDAD LIMITADA, у польских и украинских
--    юрлицо уточняется — до тех пор пишем «Dnipro-M» без юрлица. Источник помечаем `manual:darina`,
--    чтобы джоба `Kabinet - Warehouse Owner from Odoo` не выглядела автором этих строк: она правит только
--    склады, которые нашла в Odoo, и ручные значения не перетирает.
ALTER TABLE kabinet_data.warehouse_attributes ADD COLUMN IF NOT EXISTS is_partner boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN kabinet_data.warehouse_attributes.is_partner IS
    'Склад партнёра: его остатки и продажи в расчёты Кабинета не берём (решение 25.09.2026). Список читают загрузчики.';

INSERT INTO kabinet_data.warehouse_attributes (warehouse_id, owner_company, owner_source, owner_synced_at, updated_by)
SELECT w.id,
       CASE WHEN w.country = 'ES' THEN 'DNIPRO-M STORES SOCIEDAD LIMITADA' ELSE 'Dnipro-M' END,
       'manual:darina', now(), 'kabinet'
FROM kabinet_data.warehouses w
LEFT JOIN kabinet_data.warehouse_attributes a ON a.warehouse_id = w.id
WHERE coalesce(a.owner_company, '') = ''
  -- франчайзи («Партнер ФМ …») сюда не попадают: это склады партнёров, и Dnipro-M им владельцем не является
  AND w.name NOT ILIKE 'Партнер ФМ%'
ON CONFLICT (warehouse_id) DO UPDATE SET
    owner_company = EXCLUDED.owner_company, owner_source = EXCLUDED.owner_source,
    owner_synced_at = now(), updated_at = now(), updated_by = EXCLUDED.updated_by;

-- 2. Склад партнёра M&A KULGA SOLUTION. В Odoo это отдельный склад (код M&A, 734 позиции, 2 109 шт),
--    в нашем справочнике ему соответствует магазин в Аликанте: адрес совпадает с командой продаж Odoo
--    «Tienda Calle de Maestro Alonso», по которой этот склад и виден в данных. Запись оставляем
--    (за ней история 528 ТТН), но выключаем и помечаем — остатки и продажи партнёра не наши.
UPDATE kabinet_data.warehouses
   SET is_active = false,
       note = 'Партнёр M&A KULGA SOLUTION: остатки и продажи в расчёты Кабинета не берём (25.09.2026)'
 WHERE id = 59;

INSERT INTO kabinet_data.warehouse_attributes (warehouse_id, owner_company, owner_source, owner_synced_at, is_partner, updated_by)
VALUES (59, 'M&A KULGA SOLUTION', 'manual:darina', now(), true, 'kabinet')
ON CONFLICT (warehouse_id) DO UPDATE SET
    owner_company = 'M&A KULGA SOLUTION', owner_source = 'manual:darina',
    owner_synced_at = now(), is_partner = true, updated_at = now(), updated_by = 'kabinet';

-- Имя склада партнёра в Odoo — чтобы загрузчики отсеивали его по данным, а не по строке в коде.
INSERT INTO kabinet_data.warehouse_external_ids (warehouse_id, system_name, external_code, external_name, updated_by)
VALUES (59, 'odoo', 'M&A', 'M&A KULGA SOLUTION', 'kabinet')
ON CONFLICT (warehouse_id, system_name, external_code) DO UPDATE SET
    external_name = 'M&A KULGA SOLUTION', updated_at = now(), updated_by = 'kabinet';

-- 3. Переброски: маршрут «Мадрид → магазин партнёра» был последней милей для статистики сроков.
--    Выключаем — он про доставку партнёру, а не про наше обеспечение.
UPDATE kabinet_data.supply_chains
   SET is_active = false,
       note = coalesce(note || '; ', '') || 'выключен 25.09.2026: склад партнёра M&A KULGA SOLUTION',
       updated_at = now()
 WHERE to_warehouse_id = 59 AND is_active;
