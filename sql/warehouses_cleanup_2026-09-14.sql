-- 14.09.2026, по указанию владельца. Три правки в справочнике складов.
--
-- 1. RS Warszawa Spain (Основной / Amazon / Карантин), id 34/36/35 — устарели.
--    Физически это RS Spain Madrid (Stock), id 43: в Odoo (raw_odoo_stock) их нет,
--    там только «RS Spain Madrid (Stock)» и Tiendas. В старом ERP
--    (raw_erp_inventory_stock_auto) имена ещё живут, поэтому строки НЕ удаляем:
--    Availability History пишет историю по name→id, и она должна продолжать
--    ложиться в те же id. Гасим is_active, приоритет 0, canonical_id → 43.
--    Склад отгрузки на маркетплейсы один — id 43, приоритет 1.
--    Маршруты 34→ФМ (last_mile, ttn_planned, реальные сроки по сотням ТТН)
--    переносим на 43: это статистика того же физического склада.
--
-- 2. Tiendas: все шесть из Odoo уже заведены (id 45, 47, 49, 51, 52, 54, type
--    'sales'), новых строк нет.
--
-- 3. Дубли FBA: 76–82 «Amazon FBA XX» и 84–90 «FBA XX» под одним кодом.
--    Оставляем 84–90: их имена зашиты в Kabinet - Availability History
--    (FBA_LOCATIONS), туда пишутся остатки. Маршруты и привязки к рынкам
--    с 76–82 переносим и строки удаляем — после переноса на них не ссылается
--    ничего (daily_availability_history — пусто, warehouse_supply_links — пусто).
--
-- Бэкап удаляемых строк (warehouses 76–82):
--   76 Amazon FBA CZ sales Amazon CZ FBA-CZ | 77 Amazon FBA DE sales Amazon DE FBA-DE
--   78 Amazon FBA ES sales Amazon ES FBA-ES | 79 Amazon FBA FR sales Amazon FR FBA-FR
--   80 Amazon FBA GB sales Amazon GB FBA-GB | 81 Amazon FBA IT sales Amazon IT FBA-IT
--   82 Amazon FBA PL sales Amazon PL FBA-PL   (created 21.07.2026, все is_active, prio 0)

BEGIN;

-- ── 1. RS Warszawa Spain → устарели, RS Spain Madrid (Stock) — единственный склад отгрузки
UPDATE kabinet_data.warehouses
   SET is_active = FALSE, shipping_priority = 0, canonical_id = 43,
       note = concat_ws(' | ', note, 'устарел 14.09.2026: физически RS Spain Madrid (Stock) id 43, в Odoo не существует')
 WHERE id IN (34, 35, 36);

UPDATE kabinet_data.warehouses
   SET shipping_priority = 1,
       note = concat_ws(' | ', note, 'с 14.09.2026 единственный склад отгрузки на маркетплейсы (приоритет 1)')
 WHERE id = 43;

-- маршруты 34→X переносим на 43 там, где пары 43→X ещё нет
UPDATE kabinet_data.supply_chains s
   SET from_warehouse_id = 43, updated_at = now(),
       note = concat_ws(' | ', note, 'перенесён с RS Warszawa Spain (id 34) 14.09.2026')
 WHERE s.from_warehouse_id = 34
   AND s.to_warehouse_id <> 43
   AND NOT EXISTS (SELECT 1 FROM kabinet_data.supply_chains x
                    WHERE x.from_warehouse_id = 43 AND x.to_warehouse_id = s.to_warehouse_id);

-- Piasecznie → Warszawa Spain становится Piasecznie → Madrid
UPDATE kabinet_data.supply_chains
   SET to_warehouse_id = 43, updated_at = now(),
       note = concat_ws(' | ', note, 'цель перенесена с RS Warszawa Spain (id 34) 14.09.2026')
 WHERE from_warehouse_id = 32 AND to_warehouse_id = 34;

-- остальное с 34/35/36 (34→43 «сам в себя», 34→78 при живом 43→78, всё с 36) — гасим
UPDATE kabinet_data.supply_chains
   SET is_active = FALSE, updated_at = now(),
       note = concat_ws(' | ', note, 'выключен 14.09.2026: склад-источник устарел')
 WHERE (from_warehouse_id IN (34, 35, 36) OR to_warehouse_id IN (34, 35, 36))
   AND is_active IS NOT FALSE;

-- ── 3. Дубли FBA: маршруты и рынки с 76–82 на 84–90, старые строки удаляем
UPDATE kabinet_data.supply_chains s
   SET to_warehouse_id = s.to_warehouse_id + 8, updated_at = now()
 WHERE s.to_warehouse_id BETWEEN 76 AND 82
   AND NOT EXISTS (SELECT 1 FROM kabinet_data.supply_chains x
                    WHERE x.from_warehouse_id = s.from_warehouse_id
                      AND x.to_warehouse_id = s.to_warehouse_id + 8);
DELETE FROM kabinet_data.supply_chains WHERE to_warehouse_id BETWEEN 76 AND 82;  -- остались только дубли пар

INSERT INTO kabinet_data.warehouse_marketplaces (warehouse_id, marketplace_id, updated_at, updated_by)
SELECT warehouse_id + 8, marketplace_id, now(), 'cleanup 14.09.2026'
  FROM kabinet_data.warehouse_marketplaces m
 WHERE warehouse_id BETWEEN 76 AND 82
   AND NOT EXISTS (SELECT 1 FROM kabinet_data.warehouse_marketplaces x
                    WHERE x.warehouse_id = m.warehouse_id + 8 AND x.marketplace_id = m.marketplace_id);
DELETE FROM kabinet_data.warehouse_marketplaces WHERE warehouse_id BETWEEN 76 AND 82;

-- у оставшихся FBA-строк выравниваем «площадку»: это склады Amazon, а не рынок
UPDATE kabinet_data.warehouses
   SET marketplace = 'Amazon',
       note = concat_ws(' | ', note, 'дубль «Amazon FBA» (id ' || (id - 8)::text || ') удалён 14.09.2026, маршруты перенесены сюда')
 WHERE id BETWEEN 84 AND 90;

DELETE FROM kabinet_data.warehouses WHERE id BETWEEN 76 AND 82;

COMMIT;

-- Проверка
SELECT id, name, is_active, shipping_priority, canonical_id,
       (SELECT count(*) FROM kabinet_data.supply_chains s WHERE (s.from_warehouse_id = w.id OR s.to_warehouse_id = w.id) AND s.is_active) AS live_routes,
       (SELECT count(*) FROM kabinet_data.warehouse_marketplaces m WHERE m.warehouse_id = w.id) AS mps
  FROM kabinet_data.warehouses w
 WHERE id IN (34, 35, 36, 43) OR id BETWEEN 76 AND 90
 ORDER BY id;
