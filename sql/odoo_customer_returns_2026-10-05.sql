-- Возвраты покупателей из Odoo (05.10.2026): реплика сырья dnipro_m.raw_odoo_customer_returns в Lakebase.
-- Строка = проведённое движение stock.move ИЗ локации покупателя (usage = customer) куда угодно — как есть:
-- куда принят товар, накладная, заказ Odoo, номер заказа площадки, команда продаж. Что годно, а что брак,
-- и какой это канал, решает вью v_returns_cogs_credit, а не загрузчик: сырьё не подгоняется под одного читателя.
-- Пишет джоба «Kabinet - Odoo Customer Returns» под владельцем.
CREATE TABLE IF NOT EXISTS kabinet_data.raw_odoo_customer_returns (
    move_id          bigint PRIMARY KEY,
    move_date        timestamp NOT NULL,
    product_code     text,
    product_name     text,
    quantity         numeric(12,3),
    dest_location    text,
    picking          text,
    sale_order       text,
    client_order_ref text,
    sales_team       text,
    loaded_at        timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE kabinet_data.raw_odoo_customer_returns
    ADD COLUMN IF NOT EXISTS company         text,
    ADD COLUMN IF NOT EXISTS source_location text,
    ADD COLUMN IF NOT EXISTS picking_type    text,
    ADD COLUMN IF NOT EXISTS sale_origin     text;
ALTER TABLE kabinet_data.raw_odoo_customer_returns DROP COLUMN IF EXISTS dest_usage;
CREATE INDEX IF NOT EXISTS raw_odoo_customer_returns_date ON kabinet_data.raw_odoo_customer_returns (move_date);
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.raw_odoo_customer_returns TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.raw_odoo_customer_returns TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Себестоимость возвратов, вернувшаяся в маржу: две ветки одного правила «годный — возвращается, брак — нет».
--  1) FBA — по состоянию от Amazon (disposition = SELLABLE), как было с 05.10.2026;
--  2) Мадрид (Amazon MFN и Mirakl) — по факту приёмки в Odoo: товар принят в годный запас склада WH-1
--     (WH-1/STOCK и прочие его внутренние локации, не DEF/WH-1 «Defecto» и не W-SPR «ремонт»).
-- Канал узнаём по номеру заказа площадки (client_order_ref, у Mirakl он в origin заказа Odoo) — тем же
-- форматом, что SendCloud; рынок Amazon — по заказу в orders_history (там все такие заказы MFN), ManoMano —
-- по стране заказа. Зеркало FBA в Odoo (AMZ_A/*) и магазины сюда не попадают: первое уже посчитано веткой 1,
-- вторые не маркетплейс. Наборы Odoo принимает обратно КОМПОНЕНТАМИ, поэтому и себестоимость возвращается по
-- компонентам — в сумме это себестоимость набора (она и считается по составу).
CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
WITH fba AS (
    SELECT r.return_date, r.marketplace, kabinet_data.sku_cogs_key(r.sku) AS norm_sku, r.quantity::numeric AS qty
    FROM kabinet_data.raw_amazon_returns r
    WHERE r.fulfillment_type = 'FBA' AND upper(r.disposition) = 'SELLABLE'
),
odoo AS (
    SELECT o.move_date::date AS return_date, o.product_code, o.quantity,
           btrim(coalesce(o.client_order_ref, o.sale_origin)) AS ref
    FROM kabinet_data.raw_odoo_customer_returns o
    WHERE o.dest_location LIKE 'WH-1/%' AND o.product_code IS NOT NULL AND o.quantity > 0
),
amz_mk AS (
    SELECT DISTINCT ON (order_id) order_id, marketplace_code
    FROM kabinet_data.orders_history
    WHERE order_id IN (SELECT regexp_replace(ref, '^FBM', '') FROM odoo)
    ORDER BY order_id, last_updated DESC
),
mm_mk AS (
    SELECT DISTINCT ON (order_ref) order_ref, 'MM_' || upper(country) AS marketplace
    FROM kabinet_data.raw_mm_order_lines
    ORDER BY order_ref, loaded_at DESC
),
madrid AS (
    SELECT o.return_date,
           CASE WHEN o.ref ~ '^(FBM)?\d{3}-\d{7}-\d{7}$' THEN a.marketplace_code
                WHEN o.ref ~ '^M\d{12}$'                 THEN m.marketplace
                WHEN o.ref ~ '^\d{3}-\d+L\d+-[A-Z]$'      THEN 'LM'
                WHEN o.ref ~ '^\d{8}-[A-Z]$'              THEN 'CF_ES' END AS marketplace,
           kabinet_data.sku_cogs_key(o.product_code) AS norm_sku, o.quantity AS qty
    FROM odoo o
    LEFT JOIN amz_mk a ON a.order_id = regexp_replace(o.ref, '^FBM', '')
    LEFT JOIN mm_mk m ON m.order_ref = o.ref
),
allr AS (
    SELECT 'fba' AS source, * FROM fba
    UNION ALL
    SELECT 'odoo_madrid', * FROM madrid WHERE marketplace IS NOT NULL
)
SELECT a.return_date, a.marketplace, a.norm_sku,
       sum(a.qty)::integer AS sellable_units,
       max(c.cogs) AS unit_cogs,
       sum(a.qty * c.cogs) AS cogs_credit,
       a.source
FROM allr a
JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = a.norm_sku
GROUP BY a.return_date, a.marketplace, a.norm_sku, a.source;
GRANT SELECT ON kabinet_data.v_returns_cogs_credit TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- Метка в пульсе без правила — джоба, которую никто не проверяет; имя одно в трёх местах.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (470982562461595, 'Kabinet - Odoo Customer Returns', 30, 'ежедневно 08:15 Kyiv', true,
        'Возвраты покупателей из Odoo (куда принят товар) — для возврата себестоимости годных возвратов в Мадрид')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
