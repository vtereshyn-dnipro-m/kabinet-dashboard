-- Отображаемое название склада: имя из ERP на экран не годится дословно.
--
-- «RS Warszawa Piasecznie (Основний)» — украинское слово внутри русского интерфейса. Имя
-- приезжает из ERP, править его у себя нельзя: по нему склады сопоставляются в остатках,
-- накладных и маршрутах, и переименование порвало бы связи (так уже было с дублями «Amazon FBA XX»).
-- Поэтому рядом — своё отображаемое имя: `warehouses` принадлежит владельцу базы и от роли
-- Кабинета не расширяется, значит колонка идёт в нашу `warehouse_attributes`.
--
-- Правило чтения: показываем `display_name`, если задано, иначе `warehouses.name`. Сопоставление
-- и любые связи — всегда по `name`, отображаемое имя в них не участвует вовсе.
ALTER TABLE kabinet_data.warehouse_attributes
    ADD COLUMN IF NOT EXISTS display_name TEXT;

COMMENT ON COLUMN kabinet_data.warehouse_attributes.display_name IS
    'Название склада для экрана. Имя из ERP (warehouses.name) остаётся ключом сопоставления; '
    'здесь — то, что видит человек. Пусто = показываем имя из ERP как есть.';

-- Единственное известное на 28.09.2026 место, где имя ERP выглядит ошибкой интерфейса.
UPDATE kabinet_data.warehouse_attributes a
   SET display_name = 'RS Warszawa Piasecznie (основной)', updated_at = now(),
       updated_by = 'kabinet: украинское слово из имени ERP'
  FROM kabinet_data.warehouses w
 WHERE w.id = a.warehouse_id AND w.name = 'RS Warszawa Piasecznie (Основний)';

INSERT INTO kabinet_data.warehouse_attributes (warehouse_id, display_name, updated_by)
SELECT w.id, 'RS Warszawa Piasecznie (основной)', 'kabinet: украинское слово из имени ERP'
  FROM kabinet_data.warehouses w
 WHERE w.name = 'RS Warszawa Piasecznie (Основний)'
   AND NOT EXISTS (SELECT 1 FROM kabinet_data.warehouse_attributes a WHERE a.warehouse_id = w.id);
