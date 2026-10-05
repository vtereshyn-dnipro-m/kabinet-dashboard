-- Возвраты в Мадрид через локацию брака DEF/WH-1 (решение владельца 06.10.2026):
-- себестоимость возвращается в маржу, если возврат попал в годный запас — напрямую (WH-1) или с DEF после проверки,
-- и если с DEF его продали польскому юрлицу DNIPRO-M STORES Sp. z o.o. (не потеря); пока лежит на DEF — не возвращается.
-- Судьба каждого возврата, принятого в DEF, считается в Kabinet - Odoo Customer Returns (ячейка 2) по строкам движений
-- DEF (stock.move.line — физическое перемещение; шапка stock.move показывает другие локации и давала «2 % в годный»).
-- Сопоставление «какой экземпляр ушёл» — FIFO по товару: самое раннее поступление в DEF уходит первым. Это оценка,
-- а не факт по экземпляру: серийного учёта у этих товаров в Odoo нет.
CREATE TABLE IF NOT EXISTS kabinet_data.odoo_return_def_outcomes (
    return_move_id        bigint PRIMARY KEY,      -- stock.move возврата (как move_id в raw_odoo_customer_returns)
    product_code          text,
    qty_in                numeric(12,3) NOT NULL,  -- сколько этого возврата пришло в DEF
    qty_to_good           numeric(12,3) NOT NULL DEFAULT 0,  -- ушло с DEF в годный запас WH-1
    qty_sold_intercompany numeric(12,3) NOT NULL DEFAULT 0,  -- продано с DEF польскому юрлицу
    qty_other_out         numeric(12,3) NOT NULL DEFAULT 0,  -- ушло иначе (транзит, VWH, магазины) — не возвращается
    qty_in_def            numeric(12,3) NOT NULL DEFAULT 0,  -- всё ещё на DEF
    last_out_date         date,
    calc_at               timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.odoo_return_def_outcomes TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.odoo_return_def_outcomes TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Вью кредита себестоимости: третья ветка — возвраты, принятые на DEF и ушедшие с него в годный запас или проданные
-- польскому юрлицу (`odoo_def`). Дата — дата САМОГО возврата, как у FBA и прямой приёмки: месяц продажи/возврата
-- должен видеть свою себестоимость. Цена этого — прошлый месяц может ещё подрасти, пока DEF разбирает остаток.
CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
WITH fba AS (
    SELECT r.return_date, r.marketplace, kabinet_data.sku_cogs_key(r.sku) AS norm_sku, r.quantity::numeric AS qty,
           'fba'::text AS source
    FROM kabinet_data.raw_amazon_returns r
    WHERE r.fulfillment_type = 'FBA' AND upper(r.disposition) = 'SELLABLE'
),
odoo AS (
    SELECT o.move_date::date AS return_date, o.product_code,
           CASE WHEN o.dest_location LIKE 'WH-1/%' THEN o.quantity
                ELSE COALESCE(d.qty_to_good, 0) + COALESCE(d.qty_sold_intercompany, 0) END AS qty,
           CASE WHEN o.dest_location LIKE 'WH-1/%' THEN 'odoo_madrid' ELSE 'odoo_def' END AS source,
           btrim(coalesce(o.client_order_ref, o.sale_origin)) AS ref
    FROM kabinet_data.raw_odoo_customer_returns o
    LEFT JOIN kabinet_data.odoo_return_def_outcomes d ON d.return_move_id = o.move_id
    WHERE (o.dest_location LIKE 'WH-1/%' OR o.dest_location LIKE 'DEF/WH-1%')
      AND o.product_code IS NOT NULL AND o.quantity > 0
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
           kabinet_data.sku_cogs_key(o.product_code) AS norm_sku, o.qty, o.source
    FROM odoo o
    LEFT JOIN amz_mk a ON a.order_id = regexp_replace(o.ref, '^FBM', '')
    LEFT JOIN mm_mk m ON m.order_ref = o.ref
    WHERE o.qty > 0
),
allr AS (
    SELECT return_date, marketplace, norm_sku, qty, source FROM fba
    UNION ALL
    SELECT return_date, marketplace, norm_sku, qty, source FROM madrid WHERE marketplace IS NOT NULL
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

-- Паспорт «Обзора», строка «Возвраты»: правило с 06.10.2026.
UPDATE kabinet_data.data_source_origins
SET platform_source = 'Amazon: отчёт возвратов FBA (состояние товара SELLABLE / брак); Odoo: приёмка возврата покупателя на склад Мадрид (WH-1 — годный запас, DEF/WH-1 — брак до проверки, W-SPR — ремонт) и дальнейшие движения со склада брака',
    our_refresh = 'Kabinet - Returns Loader 06:00 и Kabinet - Odoo Customer Returns 08:15 Kyiv',
    note = 'Себестоимость возвращается в маржу, если возврат годен: FBA — по оценке Amazon; Мадрид — если Odoo принял товар в годный запас сразу или после проверки на складе брака DEF, либо его продали с DEF польскому юрлицу DNIPRO-M STORES Sp. z o.o. Пока товар лежит на DEF — не возвращается (прошлый месяц может ещё подрасти). Какой экземпляр ушёл с DEF, Odoo не знает — сопоставление по товару, ранние поступления уходят первыми. Сентябрь 2026: 40 шт на 1 029 €.',
    darina_reason = 'у неё в маржу возвращается себестоимость любого возврата, у нас — только годного по факту (Amazon или Odoo, включая проверку на складе брака); сентябрь — 1 718 € у неё против 1 029 € у нас',
    updated_at = now()
WHERE table_name = 'kabinet_data.v_returns_cogs_credit';
