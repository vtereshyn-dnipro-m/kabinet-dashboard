-- Площадки, которые обеспечивает склад.
--
-- Зачем отдельная таблица: в kabinet_data.warehouses площадка лежит одной
-- текстовой колонкой marketplace ('ES', 'Amazon', 'DE'), то есть одна на склад
-- и без связи со справочником. Реально склад обеспечивает несколько площадок
-- сразу — RS Warszawa Spain отгружает и на Amazon ES, и на Leroy Merlin.
--
-- Приоритет обеспечения отдельной таблицы не требует: он глобальный, один
-- на склад, и уже живёт в warehouses.shipping_priority.
--
-- Запускать под ролью с CREATE в схеме: v.tereshyn@dniprom.com, принципал
-- Кабинета или claude_code_ro после sql/claude_code_rw.sql. Строка из
-- .mcp.json для этого НЕ годится — там claude_code_ro без права CREATE.
--
-- В psql обязательно -v ON_ERROR_STOP=1. Без него ошибка внутри BEGIN…COMMIT
-- уводит транзакцию в abort, COMMIT срабатывает как ROLLBACK, и прогон
-- выглядит успешным при пустой базе. Проверить, куда подключились: \conninfo.
--
-- Экран «Справочники → Склады» до этого момента работает, но блок площадок
-- показывает предупреждение вместо галочек.

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_marketplaces (
    warehouse_id   integer     NOT NULL
                   REFERENCES kabinet_data.warehouses(id)   ON DELETE CASCADE,
    marketplace_id integer     NOT NULL
                   REFERENCES kabinet_data.marketplaces(id) ON DELETE CASCADE,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    updated_by     text,
    PRIMARY KEY (warehouse_id, marketplace_id)
);

COMMENT ON TABLE kabinet_data.warehouse_marketplaces IS
    'Какие площадки обеспечивает склад. Заполняется вручную на экране '
    '«Справочники → Склады»; строки FBA засеяны автоматически по стране.';

CREATE INDEX IF NOT EXISTS warehouse_marketplaces_mp_idx
    ON kabinet_data.warehouse_marketplaces (marketplace_id);

-- Кабинет ходит в базу под этим сервис-принципалом и пишет с экрана
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.warehouse_marketplaces
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
-- MCP-доступ на чтение, чтобы проверять заполнение
GRANT SELECT ON kabinet_data.warehouse_marketplaces TO claude_code_ro;

-- ── Засев FBA ──────────────────────────────────────────────────────────────
-- Для FBA выбирать нечего: склад Amazon в стране обеспечивает витрину Amazon
-- той же страны, и это не решение Ярослава, а факт. Соответствие берём
-- джойном по стране, а не списком id, — новый рынок подхватится сам.
--
-- Amazon FBA CZ останется без площадки: витрины Amazon Czechia в
-- kabinet_data.marketplaces нет. Это правда, а не пропуск засева.
INSERT INTO kabinet_data.warehouse_marketplaces (warehouse_id, marketplace_id, updated_by)
SELECT w.id, m.id, 'seed:fba-country'
  FROM kabinet_data.warehouses  w
  JOIN kabinet_data.marketplaces m
    ON m.country = w.country
   AND m.channel = 'Amazon'
 WHERE w.code LIKE 'FBA-%'
ON CONFLICT DO NOTHING;

COMMIT;

-- ── Проверка ───────────────────────────────────────────────────────────────
-- Ожидаем 12 строк: по одной на FBA DE/ES/FR/GB/IT/PL в обоих наборах id
-- (76–82 и 84–90), CZ без пары.
SELECT w.id, w.code, w.name, m.code AS mp, m.name AS mp_name
  FROM kabinet_data.warehouse_marketplaces wm
  JOIN kabinet_data.warehouses   w ON w.id = wm.warehouse_id
  JOIN kabinet_data.marketplaces m ON m.id = wm.marketplace_id
 ORDER BY w.code, m.code;
