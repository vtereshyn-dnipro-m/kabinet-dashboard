-- Внешние ключи для warehouse_marketplaces. Lakebase, kabinet_data.
--
-- Отдельным файлом, потому что сослаться на чужую таблицу можно только с
-- правом REFERENCES на неё, а выдать его может лишь владелец. Роль
-- claude_code_rw получила INSERT/UPDATE/DELETE и CREATE, но не REFERENCES,
-- поэтому таблица создана без ключей.
--
-- Запускать под v.tereshyn@dniprom.com — тем же ноутбуком, что и
-- sql/claude_code_rw.sql. После первого блока Claude Code сможет вешать
-- ключи на будущие таблицы сам, второй блок к тому моменту уже не нужен.

BEGIN;

-- ── 1. Право, которого не хватило ────────────────────────────────────
GRANT REFERENCES ON kabinet_data.warehouses, kabinet_data.marketplaces
   TO claude_code_rw;

-- ── 2. Сами ключи ────────────────────────────────────────────────────
-- CASCADE намеренно: строка связки без склада или без площадки смысла не
-- имеет, и держать её как сироту незачем.
ALTER TABLE kabinet_data.warehouse_marketplaces
  ADD CONSTRAINT warehouse_marketplaces_warehouse_fk
      FOREIGN KEY (warehouse_id)   REFERENCES kabinet_data.warehouses(id)   ON DELETE CASCADE,
  ADD CONSTRAINT warehouse_marketplaces_marketplace_fk
      FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces(id) ON DELETE CASCADE;

COMMIT;

-- ── Проверка: ожидаем две строки ─────────────────────────────────────
SELECT conname, pg_get_constraintdef(oid) AS opredelenie
  FROM pg_constraint
 WHERE conrelid = 'kabinet_data.warehouse_marketplaces'::regclass
   AND contype = 'f'
 ORDER BY conname;
