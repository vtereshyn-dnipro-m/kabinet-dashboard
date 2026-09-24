-- ТЗ 001 v1.0, пробелы 1–6: страны обслуживания, владелец, контроль Long Term, график отгрузки,
-- сопоставления с внешними системами. Таблица kabinet_data.warehouses принадлежит владельцу и от роли
-- claude_code_rw не расширяется — поэтому новые реквизиты лежат рядом, как это уже сделано с приоритетами.

-- 2, 7: владелец (из ERP, только для чтения) и флаг Long Term (ставит человек)
CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_attributes (
    warehouse_id      INT PRIMARY KEY REFERENCES kabinet_data.warehouses(id),
    owner_company     TEXT,                    -- приезжает из Odoo, руками не правится
    owner_source      TEXT,                    -- odoo:stock.warehouse | manual
    owner_synced_at   TIMESTAMPTZ,
    long_term_control BOOLEAN NOT NULL DEFAULT false,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by        TEXT NOT NULL DEFAULT 'kabinet'
);
COMMENT ON COLUMN kabinet_data.warehouse_attributes.owner_company IS 'ТЗ 001 §п.6: владелец физического склада; источник — ERP, в Кабинете только для чтения.';

-- 2: страны обслуживания (одна или несколько), отдельно от страны физического нахождения
CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_countries (
    warehouse_id   INT  NOT NULL REFERENCES kabinet_data.warehouses(id),
    country_alpha2 TEXT NOT NULL,            -- без внешнего ключа: countries принадлежит владельцу,
                                             -- у роли Кабинета на неё только SELECT, REFERENCES не выдан
    added_on       DATE NOT NULL DEFAULT current_date,
    updated_by     TEXT NOT NULL DEFAULT 'kabinet',
    PRIMARY KEY (warehouse_id, country_alpha2)
);
COMMENT ON TABLE kabinet_data.warehouse_countries IS 'ТЗ 001: страны обслуживания склада; страна физического нахождения остаётся в warehouses.country.';

-- 8: график отгрузки «день приёма заказа → день отгрузки»; пусто = ограничения нет
CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_shipping_schedule (
    warehouse_id INT NOT NULL REFERENCES kabinet_data.warehouses(id),
    order_dow    INT NOT NULL CHECK (order_dow BETWEEN 1 AND 7),   -- 1 = понедельник
    ship_dow     INT NOT NULL CHECK (ship_dow BETWEEN 1 AND 7),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT NOT NULL DEFAULT 'kabinet',
    PRIMARY KEY (warehouse_id, order_dow)
);

-- 9: сопоставления с внешними системами
CREATE TABLE IF NOT EXISTS kabinet_data.warehouse_external_ids (
    id            SERIAL PRIMARY KEY,
    warehouse_id  INT  NOT NULL REFERENCES kabinet_data.warehouses(id),
    system_name   TEXT NOT NULL,
    external_code TEXT NOT NULL,
    external_name TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by    TEXT NOT NULL DEFAULT 'kabinet',
    UNIQUE (warehouse_id, system_name, external_code)
);

GRANT SELECT ON kabinet_data.warehouse_attributes, kabinet_data.warehouse_countries,
      kabinet_data.warehouse_shipping_schedule, kabinet_data.warehouse_external_ids
  TO claude_code_ro, "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.warehouse_attributes, kabinet_data.warehouse_countries,
      kabinet_data.warehouse_shipping_schedule, kabinet_data.warehouse_external_ids
  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.warehouse_attributes
  TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";     -- владельца пишет джоба принципала
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.warehouse_external_ids_id_seq
  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

SELECT 'warehouse_attributes' t, count(*) FROM kabinet_data.warehouse_attributes
UNION ALL SELECT 'warehouse_countries', count(*) FROM kabinet_data.warehouse_countries
UNION ALL SELECT 'warehouse_shipping_schedule', count(*) FROM kabinet_data.warehouse_shipping_schedule
UNION ALL SELECT 'warehouse_external_ids', count(*) FROM kabinet_data.warehouse_external_ids;
