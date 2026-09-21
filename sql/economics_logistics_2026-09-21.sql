-- 21.09.2026. Упаковка и доставка в марже Кабинета — как в витрине Дарины (v_amazon_spiderweb_report и соседние):
--   упаковка — фиксированно за проданную единицу (1,5 €), доставка — по весу SKU из тарифной сетки
--   dnipro_m.raw_delivery_costs (страна ES / Other, диапазоны кг, дата действия), вес = сумма весов состава
--   (raw_weight_child_sku по BOM Odoo/каталога); у Amazon доставка только на единицы FBM (у FBA — сбор FBA
--   внутри фактических комиссий), у Mirakl — на все; нет веса → дефолт 3,71 € Amazon / 5,71 € Mirakl.
-- economics_summary принадлежит владельцу и от rw не расширяется — статьи лежат отдельной таблицей с тем же ключом.
CREATE TABLE IF NOT EXISTS kabinet_data.economics_logistics (
    sales_date     DATE NOT NULL,
    marketplace    TEXT NOT NULL,
    norm_sku       TEXT NOT NULL,
    units_ordered  INT,
    mfn_units      INT,                 -- единицы, отгруженные нами (Amazon MFN; у Mirakl = все)
    mfn_source     TEXT,                -- orders | listing | all
    weight_kg      NUMERIC(10,3),       -- вес состава; NULL — нет веса хотя бы у одного компонента
    rate_country   TEXT,                -- ES | Other
    shipping_per_unit NUMERIC(10,2),
    shipping_source TEXT,               -- rate_card | default
    packing_cost   NUMERIC(12,2) NOT NULL DEFAULT 0,
    shipping_cost  NUMERIC(12,2) NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sales_date, marketplace, norm_sku)
);
COMMENT ON TABLE kabinet_data.economics_logistics IS 'Упаковка и доставка по строкам economics_summary (правила Дарины, 21.09.2026); пишет Kabinet - Economics Loader, ячейка 11.';
GRANT SELECT ON kabinet_data.economics_logistics TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.economics_logistics TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.economics_logistics TO "v.tereshyn@dniprom.com";
-- ставки — в базе, не в коде
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('packing_cost_per_unit', '1.5', 'Упаковка, € за проданную единицу, все каналы (правило Дарины, витрина spiderweb)'),
  ('shipping_default_amazon', '3.71', 'Доставка FBM-единицы Amazon, € — когда у SKU нет веса и тариф не найден'),
  ('shipping_default_mirakl', '5.71', 'Доставка единицы Mirakl (LM/MM/CF), € — когда у SKU нет веса и тариф не найден')
ON CONFLICT (key) DO NOTHING;
SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'packing%' OR key LIKE 'shipping%';
