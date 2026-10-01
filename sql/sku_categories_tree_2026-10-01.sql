-- Справочник категорий SKU по дереву ERP (ТЗ «Остатки», пункт 1).
--
-- Откуда берём и почему именно оттуда — выяснено разведкой 01.10.2026:
--
--   * в ЛИСТИНГАХ Amazon категорий нет вовсе: `zshop_category1` и `zshop_browse_path`
--     заполнены в 315 760 строках, но значение там одно на все — пустая строка;
--   * своя таксономия Amazon есть (`raw_amazon_catalog_items`, 924 строки, только ES и
--     FR, 200 категорий), но это полка Amazon, а не наша классификация: норматив
--     «садовой технике 60 дней» по ней не задать;
--   * в Odoo своей категории нет — Odoo даёт связь кодов и состав;
--   * дерево компании лежит в ERP: `raw_erp_dim_nomenclature_tree_new`, 21 510 кодов,
--     три уровня (16 / 159 / 485). Покрытие нашего периметра 75 % точным кодом и 92 %
--     с откатом к базовому — лучший источник с большим отрывом;
--   * планировочная таблица `raw_planning_spain_2026` даёт ABC и статус, но загружена
--     ОДИН раз (31.08.2026, одна `load_date`, джобы нет), мешает цикл с каналом
--     («ФМ», «Сайт ексклюзив») и к покрытию не добавляет ничего: 397 кодов и с ней,
--     и без неё. В источники не берём.
--
-- **У категорий в ERP НЕТ кодов** — только названия; `uidCommodityCategory` в соседней
-- таблице это другая классификация (1 248 значений против 485), и справочника, который
-- расшифровал бы те uid, в хранилище нет. Поэтому ключ категории выводим из названия
-- нормализацией — тем же приёмом, что `country_name_key`: регистр не важен, края
-- обрезаны, пробелы внутри сведены. Это и есть защита от спора «та ли это категория»:
-- «Акумуляторний інструмент» и «Акумуляторний Інструмент» дают один ключ.

BEGIN;

-- ---------- нормализация названия в ключ ----------
CREATE OR REPLACE FUNCTION kabinet_data.category_name_key(txt text)
RETURNS text
LANGUAGE sql IMMUTABLE
AS $$ SELECT lower(regexp_replace(btrim(COALESCE(txt, '')), '\s+', ' ', 'g')) $$;

-- ---------- дерево категорий ----------
CREATE TABLE IF NOT EXISTS kabinet_data.sku_category_tree (
    category_key text PRIMARY KEY,          -- нормализованный путь: «уровень1/уровень2/уровень3»
    parent_key   text REFERENCES kabinet_data.sku_category_tree(category_key),
    depth        smallint NOT NULL CHECK (depth BETWEEN 1 AND 3),
    level1       text NOT NULL,             -- названия как в ERP, в том виде, как там написаны
    level2       text,
    level3       text,
    title        text NOT NULL,             -- имя самого узла: level3, иначе level2, иначе level1
    is_active    boolean NOT NULL DEFAULT true,
    source       text NOT NULL DEFAULT 'erp',
    updated_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE kabinet_data.sku_category_tree IS
    'Дерево категорий из ERP. Ключ выведен из названия: своих кодов у категорий в ERP нет.';

CREATE INDEX IF NOT EXISTS sku_category_tree_parent_idx
    ON kabinet_data.sku_category_tree (parent_key);

-- ---------- подписи первого уровня на трёх языках ----------
-- Переводим ТОЛЬКО первый уровень (16 названий) — решение владельца 01.10.2026.
-- Второй и третий остаются как в ERP: их 159 и 485, и поддерживать перевод такого
-- объёма дороже, чем он стоит. Перевод — ПОДПИСЬ на экране, связь всегда по ключу:
-- ровно та же развязка, что у стран (`country_names`).
CREATE TABLE IF NOT EXISTS kabinet_data.category_names (
    category_key text PRIMARY KEY REFERENCES kabinet_data.sku_category_tree(category_key),
    name_ru text,
    name_uk text,
    name_en text,
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- связь SKU с категорией ----------
-- Таблица уже существует (её пишет ячейка `Kabinet - Coverage Projection` плоскими
-- категориями Amazon). Не заменяем, а расширяем: старая колонка остаётся, пока на неё
-- кто-то смотрит, а дерево приезжает отдельной колонкой с собственным источником.
ALTER TABLE kabinet_data.sku_categories
    ADD COLUMN IF NOT EXISTS category_key text REFERENCES kabinet_data.sku_category_tree(category_key);
ALTER TABLE kabinet_data.sku_categories
    ADD COLUMN IF NOT EXISTS key_source text;

COMMENT ON COLUMN kabinet_data.sku_categories.key_source IS
    'erp — код нашёлся в дереве; erp:base — по базовому коду без вариант-суффикса; manual — связь поставил человек, загрузчик её не трогает';

-- ---------- жизненный цикл: ручное решение главнее расчёта ----------
-- `sku_lifecycle` принадлежит владельцу базы, и расширить её роль Кабинета не может —
-- но это и к лучшему. Загрузчик переписывает ту таблицу ЦЕЛИКОМ, и ручной статус в ней
-- не пережил бы ни одного прогона. В отдельной таблице он защищён физически, а не
-- договорённостью «загрузчик обещает не трогать»: загрузчику туда просто нечем писать.
CREATE TABLE IF NOT EXISTS kabinet_data.sku_lifecycle_manual (
    sku            text NOT NULL,
    marketplace    text NOT NULL,
    status         text NOT NULL
                   CHECK (status IN ('active', 'not_launched', 'phasing_out',
                                     'seasonal_pause', 'discontinued')),
    -- дата действия: «выводим с 01.11» начинает работать 01.11, а не в момент записи
    effective_from date NOT NULL DEFAULT current_date,
    reason         text,
    updated_by     text,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sku, marketplace, effective_from)
);

COMMENT ON TABLE kabinet_data.sku_lifecycle_manual IS
    'Статусы жизненного цикла, поставленные человеком. Главнее расчётных; загрузчик сюда не пишет.';

-- Действующий статус: ручной, если его дата уже наступила, иначе расчётный из `sku_lifecycle`.
-- Вью, а не колонка: «действует ли» зависит от сегодняшней даты, и хранимое поле
-- разошлось бы с календарём ровно в полночь. Ключ строки — пара SKU × маркетплейс,
-- как в самой `sku_lifecycle`.
CREATE OR REPLACE VIEW kabinet_data.v_sku_lifecycle_current AS
WITH вместе AS (
    SELECT sku, marketplace, status, true AS is_manual, 'manual'::text AS source,
           reason, effective_from, updated_by, updated_at
      FROM kabinet_data.sku_lifecycle_manual
     WHERE effective_from <= current_date
    UNION ALL
    SELECT sku, marketplace, status, false, COALESCE(source, 'loader'),
           reason, effective_from, updated_by, updated_at
      FROM kabinet_data.sku_lifecycle
)
SELECT DISTINCT ON (sku, marketplace)
       sku, marketplace, status, is_manual, source, reason,
       effective_from, updated_by, updated_at
  FROM вместе
 ORDER BY sku, marketplace,
          -- ручное решение впереди расчёта, при равенстве — то, что начало действовать позже
          is_manual DESC, effective_from DESC NULLS LAST, updated_at DESC;

GRANT SELECT ON kabinet_data.sku_category_tree, kabinet_data.category_names,
                kabinet_data.v_sku_lifecycle_current
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT INSERT, UPDATE, DELETE ON kabinet_data.sku_category_tree, kabinet_data.category_names
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_lifecycle_manual
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.sku_lifecycle_manual
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

SELECT 'дерево' AS what, count(*)::text AS n FROM kabinet_data.sku_category_tree
UNION ALL SELECT 'подписи', count(*)::text FROM kabinet_data.category_names
UNION ALL SELECT 'связей SKU с деревом', count(*)::text
  FROM kabinet_data.sku_categories WHERE category_key IS NOT NULL;
