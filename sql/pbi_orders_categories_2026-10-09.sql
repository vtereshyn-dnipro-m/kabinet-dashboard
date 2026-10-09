-- Паритет с Power BI (09.10.2026): заказы и категории — ещё две таблицы его модели, реплики рядом с
-- kabinet_data.pbi_spiderweb_report. Пишет та же джоба Kabinet - Power BI Replica (ячейки 2 и 3).
--   pbi_orders_report    ← dnipro_m.v_all_marketplaces_orders_enriched: строка на заказ. Карточки Power BI:
--                          Orders Count = число строк, Average Order Value = сумма order_total_amount_eur / число строк,
--                          Average Basket Depth = среднее unique_sku_ordered (проверено на августе: 1 401 / 59,06 / 1,02).
--   pbi_sku_categories   ← dnipro_m.v_sku_names_categories: SKU → название и три уровня категорий, как в Power BI.
--                          SKU без кода в дереве ERP получают там название «Need to Name» и категорию «Set».
BEGIN;
CREATE TABLE IF NOT EXISTS kabinet_data.pbi_orders_report (
    order_id                text             NOT NULL,
    source                  text             NOT NULL,   -- amazon / lm / cf / mm / odoo, как в витрине
    purchase_date           date             NOT NULL,
    marketplace             text             NOT NULL,   -- код рынка Кабинета: ES, GB, LM, MM_ES, CF_ES, WP_ES…
    pbi_marketplace         text             NOT NULL,
    pbi_country             text             NOT NULL,
    order_total_amount_eur  double precision,
    items_quantity_ordered  double precision,
    unique_sku_ordered      bigint,
    loaded_at               timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (source, order_id)
);
CREATE INDEX IF NOT EXISTS pbi_orders_report_date ON kabinet_data.pbi_orders_report (purchase_date, marketplace);

CREATE TABLE IF NOT EXISTS kabinet_data.pbi_sku_categories (
    sku                  text PRIMARY KEY,
    name_en              text,
    name_ukr             text,
    category_level1_en   text,
    category_level2_en   text,
    category_level3_en   text,
    category_level1_ukr  text,
    category_level2_ukr  text,
    category_level3_ukr  text,
    loaded_at            timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.pbi_orders_report IS 'Реплика витрины заказов Power BI v_all_marketplaces_orders_enriched (Kabinet - Power BI Replica)';
COMMENT ON TABLE kabinet_data.pbi_sku_categories IS 'Реплика справочника Power BI v_sku_names_categories (Kabinet - Power BI Replica)';

GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.pbi_orders_report, kabinet_data.pbi_sku_categories TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.pbi_orders_report, kabinet_data.pbi_sku_categories TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.pbi_orders_report, kabinet_data.pbi_sku_categories TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
COMMIT;
