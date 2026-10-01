-- Английские названия из ERP: категории всех трёх уровней и названия товаров
-- (задание владельца 01.10.2026).
--
-- ЧТО ОКАЗАЛОСЬ ПОД ИСТОЧНИКОМ, прежде чем на него опираться.
-- `dnipro_m.raw_erp_dim_nomenclature_tree_new_translate_en` — это ВЬЮ, а не таблица, и
-- связь в ней по ТЕКСТУ, а не по коду: под ней словарь `dnipro_m.dim_translation_en`
-- (`text_original` → `text_en`, 7 410 строк), который приджойнен к дереву четыре раза —
-- на название товара и на три уровня категории. Код в выдаче есть, но он от дерева, а не
-- от перевода. Практических следствий два, и оба важны:
--
--   * джойн 1:1 честный — дублей `text_original` ноль, строк во вью ровно столько же,
--     сколько кодов в дереве (21 520), размножения строк не будет;
--   * у вью и у словаря НЕТ ни одной колонки с датой, а сам словарь наполняется
--     интерактивным ноутбуком пакетами по 30 строк (275 версий, последние 01.10 в
--     09:11–09:12). Джобы, которая обновляла бы его в 07:00, в воркспейсе нет.
--
-- Поэтому правило свежести ставится на НАШУ реплику словаря: у неё есть `loaded_at`,
-- который пишет наш прогон, и правило отвечает на вопрос, на который может ответить —
-- «не встал ли наш перенос». Чтобы сторож ловил замирание САМОГО источника, словарю
-- нужна колонка с датой на стороне ERP; пока её нет, обещать эту проверку нельзя.
--
-- КЛЮЧ НЕ МЕНЯЕТСЯ. Ключ узла остаётся нормализованным украинским путём: перевод — это
-- ПОДПИСЬ на экране, и связь по нему не строится. Та же развязка, что у стран
-- (`country_names`) и у отображаемых имён складов (`warehouse_attributes.display_name`).

BEGIN;

-- ---------- реплика словаря переводов ----------
-- Первоисточник остаётся в `dnipro_m` — он нужен не только Кабинету. Но страницы читают
-- Lakebase и кросс-проектных запросов не делают, а английское название нужно в SQL
-- страницы. Словарь по тексту, а не по коду, пригодится и дальше: переводить придётся не
-- только номенклатуру.
CREATE TABLE IF NOT EXISTS kabinet_data.raw_erp_translation_en (
    text_original text PRIMARY KEY,
    text_en       text NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE kabinet_data.raw_erp_translation_en IS
    'Реплика dnipro_m.dim_translation_en: перевод строк ERP на английский по тексту. Пишет Kabinet - SKU Master Loader.';

-- ---------- английские названия товаров ----------
ALTER TABLE kabinet_data.sku_master ADD COLUMN IF NOT EXISTS name_en text;
COMMENT ON COLUMN kabinet_data.sku_master.name_en IS
    'Название из ERP по-английски (dim_translation_en). Пусто = перевода ещё нет, на экране остаётся оригинал.';

-- ---------- английские названия категорий ----------
-- Переводы лежат РЯДОМ с украинскими, а не вместо них: на экране нужны оба (в русском
-- интерфейсе показываем оригинал ERP, в английском — перевод), а норматив, заведённый на
-- категорию, не должен зависеть от того, перевели её или нет.
ALTER TABLE kabinet_data.sku_category_tree ADD COLUMN IF NOT EXISTS level1_en text;
ALTER TABLE kabinet_data.sku_category_tree ADD COLUMN IF NOT EXISTS level2_en text;
ALTER TABLE kabinet_data.sku_category_tree ADD COLUMN IF NOT EXISTS level3_en text;
ALTER TABLE kabinet_data.sku_category_tree ADD COLUMN IF NOT EXISTS title_en text;

-- Два разных узла с ОДНИМ английским названием — это не редкость, которую можно
-- проигнорировать, а готовая путаница на экране: человек видит две одинаковые строки и
-- не знает, которая из них какая. Поэтому такие узлы помечаются, и подпись у них
-- откатывается к оригиналу — неудобно, но различимо. Флаг ставит загрузчик, сравнивая
-- узел с СОСЁДЯМИ по одному родителю: одинаковые названия в разных ветках законны
-- («Аксесуари» под каждым инструментом), а внутри одной ветки — нет.
ALTER TABLE kabinet_data.sku_category_tree ADD COLUMN IF NOT EXISTS en_ambiguous boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN kabinet_data.sku_category_tree.en_ambiguous IS
    'Английское название совпало с соседним узлом того же родителя — на экране показывается оригинал, пока перевод не поправят в ERP.';

-- ---------- подпись узла на языке интерфейса ----------
-- Одно место, где решается, что человек видит. Разъехаться двум написаниям этого
-- правила негде: страницы читают вью, а не собирают COALESCE каждая по-своему.
CREATE OR REPLACE VIEW kabinet_data.v_sku_category_tree AS
WITH подписи AS (
    SELECT t.*, n.name_ru, n.name_uk, n.name_en,
           -- что встало бы английской подписью: своя, иначе перевод ERP
           COALESCE(n.name_en, t.title_en) AS кандидат_en
      FROM kabinet_data.sku_category_tree t
      LEFT JOIN kabinet_data.category_names n ON n.category_key = t.category_key
),
спорные AS (
    -- Неоднозначность считается ПОСЛЕ ручных подписей, а не по сырому переводу: стоило
    -- завести своё название одному из двух одинаково переведённых узлов, и второй
    -- перестал быть спорным — показывать у него украинский оригинал больше незачем.
    -- Загрузчик этого знать не может: он видит только перевод, а подпись заводят потом.
    -- Сравниваем соседей по ОДНОМУ родителю: одинаковые названия в разных ветках
    -- законны («Аксесуари» есть под каждым инструментом), внутри ветки — нет.
    SELECT category_key,
           count(*) OVER (PARTITION BY parent_key, кандидат_en) > 1 AS совпало
      FROM подписи
     WHERE кандидат_en IS NOT NULL
)
SELECT p.category_key, p.parent_key, p.depth,
       p.level1, p.level2, p.level3, p.title,
       p.level1_en, p.level2_en, p.level3_en, p.title_en, p.en_ambiguous,
       p.is_active, p.source, p.updated_at,
       -- Русский и украинский: наш ручной перевод (сейчас это шестнадцать названий
       -- первого уровня), иначе оригинал ERP — он украинский, и для русского экрана это
       -- осознанный компромисс: переводить 644 названия дороже, чем они стоят.
       COALESCE(p.name_ru, p.title) AS label_ru,
       COALESCE(p.name_uk, p.title) AS label_uk,
       -- Английский: своя подпись главнее перевода (её поставил человек, и спорной она
       -- быть не может), перевод главнее оригинала, а спорный перевод не показывается.
       COALESCE(p.name_en,
                CASE WHEN NOT COALESCE(s.совпало, false) THEN p.title_en END,
                p.title) AS label_en,
       -- Откуда взялась английская подпись — чтобы на экране было видно, где перевод
       -- ERP, где наша правка, а где перевода ещё нет и стоит оригинал.
       CASE WHEN p.name_en IS NOT NULL             THEN 'manual'
            WHEN COALESCE(s.совпало, false)        THEN 'ambiguous'
            WHEN p.title_en IS NOT NULL            THEN 'erp'
            ELSE 'original' END AS label_en_source,
       p.name_ru, p.name_uk, p.name_en
  FROM подписи p
  LEFT JOIN спорные s ON s.category_key = p.category_key;

COMMENT ON VIEW kabinet_data.v_sku_category_tree IS
    'Дерево категорий с подписью узла на трёх языках: label_ru / label_uk / label_en плюс источник английской подписи.';

GRANT SELECT ON kabinet_data.raw_erp_translation_en, kabinet_data.v_sku_category_tree
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
-- Пишет реплику джоба, то есть принципал джоб, а не приложение. Грант нужен СРАЗУ:
-- таблицу создаёт роль Кабинета, а прогон идёт под другим — на этом уже падал Buy Box.
GRANT INSERT, UPDATE, DELETE ON kabinet_data.raw_erp_translation_en
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- ---------- правило свежести ----------
INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment)
VALUES ('kabinet_data.raw_erp_translation_en', 'loaded_at', 48, 'lakebase', 'DATA_OWNER', true,
        'Перевод ERP на английский: реплика dnipro_m.dim_translation_en, пишет Kabinet - SKU Master Loader (06:00 Kyiv). 48 ч — сутки с запасом на один пропущенный прогон. У самого источника колонки с датой нет, поэтому следим за своей копией, а не за ERP.')
ON CONFLICT (table_name) DO UPDATE
   SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
       source_type = EXCLUDED.source_type, is_active = true,
       comment = EXCLUDED.comment, updated_at = now();

COMMIT;

-- ---------- ручная правка двух спорных переводов ----------
-- В словаре ERP «Шурупокрути 12В» и «Гвинтоверти 12В» переведены ОДНОЙ строкой
-- «Screwdrivers 12B», и то же на 20В. Это разные инструменты: под «Гвинтоверти» лежат
-- «Аккумуляторный ударный винтоверт Dnipro-M DTD-200» и подобные, то есть impact driver,
-- а не шурупокрут. Своей подписью это лечится здесь и сейчас; список отправлен Дарине,
-- чтобы поправили в самом словаре.
--
-- Заодно видно вторую, более широкую описку того же словаря: вольты переведены латинской
-- «B» вместо «V» — «Tool 20B», «Pruners 12B», 61 название. Её НЕ лечим здесь по одному:
-- это правило, а не шестьдесят одно решение, и загрузчик приводит такие названия сам,
-- только когда в украинском оригинале на том же месте стоит кириллическая «В».
INSERT INTO kabinet_data.category_names (category_key, name_en, updated_by) VALUES
    ('акумуляторний інструмент/інструмент 12в/гвинтоверти 12в', 'Impact drivers 12V', 'fix:erp-collision:2026-10-01'),
    ('акумуляторний інструмент/інструмент 20в/гвинтоверти 20в', 'Impact drivers 20V', 'fix:erp-collision:2026-10-01')
ON CONFLICT (category_key) DO UPDATE
   SET name_en = EXCLUDED.name_en, updated_by = EXCLUDED.updated_by, updated_at = now()
 WHERE kabinet_data.category_names.name_en IS NULL;

-- Проверка глазами: подпись узла на трёх языках и откуда взялась английская.
SELECT depth, title AS в_erp, label_ru, label_en, label_en_source
  FROM kabinet_data.v_sku_category_tree
 WHERE title LIKE '%винтоверт%' OR title LIKE '%Шурупокрут%' OR depth = 1
 ORDER BY depth, title LIMIT 24;
