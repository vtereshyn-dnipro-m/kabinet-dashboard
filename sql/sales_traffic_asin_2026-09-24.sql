-- Трафик и продажи по ASIN: сейчас в Lakebase их нет вовсе (sales_traffic_daily агрегирована по рынку),
-- а подсказка коммерческой роли (ТЗ 009) без кликов не считается: Traffic — это «много смотрят, мало зарабатываем».
-- Источник тот же, что у дневной витрины, — сырьё Дарины по ASIN × SKU × день; реплику пишет
-- Kabinet - Sales & Traffic Replica тем же прогоном.
CREATE TABLE IF NOT EXISTS kabinet_data.sales_traffic_asin (
    snapshot_date DATE NOT NULL,
    marketplace   TEXT NOT NULL,          -- код страны, как в economics_summary
    asin          TEXT NOT NULL,
    sku           TEXT,                   -- seller SKU из отчёта, как есть
    sessions      INT,
    page_views    INT,
    units_ordered INT,
    ordered_sales NUMERIC(12,2),
    buy_box_pct   NUMERIC(5,2),
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_date, marketplace, asin)
);
CREATE INDEX IF NOT EXISTS sales_traffic_asin_asin_idx ON kabinet_data.sales_traffic_asin (marketplace, asin, snapshot_date DESC);
COMMENT ON TABLE kabinet_data.sales_traffic_asin IS 'Sales & Traffic по ASIN × день из сырья Дарины; нужна для подсказок коммерческих ролей (ТЗ 009).';

GRANT SELECT ON kabinet_data.sales_traffic_asin TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sales_traffic_asin TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
SELECT count(*) FROM kabinet_data.sales_traffic_asin;
