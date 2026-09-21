-- Доработки складов от 17.09.2026, п. «Типы складов»: третий тип «Обзор» (view) — склад,
-- который показываем, но по которому решений не принимаем.
-- Таблица kabinet_data.warehouses принадлежит владельцу (v.tereshyn@dniprom.com): ограничение
-- warehouses_type_check роль claude_code_rw поменять не может. Выполняет владелец.
BEGIN;
ALTER TABLE kabinet_data.warehouses DROP CONSTRAINT IF EXISTS warehouses_type_check;
ALTER TABLE kabinet_data.warehouses ADD CONSTRAINT warehouses_type_check
    CHECK (type IN ('sales', 'transit_domestic', 'transit_inter', 'storage', 'manufacturer', 'fba', 'view'));
COMMIT;
