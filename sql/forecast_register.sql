-- 17.09.2026. Реестр прогнозов продаж по ТЗ 010 v0.2 и регистр зависимой потребности по ТЗ 011 v0.2.
-- Первый релиз хранилища: документы, помесячные записи с версиями и статусами, история замен,
-- журнал изменений. Алгоритмы расчёта прогноза (ТЗ 010 §14) и UI документа — вне этого файла.
--
-- Решения хранения (ТЗ оставляет их программисту):
--   • месяц — DATE первого числа; объект — (object_type, object_id): marketplace → marketplaces_new.id, pool → pools.id;
--   • состав пула фиксируется в документе как jsonb-массив id marketplace (ТЗ 010 §5 «Дата среза пула»);
--   • действующая запись — is_current = TRUE; для «Прогноз продаж» она одна на (объект, SKU, месяц) — частичный уникальный индекс;
--   • зависимая потребность лежит в том же реестре с record_type = 'dependent' и полями ТЗ 011 §5; логический ключ ТЗ 011 §6 —
--     (object_type, object_id, month, sku, composite_sku, source_forecast_id);
--   • ссылки «Заменено документом» / «Изменяет» — массивы id, потому что при разделении пула заменителей несколько (ТЗ 010 §10).

CREATE TABLE IF NOT EXISTS kabinet_data.forecast_documents (
    id            SERIAL PRIMARY KEY,
    number        TEXT UNIQUE,                                   -- формируется системой
    doc_date      DATE NOT NULL DEFAULT current_date,
    object_type   TEXT NOT NULL CHECK (object_type IN ('marketplace', 'pool')),
    object_id     INT  NOT NULL,
    pool_snapshot JSONB,                                          -- для пула: [marketplace_id, …] на дату создания
    pool_snapshot_date DATE,
    first_month   DATE NOT NULL CHECK (first_month = date_trunc('month', first_month)),
    last_month    DATE NOT NULL CHECK (last_month = date_trunc('month', last_month) AND last_month >= first_month
                                       AND last_month < first_month + INTERVAL '13 months'),
    completeness  TEXT NOT NULL DEFAULT 'partial' CHECK (completeness IN ('full', 'partial')),
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted')),
    comment       TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',                 -- manual | import:quantity_manager | import:xlsx | …
    created_by    TEXT NOT NULL DEFAULT current_user,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    posted_by     TEXT,
    posted_at     TIMESTAMPTZ,
    replacement_op_id TEXT                                        -- общая замена после изменения пула (сценарий 21)
);
COMMENT ON TABLE kabinet_data.forecast_documents IS 'ТЗ 010 §5: документ «Прогноз продаж marketplace / пула». Проведённый документ неизменяем; изменение — новым документом.';

CREATE TABLE IF NOT EXISTS kabinet_data.forecast_register (
    id              BIGSERIAL PRIMARY KEY,
    record_type     TEXT NOT NULL CHECK (record_type IN ('sales', 'dependent')),
    object_type     TEXT NOT NULL CHECK (object_type IN ('marketplace', 'pool')),
    object_id       INT  NOT NULL,
    sku             TEXT NOT NULL,
    month           DATE NOT NULL CHECK (month = date_trunc('month', month)),
    quantity        INT  CHECK (quantity IS NULL OR quantity >= 0),   -- NULL в черновике = не заполнено; 0 = продаж не планируем
    version         INT  NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'unapproved' CHECK (status IN ('unapproved', 'approved', 'superseded')),
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,               -- действующая запись: approved + документ posted + не заменена
    document_id     INT NOT NULL REFERENCES kabinet_data.forecast_documents(id),
    target_price    NUMERIC(12,2),
    forecast_revenue NUMERIC(14,2) GENERATED ALWAYS AS (quantity * target_price) STORED,
    line_comment    TEXT,
    cogs_calc       NUMERIC(12,2),                                -- ТЗ 010 §20: до отдельного алгоритма NULL = NOT_CALCULATED
    margin_calc     NUMERIC(14,2),
    margin_pct      NUMERIC(8,4),
    acos_pct        NUMERIC(8,4),
    -- зависимая потребность (ТЗ 011 §5)
    composite_sku       TEXT,
    component_qty       INT,
    source_forecast_id  BIGINT REFERENCES kabinet_data.forecast_register(id),
    forecast_quantity   INT,
    calculation_status  TEXT CHECK (calculation_status IN ('CALCULATED', 'ERROR', 'SUPERSEDED')),
    calculation_version TEXT,
    source_snapshot_id  TEXT,
    error_code          TEXT,
    error_text          TEXT,
    calculated_at       TIMESTAMPTZ,
    -- история замен (ТЗ 010 §10)
    replaced_by     BIGINT[] NOT NULL DEFAULT '{}',
    replaces        BIGINT[] NOT NULL DEFAULT '{}',
    changed_at      TIMESTAMPTZ,                                  -- дата проведения документа, которым изменён прогноз
    created_by      TEXT NOT NULL DEFAULT current_user,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    unapproved_by   TEXT,
    unapproved_at   TIMESTAMPTZ,
    superseded_at   TIMESTAMPTZ,
    CHECK (record_type = 'sales' OR (composite_sku IS NOT NULL AND source_forecast_id IS NOT NULL))
);
-- ТЗ 010 §10: для одной комбинации объекта, SKU и месяца действует только одна версия прогноза продаж
CREATE UNIQUE INDEX IF NOT EXISTS forecast_register_current_sales_uq
    ON kabinet_data.forecast_register (object_type, object_id, sku, month) WHERE is_current AND record_type = 'sales';
-- ТЗ 011 §6: логический ключ результата зависимой потребности; действующий — один
CREATE UNIQUE INDEX IF NOT EXISTS forecast_register_current_dependent_uq
    ON kabinet_data.forecast_register (object_type, object_id, month, sku, composite_sku, source_forecast_id) WHERE is_current AND record_type = 'dependent';
CREATE INDEX IF NOT EXISTS forecast_register_doc_idx ON kabinet_data.forecast_register (document_id);
CREATE INDEX IF NOT EXISTS forecast_register_sku_month_idx ON kabinet_data.forecast_register (sku, month) WHERE is_current;
COMMENT ON TABLE kabinet_data.forecast_register IS 'ТЗ 010 §10 + ТЗ 011 §5: помесячные записи прогноза продаж и зависимой потребности с версиями, статусами и историей замен.';

CREATE TABLE IF NOT EXISTS kabinet_data.forecast_change_log (
    id          BIGSERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES kabinet_data.forecast_documents(id),
    sku         TEXT,
    month       DATE,
    field       TEXT NOT NULL DEFAULT 'quantity',                 -- quantity | target_price | approval | …
    old_value   TEXT,
    new_value   TEXT,
    source      TEXT NOT NULL,                                    -- manual | import:quantity_manager | import:xlsx | approve | unapprove | post | replace
    actor       TEXT NOT NULL DEFAULT current_user,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.forecast_change_log IS 'ТЗ 010 §10/§11.5: история ручных изменений и загрузок — дата, пользователь, SKU, месяц, было/стало, источник.';

-- Действующий прогноз продаж — то, что читают отчёт «Факт / прогноз», контроль покрытия и алерты
CREATE OR REPLACE VIEW kabinet_data.v_forecast_current AS
SELECT r.id, r.object_type, r.object_id,
       CASE WHEN r.object_type = 'marketplace' THEN m.code ELSE p.name END AS object_name,
       r.sku, r.month, r.quantity, r.target_price, r.forecast_revenue, r.document_id, d.pool_snapshot, d.posted_at
FROM kabinet_data.forecast_register r
JOIN kabinet_data.forecast_documents d ON d.id = r.document_id
LEFT JOIN kabinet_data.marketplaces_new m ON r.object_type = 'marketplace' AND m.id = r.object_id
LEFT JOIN kabinet_data.pools p ON r.object_type = 'pool' AND p.id = r.object_id
WHERE r.record_type = 'sales' AND r.is_current;

GRANT SELECT ON kabinet_data.forecast_documents, kabinet_data.forecast_register, kabinet_data.forecast_change_log, kabinet_data.v_forecast_current TO claude_code_ro;
GRANT SELECT, INSERT, UPDATE ON kabinet_data.forecast_documents, kabinet_data.forecast_register, kabinet_data.forecast_change_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE ON SEQUENCE kabinet_data.forecast_documents_id_seq, kabinet_data.forecast_register_id_seq, kabinet_data.forecast_change_log_id_seq TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
