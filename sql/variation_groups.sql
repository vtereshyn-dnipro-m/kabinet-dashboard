-- 18.09.2026: справочник «Группы вариаций marketplace» по ТЗ 006 v0.2.
-- Группа существует в контексте одной marketplace; у Amazon ей соответствует Parent ASIN.
-- Связь варианта с группой — на уровне записи PeID (product_entities.variation_group_id, ТЗ 008 §4),
-- одна группа на PeID в marketplace; история смены группы — в product_entity_change_log (ТЗ 008 §11).
CREATE TABLE IF NOT EXISTS kabinet_data.variation_groups (
    id             serial PRIMARY KEY,
    marketplace_id int  NOT NULL,                    -- → marketplaces_new.id (FK не объявлен: у rw нет REFERENCES)
    name           text NOT NULL,                    -- как называет площадка (ТЗ §5), не внутреннее имя
    name_source    text,                             -- parent_listing / child_title / manual
    group_peid     text,                             -- Parent ASIN у Amazon; NULL, если площадка сущность группы не использует
    url            text,
    is_family      boolean NOT NULL DEFAULT true,    -- ТЗ §8: объединение соответствует правилам площадки; у Amazon-родителя — всегда
    is_active      boolean NOT NULL DEFAULT true,
    active_source  text,
    source         text NOT NULL,                    -- amazon_parent / manual
    comment        text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    updated_by     text
);
-- групповой PeID уникален в marketplace (ТЗ §8); одновременно не может совпадать с вариантным — проверяет загрузчик
CREATE UNIQUE INDEX IF NOT EXISTS variation_groups_peid_uq ON kabinet_data.variation_groups (marketplace_id, group_peid) WHERE group_peid IS NOT NULL;

ALTER TABLE kabinet_data.product_entities ADD COLUMN IF NOT EXISTS group_source text;   -- auto / manual
DO $$ BEGIN
  ALTER TABLE kabinet_data.product_entities ADD CONSTRAINT product_entities_group_fk
      FOREIGN KEY (variation_group_id) REFERENCES kabinet_data.variation_groups(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS kabinet_data.product_entity_change_log (
    id         bigserial PRIMARY KEY,
    marketplace_id int NOT NULL,
    peid       text NOT NULL,
    field      text NOT NULL,          -- variation_group_id, is_active, …
    old_value  text,
    new_value  text,
    source     text NOT NULL,
    actor      text,
    changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kabinet_data.variation_group_checks (
    group_id   int  NOT NULL,
    check_code text NOT NULL,          -- single_member, no_name, peid_collision, parent_no_listing
    severity   text NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    detail     text,
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, check_code)
);

GRANT SELECT ON kabinet_data.variation_groups, kabinet_data.product_entity_change_log, kabinet_data.variation_group_checks TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.variation_groups, kabinet_data.product_entity_change_log, kabinet_data.variation_group_checks
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.variation_groups_id_seq, kabinet_data.product_entity_change_log_id_seq
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
