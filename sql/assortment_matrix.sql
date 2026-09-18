-- 18.09.2026: ассортиментная матрица marketplace по ТЗ 007 v0.2 и классификатор коммерческих ролей по ТЗ 009 v0.2.
-- Два регистра: допуск SKU (площадка или marketplace + SKU, история неизменяемыми записями с датами) и
-- представление (какой PeID представляет допущенный SKU; роль — только при группе вариаций у PeID).
-- Стартовый срез собирает загрузчик из действующих листингов (source = seed); ручные решения (source = manual)
-- загрузчик не меняет и не закрывает — только подсвечивает расхождения в контроле.

CREATE TABLE IF NOT EXISTS kabinet_data.commercial_roles (
    code        text PRIMARY KEY CHECK (code IN ('HERO', 'TRAFFIC', 'MARGIN', 'SUPPORT')),
    name        text NOT NULL,
    definition  text NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    sort_order  int NOT NULL
);
INSERT INTO kabinet_data.commercial_roles (code, name, definition, sort_order) VALUES
  ('HERO',    'Hero',    'Ключевой товар, формирующий основное предложение и ценовое восприятие группы.', 1),
  ('TRAFFIC', 'Traffic', 'Товар, используемый для привлечения спроса и трафика.', 2),
  ('MARGIN',  'Margin',  'Товар, ориентированный на вклад в маржу и экономический результат.', 3),
  ('SUPPORT', 'Support', 'Товар, поддерживающий предложение, структуру группы или продажи других SKU.', 4)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS kabinet_data.assortment_admissions (
    id             serial PRIMARY KEY,
    level          text NOT NULL CHECK (level IN ('platform', 'marketplace')),
    platform       text NOT NULL,                          -- platform_short: AMZ, MM, LM, CF
    marketplace_id int,                                    -- только для level = marketplace
    sku            text NOT NULL REFERENCES kabinet_data.sku_master(sku),
    added_on       date NOT NULL,
    removed_on     date,                                   -- NULL — действующая запись
    in_listing     boolean NOT NULL DEFAULT false,         -- самостоятельная продажа
    complementary  boolean NOT NULL DEFAULT false,         -- обеспечение запасом для составных; только базовый SKU
    reason         text,
    source         text NOT NULL,                          -- seed:listing / seed:component / manual
    created_by     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CHECK ((level = 'platform' AND marketplace_id IS NULL) OR (level = 'marketplace' AND marketplace_id IS NOT NULL)),
    CHECK (removed_on IS NULL OR removed_on >= added_on)
);
-- одна действующая запись на уровень + SKU (ТЗ §7)
CREATE UNIQUE INDEX IF NOT EXISTS assortment_admissions_active_uq
    ON kabinet_data.assortment_admissions (level, platform, COALESCE(marketplace_id, 0), sku) WHERE removed_on IS NULL;

CREATE TABLE IF NOT EXISTS kabinet_data.assortment_representations (
    id              serial PRIMARY KEY,
    admission_id    int  NOT NULL REFERENCES kabinet_data.assortment_admissions(id),
    marketplace_id  int  NOT NULL,
    peid            text NOT NULL,
    commercial_role text REFERENCES kabinet_data.commercial_roles(code),   -- только если у PeID есть группа (ТЗ 009 §3)
    role_since      date,
    valid_from      date,
    valid_to        date,                                  -- NULL — действующее представление
    source          text NOT NULL,                         -- seed:listing / manual
    created_by      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
-- один PeID одновременно представляет один SKU в marketplace (ТЗ 007 §5, 008 §5)
CREATE UNIQUE INDEX IF NOT EXISTS assortment_repr_active_peid_uq
    ON kabinet_data.assortment_representations (marketplace_id, peid) WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS kabinet_data.assortment_change_log (
    id          bigserial PRIMARY KEY,
    register    text NOT NULL,       -- admission / representation
    record_id   int  NOT NULL,
    field       text NOT NULL,
    old_value   text,
    new_value   text,
    source      text NOT NULL,
    actor       text,
    changed_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kabinet_data.assortment_checks (
    register    text NOT NULL,
    record_id   int  NOT NULL,
    check_code  text NOT NULL,   -- sku_no_intro, sku_exited, restricted, no_platform_admission, listing_inactive,
                                 -- listing_without_admission, composite_complementary, role_without_group, repr_without_admission
    severity    text NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    detail      text,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (register, record_id, check_code)
);

GRANT SELECT ON kabinet_data.commercial_roles, kabinet_data.assortment_admissions, kabinet_data.assortment_representations,
      kabinet_data.assortment_change_log, kabinet_data.assortment_checks TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.commercial_roles, kabinet_data.assortment_admissions, kabinet_data.assortment_representations,
      kabinet_data.assortment_change_log, kabinet_data.assortment_checks
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.assortment_admissions_id_seq, kabinet_data.assortment_representations_id_seq, kabinet_data.assortment_change_log_id_seq
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (630855251229041, 'Kabinet - Assortment Matrix Loader', 30, '06:30 Kyiv daily', 'ТЗ 007/009: стартовый срез матрицы из листингов и контроль; ручные записи не трогает')
ON CONFLICT DO NOTHING;
