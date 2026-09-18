-- 18.09.2026: справочник «SKU» по ТЗ 005 v0.1 и регистр состава (§7).
-- Мастер кодов — Odoo (raw_odoo_sku_mapping), подтверждение у Дарины 18.09; ERP — имена и вес брутто;
-- Amazon — EAN и габариты упаковки; листинги восьми рынков и офферы Mirakl — периметр.
-- Каждое автозаполняемое поле несёт источник: 'manual' загрузчик не перезаписывает никогда.

CREATE TABLE IF NOT EXISTS kabinet_data.sku_master (
    sku               text PRIMARY KEY,                        -- внутренний код/артикул (ТЗ §3)
    sku_type          text CHECK (sku_type IN ('base', 'composite')),  -- NULL = не определён, контроль подсветит
    type_source       text,
    name              text,
    name_source       text,
    supplier_code     text,                                    -- оригинальный код поставщика — только руками / 1С
    ean               text,
    ean_source        text,
    intro_date        date,                                    -- дата ввода (§5.1); estimate:* — оценка по листингу/продаже
    intro_source      text,
    exit_date         date,                                    -- дата вывода (§5.2)
    exit_source       text,
    restrictions      jsonb NOT NULL DEFAULT '[]'::jsonb,      -- §6: коды marketplace и/или стран, где применение запрещено
    height_mm         int,
    width_mm          int,
    length_mm         int,
    dims_source       text,
    volume_m3         numeric(12,6),                           -- §4: расчёт, для составного — сумма по составу
    gross_weight_kg   numeric(10,3),
    weight_source     text,
    passport_ref      text,                                    -- §8: ссылка на Паспорт SKU, 0..1
    erp_uid           text,
    odoo_type         text,                                    -- consu / product / service из Odoo
    in_scope          text[] NOT NULL DEFAULT '{}',            -- почему SKU в периметре: amazon, mm, lm, cf, component, sales
    is_active         boolean NOT NULL DEFAULT true,
    note              text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    updated_by        text
);
COMMENT ON TABLE kabinet_data.sku_master IS 'ТЗ 005 «Справочник SKU»: базовые и составные SKU компании. Поля *_source: manual не перезаписывается загрузчиком.';

-- Состав составного SKU (§7): неизменяем; изменение состава = новый SKU. Источник — Odoo BOM.
CREATE TABLE IF NOT EXISTS kabinet_data.sku_composition (
    composite_sku  text NOT NULL REFERENCES kabinet_data.sku_master(sku),
    base_sku       text NOT NULL REFERENCES kabinet_data.sku_master(sku),
    quantity       int  NOT NULL CHECK (quantity > 0),
    source         text NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (composite_sku, base_sku),
    CHECK (composite_sku <> base_sku)
);

-- Результаты контроля заполнения (§10, §7.6): пересчитываются загрузчиком целиком; экран красит по ним.
CREATE TABLE IF NOT EXISTS kabinet_data.sku_checks (
    sku         text NOT NULL,
    check_code  text NOT NULL,      -- no_type, no_intro_date, intro_estimate, no_dims, no_weight, composition_missing,
                                    -- composition_lt2, composition_nested, composition_base_missing, exit_candidate
    severity    text NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    detail      text,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sku, check_code)
);

-- История изменений идентификаторов и дат (§12): пишет и экран, и загрузчик.
CREATE TABLE IF NOT EXISTS kabinet_data.sku_change_log (
    id         bigserial PRIMARY KEY,
    sku        text NOT NULL,
    field      text NOT NULL,
    old_value  text,
    new_value  text,
    source     text NOT NULL,
    actor      text,
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sku_change_log_sku ON kabinet_data.sku_change_log (sku);

GRANT SELECT ON kabinet_data.sku_master, kabinet_data.sku_composition, kabinet_data.sku_checks, kabinet_data.sku_change_log TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_master, kabinet_data.sku_composition, kabinet_data.sku_checks, kabinet_data.sku_change_log
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.sku_change_log_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Правило здоровья загрузчика (06:00 Kyiv ежедневно).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (909831072825007, 'Kabinet - SKU Master Loader', 30, '06:00 Kyiv daily', 'справочник SKU по ТЗ 005 из Odoo/ERP/Amazon')
ON CONFLICT DO NOTHING;
