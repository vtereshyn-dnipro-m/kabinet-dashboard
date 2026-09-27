-- Нормативы покрытия по ТЗ «закладка Остатки» v0.2 §9 и справочник SKU → категория (§12.6).
--
-- Почему новый реестр, а не колонки в kabinet_data.coverage_norms. Та таблица принадлежит
-- владельцу базы (v.tereshyn@dniprom.com) — роль Кабинета в неё колонок не добавит, а нужны
-- они все: категория, даты вступления в силу и окончания, комментарий, автор. И главное —
-- ТЗ §9.2 требует ВЕРСИЙ: для одной связки несколько строк с разными периодами. Версия — это
-- строка, а не атрибут строки, поэтому боковая таблица «дополнительных полей» тут не годится.
-- Старая coverage_norms остаётся пустой и её никто не читает: вкладка «Нормативы» переведена
-- на этот реестр.
--
-- Канонической единицей ТЗ §9 называет календарные ДНИ. Недели и месяцы на экране —
-- производное отображение, в расчёт не входят.

-- ─────────────────────────────────────────────────────────── SKU → категория (ТЗ §12.6)
-- Нужен, чтобы уровень «категория» из §9.1 вообще мог сработать: без связи SKU → категория
-- норматив категории ни к одному товару не применится. Источник — сырьё Дарины
-- dnipro_m.raw_amazon_sku_category (237 SKU, 34 категории, неоднозначных нет).
CREATE TABLE IF NOT EXISTS kabinet_data.sku_categories (
    sku                 TEXT        NOT NULL,
    category            TEXT        NOT NULL,
    -- откуда взялась связь: amazon — SKU нашёлся в источнике как есть; amazon:base — нашёлся
    -- его базовый код (вариант 41324000-B получает категорию 41324000; неоднозначных базовых
    -- кодов в источнике нет, проверено 27.09.2026); manual — поставил человек
    category_source     TEXT        NOT NULL,
    source_sku          TEXT,                       -- какой ключ источника совпал
    effective_from      DATE        NOT NULL DEFAULT current_date,
    effective_to        DATE,
    -- ТЗ §9.1: связь не используется молча — почему уровень категории недоступен, видно строкой
    data_quality_status TEXT,                       -- NULL = связь годная; CATEGORY_MAPPING_CONFLICT
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by          TEXT        NOT NULL DEFAULT 'Kabinet - Coverage Projection',
    CONSTRAINT sku_categories_src_ck CHECK (category_source IN ('amazon', 'amazon:base', 'manual')),
    CONSTRAINT sku_categories_period_ck CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
-- ТЗ §12.6: «для одного SKU на дату расчёта должна быть ровно одна активная категория»
CREATE UNIQUE INDEX IF NOT EXISTS sku_categories_active_uq
    ON kabinet_data.sku_categories (sku) WHERE effective_to IS NULL;
CREATE INDEX IF NOT EXISTS sku_categories_cat_ix ON kabinet_data.sku_categories (category);

-- ─────────────────────────────────────────────────────────── нормативы (ТЗ §9)
CREATE TABLE IF NOT EXISTS kabinet_data.coverage_norm_rules (
    -- id и есть «идентификатор версии» из §9.2: воспроизводимый признак, который уезжает
    -- в снимок покрытия (coverage_summary.norm_rule_id) и позволяет сказать, по какой
    -- версии норматива был посчитан тот расчёт
    id              SERIAL      PRIMARY KEY,
    level           TEXT        NOT NULL,           -- sku | category | default
    sku             TEXT,
    category        TEXT,
    marketplace_id  INTEGER     REFERENCES kabinet_data.marketplaces_new(id),
    pool_id         INTEGER     REFERENCES kabinet_data.pools(id),
    min_days        INTEGER     NOT NULL,
    target_days     INTEGER     NOT NULL,
    max_days        INTEGER     NOT NULL,
    effective_from  DATE        NOT NULL DEFAULT current_date,
    effective_to    DATE,
    note            TEXT,
    updated_by      TEXT        NOT NULL DEFAULT 'kabinet-app',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- уровень и заполненность полей — одно и то же утверждение, записанное дважды;
    -- без этой проверки «норматив категории» с пустой категорией выглядел бы как правило
    -- по умолчанию и тихо применялся бы ко всему рынку
    CONSTRAINT cnr_level_ck CHECK (
        (level = 'sku'      AND sku IS NOT NULL AND category IS NULL) OR
        (level = 'category' AND category IS NOT NULL AND sku IS NULL) OR
        (level = 'default'  AND sku IS NULL AND category IS NULL)),
    -- связка ТЗ §9.1 — «страна + маркетплейс» или «страна + пул»; страна не хранится, потому
    -- что и маркетплейс, и пул её однозначно задают (пул по ТЗ 004 одностранный)
    CONSTRAINT cnr_target_ck CHECK ((marketplace_id IS NULL) <> (pool_id IS NULL)),
    CONSTRAINT cnr_days_ck   CHECK (0 <= min_days AND min_days <= target_days AND target_days <= max_days),
    CONSTRAINT cnr_period_ck CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

-- ТЗ §9.2: «периоды одной настройки не должны пересекаться». Проверкой в коде это не
-- закрывается — правило можно вставить и запросом, — поэтому запрет стоит в базе. Хотелось
-- EXCLUDE USING gist, но btree_gist роль Кабинета создать не может («Must have CREATE
-- privilege on current database»), а без него equality по int и text в gist-индекс не влезает.
-- Значит триггер: он на порядок понятнее в сообщении об ошибке и работает без расширения.
-- Слабое место триггера — одновременная вставка двух пересекающихся периодов в разных
-- транзакциях; при одном приложении и одном аналитике это не тот риск, за который стоит
-- платить просьбой к владельцу базы поставить расширение.
CREATE OR REPLACE FUNCTION kabinet_data.coverage_norm_no_overlap()
RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    conflict_id INTEGER;
BEGIN
    -- проверку периода делаем здесь, хотя она же стоит CHECK'ом: BEFORE-триггер срабатывает
    -- раньше ограничений, и на перевёрнутых датах daterange() падал сообщением
    -- «range lower bound must be less than or equal to range upper bound» — про диапазон,
    -- а не про норматив. CHECK остаётся как запрет для запросов, которые триггер обойдут
    IF NEW.effective_to IS NOT NULL AND NEW.effective_to < NEW.effective_from THEN
        RAISE EXCEPTION 'дата окончания норматива (%) раньше даты вступления в силу (%)',
            NEW.effective_to, NEW.effective_from USING ERRCODE = 'check_violation';
    END IF;

    SELECT r.id INTO conflict_id
    FROM kabinet_data.coverage_norm_rules r
    WHERE r.id <> COALESCE(NEW.id, -1)
      AND r.level = NEW.level
      AND COALESCE(r.sku, '') = COALESCE(NEW.sku, '')
      AND COALESCE(r.category, '') = COALESCE(NEW.category, '')
      AND COALESCE(r.marketplace_id, -1) = COALESCE(NEW.marketplace_id, -1)
      AND COALESCE(r.pool_id, -1) = COALESCE(NEW.pool_id, -1)
      AND daterange(r.effective_from, r.effective_to, '[]')
          && daterange(NEW.effective_from, NEW.effective_to, '[]')
    LIMIT 1;
    IF conflict_id IS NOT NULL THEN
        RAISE EXCEPTION 'период норматива пересекается с правилом #% по той же связке', conflict_id
            USING ERRCODE = 'exclusion_violation';
    END IF;
    RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS coverage_norm_no_overlap_t ON kabinet_data.coverage_norm_rules;
CREATE TRIGGER coverage_norm_no_overlap_t
    BEFORE INSERT OR UPDATE ON kabinet_data.coverage_norm_rules
    FOR EACH ROW EXECUTE FUNCTION kabinet_data.coverage_norm_no_overlap();

CREATE INDEX IF NOT EXISTS cnr_lookup_ix
    ON kabinet_data.coverage_norm_rules (level, sku, category, marketplace_id, pool_id, effective_from);

-- Журнал: как у остальных справочников — что было, что стало, кто и когда.
CREATE TABLE IF NOT EXISTS kabinet_data.coverage_norm_log (
    id         BIGSERIAL   PRIMARY KEY,
    rule_id    INTEGER,
    action     TEXT        NOT NULL,        -- created | updated | closed
    before_state JSONB,
    after_state  JSONB,
    actor      TEXT        NOT NULL DEFAULT 'kabinet-app',
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note       TEXT
);
CREATE INDEX IF NOT EXISTS coverage_norm_log_rule_ix ON kabinet_data.coverage_norm_log (rule_id, changed_at DESC);

-- ─────────────────────────────────────────────────────────── разрешение норматива (ТЗ §9.1)
-- Одна реализация приоритета на страницу и на загрузчик: если написать её дважды, экран и
-- расчёт разойдутся, и расхождение не будет видно ниоткуда.
--
-- Приоритет (более специфичное выше общего): SKU+маркетплейс → SKU+пул → категория+маркетплейс
-- → категория+пул → по умолчанию+маркетплейс → по умолчанию+пул. Нет ни одного — строк нет,
-- и это состояние «Норматив не настроен», а не «ноль дней».
CREATE OR REPLACE FUNCTION kabinet_data.coverage_norm_resolve(
        p_sku TEXT, p_marketplace_id INTEGER, p_pool_id INTEGER, p_on DATE DEFAULT current_date)
RETURNS TABLE (rule_id INTEGER, level TEXT, min_days INTEGER, target_days INTEGER,
               max_days INTEGER, category TEXT, quality TEXT)
LANGUAGE sql STABLE AS $$
    WITH cat AS (
        SELECT c.category, c.data_quality_status
        FROM kabinet_data.sku_categories c
        WHERE c.sku = p_sku
          AND c.effective_from <= p_on
          AND (c.effective_to IS NULL OR c.effective_to >= p_on)
          AND c.data_quality_status IS NULL     -- ТЗ §9.1: спорная связь уровень категории не даёт
        LIMIT 1
    )
    SELECT r.id, r.level, r.min_days, r.target_days, r.max_days,
           (SELECT category FROM cat),
           CASE WHEN (SELECT category FROM cat) IS NULL THEN 'CATEGORY_MAPPING_MISSING' END
    FROM kabinet_data.coverage_norm_rules r
    WHERE r.effective_from <= p_on
      AND (r.effective_to IS NULL OR r.effective_to >= p_on)
      AND ((r.marketplace_id IS NOT NULL AND r.marketplace_id = p_marketplace_id)
           OR (r.pool_id IS NOT NULL AND r.pool_id = p_pool_id))
      AND (   (r.level = 'sku'      AND r.sku = p_sku)
           OR (r.level = 'category' AND r.category = (SELECT category FROM cat))
           OR  r.level = 'default')
    ORDER BY CASE r.level WHEN 'sku' THEN 0 WHEN 'category' THEN 2 ELSE 4 END
             + CASE WHEN r.marketplace_id IS NOT NULL THEN 0 ELSE 1 END,
             r.effective_from DESC
    LIMIT 1;
$$;

-- ─────────────────────────────────────────────────────────── статус относительно норматива (ТЗ §9.3)
-- Держим в базе, чтобы «ниже минимума / норма / выше максимума» считалось одним способом
-- и у загрузчика, и на экране, и в любом разовом запросе.
CREATE OR REPLACE FUNCTION kabinet_data.coverage_norm_status(
        p_coverage_days NUMERIC, p_min INTEGER, p_max INTEGER)
RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_min IS NULL OR p_max IS NULL THEN 'no_norm'
        WHEN p_coverage_days IS NULL        THEN NULL
        WHEN p_coverage_days < p_min        THEN 'below'
        WHEN p_coverage_days > p_max        THEN 'above'
        ELSE 'norm' END;
$$;

GRANT SELECT ON kabinet_data.sku_categories, kabinet_data.coverage_norm_rules,
                kabinet_data.coverage_norm_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT INSERT, UPDATE ON kabinet_data.coverage_norm_rules, kabinet_data.coverage_norm_log
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.coverage_norm_rules_id_seq,
                                kabinet_data.coverage_norm_log_id_seq
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.sku_categories, kabinet_data.coverage_norm_rules
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
