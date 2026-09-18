-- 18.09.2026: справочник «Товарные сущности marketplace (PeID/ASIN)» по ТЗ 008 v0.2.
-- PeID — идентификатор товара на площадке: ASIN у Amazon, model id (id_me) у ManoMano,
-- product_sku у Leroy Merlin и Carrefour. Одна запись — один PeID в одном marketplace.
-- Связь с SKU по ТЗ живёт только в матрице (007); здесь — то, что видно в листингах и офферах
-- (product_entity_listings): исходник для регистра представления и для контроля дублей.
CREATE TABLE IF NOT EXISTS kabinet_data.product_entities (
    id                 serial PRIMARY KEY,
    marketplace_id     int  NOT NULL,                -- → marketplaces_new.id; FK не объявлен: у rw нет REFERENCES на таблицу владельца
    peid               text NOT NULL,
    variation_group_id int,                          -- ТЗ 006: назначается на уровне PeID, FK добавит sql/variation_groups.sql
    title              text,                         -- как называет площадка; информационно
    url                text,
    is_parent          boolean NOT NULL DEFAULT false, -- у Amazon: Parent ASIN — сущность группы, не вариант (ТЗ 006 §4)
    is_active          boolean NOT NULL DEFAULT true,
    active_source      text,                         -- auto: снят, если сущности нет в листингах N дней; manual — руками
    seen_in            text[] NOT NULL DEFAULT '{}', -- merchant_listings, catalog, snapshots, mm_offers, lm_offers, cf_offers
    first_seen         date,
    last_seen          date,
    comment            text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    updated_by         text,
    UNIQUE (marketplace_id, peid)
);
COMMENT ON TABLE kabinet_data.product_entities IS 'ТЗ 008: PeID/ASIN по marketplace. Связь с SKU — в матрице (007), здесь только наблюдаемые листинги.';

-- Наблюдаемые листинги/офферы: под каким seller-SKU и каким SKU справочника PeID выставлен.
-- Это факт площадки, не решение; регистр представления матрицы (007) собирается отсюда.
CREATE TABLE IF NOT EXISTS kabinet_data.product_entity_listings (
    marketplace_id   int  NOT NULL,
    peid             text NOT NULL,
    seller_sku       text NOT NULL,
    sku              text,                           -- код справочника SKU после нормализации; NULL — не SKU (контейнер вариаций и т.п.)
    listing_status   text,                           -- Active / Inactive / Incomplete у Amazon; active/online у Mirakl
    fulfillment      text,                           -- AMAZON_EU / DEFAULT (FBM) / NULL
    open_date        date,
    last_report_date date,
    source           text NOT NULL,
    PRIMARY KEY (marketplace_id, peid, seller_sku)
);

CREATE TABLE IF NOT EXISTS kabinet_data.product_entity_checks (
    marketplace_id int  NOT NULL,
    peid           text NOT NULL,
    check_code     text NOT NULL,   -- sku_unknown, multi_sku, no_group, parent_without_children, inactive_listing
    severity       text NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    detail         text,
    checked_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (marketplace_id, peid, check_code)
);

GRANT SELECT ON kabinet_data.product_entities, kabinet_data.product_entity_listings, kabinet_data.product_entity_checks TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.product_entities, kabinet_data.product_entity_listings, kabinet_data.product_entity_checks
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.product_entities_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";


INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (761137342699876, 'Kabinet - Product Entities Loader', 30, '06:15 Kyiv daily', 'ТЗ 008: PeID/ASIN из merchant listings 8 рынков, каталога, снимков и офферов Mirakl')
ON CONFLICT DO NOTHING;
