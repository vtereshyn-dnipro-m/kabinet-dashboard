-- Worten в витрине Unity Catalog по форме Amazon (30.10.2026, поручение владельца с согласия аналитика витрины;
-- спецификация exports/spec_worten_tiktok_vitrina_2026-10-30.md, раздел «Worten»). Три новые вью канала. Сводные вью —
-- отдельным файлом sql/worten_vitrina_unions_2026-10-30.sql, после этого. Применяет владелец или агент по прямому
-- «применяй», под учёткой владельца, на SQL-складе. Только добавляет: CREATE VIEW без OR REPLACE — вью с таким именем
-- уже есть, значит, их кто-то завёл, и затирать их нельзя.
--
-- Источник — сырьё Worten API (Mirakl): dnipro_m.worten.raw_orders / raw_order_lines / raw_offers, магазин 18499,
-- канал WRT_PT_ONLINE. Пишет Kabinet - Worten Loader (docs/worten.md).
--   * День заказа — по Лиссабону: created_at в сырье — часы Лиссабона, записанные как UTC, DATE() сразу даёт день.
--   * Деньги — в евро, с НДС (order_tax_mode = TAX_INCLUDED). НДС — готовый tax_amount строки (23 %), а не деление на
--     1,23: пониженные ставки 6 и 13 % на наших товарах не проверены.
--   * Продажа — с отгрузки (решение владельца 30.10.2026): строка в SHIPPING и дальше (SHIPPED, TO_COLLECT, RECEIVED,
--     CLOSED, INCIDENT_*, WAITING_REFUND*, REFUNDED). Не продажа — до приёма заказа и оплаты (STAGING,
--     WAITING_ACCEPTANCE, WAITING_DEBIT, WAITING_DEBIT_PAYMENT) и отменённые (CANCELED, REFUSED); список — WRT_NOT_SALE
--     ниже, один на обе вью. Строка REFUNDED остаётся продажей в дне заказа, её возврат идёт
--     отдельно, в день возврата, как у Amazon (t_spiderweb_refunds). Это отступление от Leroy Merlin / Carrefour /
--     ManoMano: у них REFUNDED — в дне заказа и вне продаж.
--   * Комиссия — факт из API (commission_fee строки, начислен при приёме заказа). commission_vat у Worten 0.
--   * Возвраты — refunds[] строки (raw_json): только refund state = REFUNDED. amount — с НДС, taxes[].amount — НДС
--     возврата, commission_amount — вернувшаяся комиссия, quantity — штуки. Дата — created_date (настоящий UTC) по
--     Лиссабону. Имена полей сверены с возвратами того же Mirakl у Leroy Merlin (kabinet_data.raw_lm_order_lines.raw);
--     у Worten на 30.10.2026 возвратов нет — сверить на первом.
--   * Себестоимость, вес, упаковка 1,5, коэффициент брака 0,9 — как в v_lm_sales_fees_cogs_es. Доставка — по весу из
--     dnipro_m.raw_delivery_costs, тариф country = 'Other' (отправки вне Испании, как у Amazon), запасной — 5,71.

-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
CREATE VIEW dnipro_m.dnipro_m.v_wrt_sales_fees_cogs_pt
COMMENT 'Worten PT (Mirakl, магазин 18499, канал WRT_PT_ONLINE): день × SKU — продажи с отгрузки по дню заказа (Лиссабон), возвраты по дню возврата, себестоимость, доставка, прибыль. Форма v_lm_sales_fees_cogs_es. Источник — dnipro_m.worten.*'
AS
WITH
params AS (
    SELECT 0.9 AS cogs_quality_coef, 'Other' AS delivery_country
),

-- ─── 1. СТРОКИ ЗАКАЗОВ МАГАЗИНА И КАНАЛА, ОЧИСТКА SKU (как в v_lm_sales_fees_cogs_es) ──────────────────────────
lines AS (
    SELECT
        DATE(o.created_at)                                               AS order_date,
        l.order_id,
        l.order_line_id,
        l.order_line_state,
        REGEXP_REPLACE(
            COALESCE(
                NULLIF(REGEXP_EXTRACT(TRIM(l.shop_sku), r'^(.*?)[\s\-]+(?:FBA|FBM)'), ''),
                TRIM(l.shop_sku)
            ),
            r'[-_\s]+$', ''
        )                                                                AS clean_sku_raw,
        f.product_sku,
        l.quantity,
        l.price,
        l.commission_fee,
        l.tax_amount,
        l.raw_json
    FROM dnipro_m.worten.raw_order_lines l
    JOIN dnipro_m.worten.raw_orders o
        ON o.shop_id = l.shop_id AND o.order_id = l.order_id
    LEFT JOIN dnipro_m.worten.raw_offers f
        ON f.shop_id = l.shop_id AND f.offer_id = l.offer_id
    WHERE o.shop_id = '18499'
      AND o.channel_code = 'WRT_PT_ONLINE'
),
lines_clean AS (
    SELECT
        *,
        CASE
            WHEN LENGTH(clean_sku_raw) < 8 THEN LPAD(clean_sku_raw, 8, '0')
            ELSE clean_sku_raw
        END                                                              AS clean_sku_padded
    FROM lines
),
lines_sku AS (
    SELECT
        *,
        -- то же точечное исключение, что в v_lm_sales_fees_cogs_es: в мэппинге и себестоимости SKU записан с пробелом
        CASE WHEN clean_sku_padded = '54623000-2' THEN '54623000 2' ELSE clean_sku_padded END AS clean_sku
    FROM lines_clean
),

-- ─── 2. ПРОДАЖИ — ПО ДНЮ ЗАКАЗА ────────────────────────────────────────────────────────────────────────────────
sales_agg AS (
    SELECT
        order_date                                                       AS date,
        clean_sku,
        MAX(product_sku)                                                 AS product_sku,
        SUM(quantity)                                                    AS units_sold,
        SUM(price)                                                       AS price,
        SUM(tax_amount)                                                  AS tax_amount,
        SUM(commission_fee)                                              AS commission_fee
    FROM lines_sku
    -- WRT_NOT_SALE: до приёма заказа и оплаты — не продажа, продажа с отгрузки (SHIPPING и дальше)
    WHERE order_line_state NOT IN ('STAGING', 'WAITING_ACCEPTANCE', 'WAITING_DEBIT', 'WAITING_DEBIT_PAYMENT', 'CANCELED', 'REFUSED')
    GROUP BY order_date, clean_sku
),

-- ─── 3. ВОЗВРАТЫ — ИЗ refunds[] СТРОКИ, ПО ДНЮ ВОЗВРАТА (Лиссабон) ────────────────────────────────────────────
refund_items AS (
    SELECT
        s.clean_sku,
        s.product_sku,
        r.*
    FROM lines_sku s
    LATERAL VIEW explode(
        from_json(
            get_json_object(s.raw_json, '$.refunds'),
            'array<struct<amount:double, quantity:int, commission_amount:double, state:string,
                          created_date:string, taxes:array<struct<amount:double>>>>'
        )
    ) x AS r
),
refunds_agg AS (
    SELECT
        DATE(from_utc_timestamp(to_timestamp(created_date), 'Europe/Lisbon')) AS date,
        clean_sku,
        MAX(product_sku)                                                 AS product_sku,
        SUM(quantity)                                                    AS quantity_refund,
        SUM(amount)                                                      AS price_refund,
        SUM(aggregate(COALESCE(taxes, array()), CAST(0 AS DOUBLE), (acc, t) -> acc + COALESCE(t.amount, 0)))
                                                                         AS tax_amount_refund,
        SUM(commission_amount)                                           AS commission_fee_refund
    FROM refund_items
    WHERE state = 'REFUNDED'
    GROUP BY 1, clean_sku
),

-- ─── 4. ДЕНЬ × SKU: ПРОДАЖИ И ВОЗВРАТЫ ВМЕСТЕ (возврат может прийтись на день без продаж) ──────────────────────
day_sku AS (
    SELECT
        COALESCE(s.date, r.date)                                         AS date,
        COALESCE(s.clean_sku, r.clean_sku)                               AS clean_sku,
        COALESCE(s.product_sku, r.product_sku)                           AS product_sku,
        COALESCE(s.units_sold, 0)                                        AS units_sold,
        COALESCE(s.price, 0)                                             AS price,
        COALESCE(s.tax_amount, 0)                                        AS tax_amount,
        COALESCE(s.commission_fee, 0)                                    AS commission_fee,
        COALESCE(r.quantity_refund, 0)                                   AS quantity_refund,
        COALESCE(r.price_refund, 0)                                      AS price_refund,
        COALESCE(r.tax_amount_refund, 0)                                 AS tax_amount_refund,
        COALESCE(r.commission_fee_refund, 0)                             AS commission_fee_refund
    FROM sales_agg s
    FULL OUTER JOIN refunds_agg r
        ON r.date = s.date AND r.clean_sku = s.clean_sku
),

-- ─── 5. МЭППИНГ PARENT/CHILD SKU: odoo, запасной — catalog (как в v_lm_sales_fees_cogs_es) ────────────────────
odoo_sku_mapping_clean AS (
    SELECT
        CASE
            WHEN LENGTH(regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')) < 8
            THEN LPAD(regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', ''), 8, '0')
            ELSE regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')
        END AS parent_sku,
        CASE
            WHEN LENGTH(regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')) < 8
            THEN LPAD(regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', ''), 8, '0')
            ELSE regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')
        END AS child_sku,
        quantity
    FROM dnipro_m.raw_odoo_sku_mapping
),
catalog_sku_mapping_clean AS (
    SELECT
        CASE
            WHEN LENGTH(regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')) < 8
            THEN LPAD(regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', ''), 8, '0')
            ELSE regexp_replace(regexp_replace(regexp_replace(parent_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')
        END AS parent_sku,
        CASE
            WHEN LENGTH(regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')) < 8
            THEN LPAD(regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', ''), 8, '0')
            ELSE regexp_replace(regexp_replace(regexp_replace(child_sku, '[_-]+$', ''), '(?i)(FBA|FBM)$', ''), '[_-]+$', '')
        END AS child_sku,
        units AS quantity
    FROM dnipro_m.raw_amazon_sku_catalog
),
sku_mapping_combined AS (
    SELECT parent_sku, child_sku, quantity, 'odoo' AS mapping_source_table
    FROM odoo_sku_mapping_clean
    UNION ALL
    SELECT c.parent_sku, c.child_sku, c.quantity, 'catalog' AS mapping_source_table
    FROM catalog_sku_mapping_clean c
    WHERE NOT EXISTS (SELECT 1 FROM odoo_sku_mapping_clean o WHERE o.parent_sku = c.parent_sku)
),
parent_mapping_status AS (
    SELECT parent_sku, MAX(mapping_source_table) AS mapping_source_table
    FROM sku_mapping_combined
    GROUP BY parent_sku
),

-- ─── 6. СЕБЕСТОИМОСТЬ НА МЕСЯЦ ДНЯ СТРОКИ (порог 2026-05-31 — как в v_lm_sales_fees_cogs_es) ───────────────────
all_cogs_dates AS (
    SELECT DISTINCT date AS cogs_date FROM dnipro_m.raw_amazon_cogs
),
sales_dates AS (
    SELECT DISTINCT
        date AS sale_date,
        CASE WHEN date <= '2026-05-31' THEN DATE('2026-05-01') ELSE DATE_TRUNC('month', date) END AS target_cogs_date
    FROM day_sku
),
sales_to_cogs_date AS (
    SELECT sd.sale_date, sd.target_cogs_date, MAX(cd.cogs_date) AS resolved_cogs_date
    FROM sales_dates sd
    JOIN all_cogs_dates cd ON cd.cogs_date <= sd.target_cogs_date
    GROUP BY sd.sale_date, sd.target_cogs_date
),
child_cogs AS (
    SELECT sku AS child_sku, date AS cogs_date, cogs AS child_cogs
    FROM dnipro_m.raw_amazon_cogs
    WHERE cogs IS NOT NULL
),
parent_cogs_by_date AS (
    SELECT
        cat.parent_sku,
        scd.sale_date,
        CASE WHEN COUNT(cat.child_sku) != COUNT(cc.child_cogs) THEN NULL ELSE SUM(cat.quantity * cc.child_cogs) END AS cogs
    FROM sku_mapping_combined cat
    JOIN sales_to_cogs_date scd ON TRUE
    LEFT JOIN child_cogs cc
        ON cc.child_sku = cat.child_sku AND cc.cogs_date = scd.resolved_cogs_date
    GROUP BY cat.parent_sku, scd.sale_date
),

-- ─── 7. ВЕС И ДОСТАВКА ПО ВЕСУ (тариф params.delivery_country) ────────────────────────────────────────────────
parent_weight_by_parent AS (
    SELECT
        map.parent_sku,
        CASE WHEN COUNT(map.child_sku) != COUNT(w.weight) THEN NULL ELSE SUM(map.quantity * w.weight) END AS total_weight
    FROM sku_mapping_combined map
    LEFT JOIN dnipro_m.raw_weight_child_sku w ON w.child_sku = map.child_sku
    GROUP BY map.parent_sku
),
all_delivery_dates AS (
    SELECT DISTINCT dc.effective_date AS delivery_date
    FROM dnipro_m.raw_delivery_costs dc
    CROSS JOIN params p
    WHERE dc.country = p.delivery_country
),
sales_to_delivery_date AS (
    SELECT
        sd.sale_date,
        sd.target_cogs_date,
        COALESCE(MAX(CASE WHEN dd.delivery_date <= sd.target_cogs_date THEN dd.delivery_date END), MIN(dd.delivery_date))
                                                                         AS resolved_delivery_date
    FROM sales_dates sd
    CROSS JOIN all_delivery_dates dd
    GROUP BY sd.sale_date, sd.target_cogs_date
),
parent_shipping_cost_by_date AS (
    SELECT pw.parent_sku, std.sale_date, dc.cost AS shipping_cost
    FROM parent_weight_by_parent pw
    JOIN sales_to_delivery_date std ON TRUE
    CROSS JOIN params p
    LEFT JOIN dnipro_m.raw_delivery_costs dc
        ON dc.country = p.delivery_country
        AND dc.effective_date = std.resolved_delivery_date
        AND pw.total_weight >= dc.min_weight
        AND pw.total_weight <  dc.max_weight
    WHERE pw.total_weight IS NOT NULL
),

-- ─── 8. BASE CALCULATIONS ───────────────────────────────────────────────────────────────────────────────────────
base_calculations AS (
    SELECT
        s.date,
        s.clean_sku,
        s.product_sku,
        s.units_sold,
        s.price,
        s.tax_amount,
        s.commission_fee,
        (s.price - s.tax_amount)                                         AS price_vat_excl,
        s.quantity_refund,
        s.price_refund,
        s.tax_amount_refund,
        (s.price_refund - s.tax_amount_refund)                           AS price_refund_vat_excl,
        s.commission_fee_refund,
        c.cogs                                                           AS cogs_per_unit,
        pr.cogs_quality_coef                                             AS cogs_quality_coef,
        CASE
            WHEN ms.mapping_source_table = 'odoo'    THEN 'found_odoo'
            WHEN ms.mapping_source_table = 'catalog' THEN 'not_found_odoo_found_catalog'
            ELSE 'not_found'
        END                                                              AS mapping_source,
        1.5                                                              AS packing_cost_per_unit,
        COALESCE(sc.shipping_cost, 5.71)                                 AS shipping_cost_per_unit,
        CASE WHEN sc.shipping_cost IS NOT NULL THEN 'weight_based' ELSE 'static_default' END AS shipping_cost_source
    FROM day_sku s
    CROSS JOIN params pr
    LEFT JOIN parent_cogs_by_date c
        ON c.parent_sku = s.clean_sku AND c.sale_date = s.date
    LEFT JOIN parent_mapping_status ms
        ON ms.parent_sku = s.clean_sku
    LEFT JOIN parent_shipping_cost_by_date sc
        ON sc.parent_sku = s.clean_sku AND sc.sale_date = s.date
),

-- ─── 9. ФИНАЛЬНЫЕ РАСЧЁТЫ (формулы v_lm_sales_fees_cogs_es без изменений) ─────────────────────────────────────
calculated AS (
    SELECT
        date,
        clean_sku,
        product_sku,
        units_sold,
        price,
        tax_amount,
        commission_fee,
        price_vat_excl,
        quantity_refund,
        price_refund,
        tax_amount_refund,
        price_refund_vat_excl,
        commission_fee_refund,
        cogs_per_unit,
        cogs_quality_coef,
        mapping_source,
        shipping_cost_per_unit,
        packing_cost_per_unit,
        shipping_cost_source,
        cogs_per_unit          * units_sold                              AS cogs_total,
        shipping_cost_per_unit * units_sold                              AS shipping_cost_total,
        packing_cost_per_unit  * units_sold                              AS packing_cost_total,
        cogs_per_unit          * quantity_refund * cogs_quality_coef     AS cogs_refund,
        shipping_cost_per_unit * quantity_refund                         AS shipping_cost_refund,
        CASE WHEN cogs_per_unit IS NOT NULL THEN
            (cogs_per_unit * units_sold) + (shipping_cost_per_unit * units_sold) + (packing_cost_per_unit * units_sold)
          + commission_fee
        ELSE NULL END                                                    AS expenses,
        CASE WHEN cogs_per_unit IS NOT NULL THEN
            price_refund_vat_excl - commission_fee_refund
        ELSE NULL END                                                    AS expenses_refund
    FROM base_calculations
)

SELECT
    *,
    CASE WHEN cogs_per_unit IS NOT NULL THEN
        price_vat_excl - expenses - expenses_refund + cogs_refund - shipping_cost_refund
    ELSE NULL END AS profit
FROM calculated;


-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
CREATE VIEW dnipro_m.dnipro_m.v_wrt_spiderweb_report
COMMENT 'Worten PT: непрерывная сетка дней × SKU от первой продажи до вчера поверх v_wrt_sales_fees_cogs_pt. Форма v_cf_spiderweb_report (рекламы нет).'
AS
WITH
dates AS (
    SELECT explode(
        sequence(
            (SELECT MIN(date) FROM dnipro_m.v_wrt_sales_fees_cogs_pt),
            date_sub(current_date(), 1),
            INTERVAL 1 DAY
        )
    ) AS date
),
all_skus AS (
    SELECT clean_sku AS sku, MAX(product_sku) AS product_sku, 'Portugal' AS country
    FROM dnipro_m.v_wrt_sales_fees_cogs_pt
    GROUP BY clean_sku
),
grid AS (
    SELECT d.date, a.sku, a.product_sku, a.country
    FROM dates d
    CROSS JOIN all_skus a
)
SELECT
    g.date,
    g.country,
    g.sku,
    g.product_sku,
    COALESCE(s.units_sold,            0) AS units_sold,
    COALESCE(s.price,                 0) AS price,
    COALESCE(s.tax_amount,            0) AS tax_amount,
    COALESCE(s.commission_fee,        0) AS commission_fee,
    s.price_vat_excl,
    COALESCE(s.quantity_refund,       0) AS quantity_refund,
    COALESCE(s.price_refund,          0) AS price_refund,
    COALESCE(s.tax_amount_refund,     0) AS tax_amount_refund,
    s.price_refund_vat_excl,
    COALESCE(s.commission_fee_refund, 0) AS commission_fee_refund,
    COALESCE(s.cogs_total,            0) AS cogs_total,
    COALESCE(s.shipping_cost_total,   0) AS shipping_cost_total,
    COALESCE(s.packing_cost_total,    0) AS packing_cost_total,
    COALESCE(s.cogs_refund,           0) AS cogs_refund,
    COALESCE(s.shipping_cost_refund,  0) AS shipping_cost_refund,
    COALESCE(s.expenses,              0) AS expenses,
    COALESCE(s.expenses_refund,       0) AS expenses_refund,
    COALESCE(s.profit,                0) AS profit
FROM grid g
LEFT JOIN dnipro_m.v_wrt_sales_fees_cogs_pt s
    ON s.clean_sku = g.sku AND s.date = g.date
ORDER BY date, country, sku;


-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
CREATE VIEW dnipro_m.dnipro_m.v_wrt_orders_enriched
COMMENT 'Worten PT: строка на заказ (день заказа — Лиссабон), продажа с отгрузки: без строк до приёма заказа и отменённых. Форма v_lm_orders_enriched; сумма — SUM(price): price строки Mirakl уже за все единицы.'
AS
WITH
lines AS (
    SELECT
        DATE(o.created_at)                                               AS created_date,
        l.order_id,
        CAST(l.quantity AS INT)                                          AS quantity,
        CAST(l.price AS DOUBLE)                                          AS price,
        NULLIF(
            REGEXP_REPLACE(
                COALESCE(
                    NULLIF(REGEXP_EXTRACT(TRIM(l.shop_sku), r'^(.*?)[\s\-]+(?:FBA|FBM)'), ''),
                    TRIM(l.shop_sku)
                ),
                r'[-_\s]+$', ''
            ),
            ''
        )                                                                AS clean_sku_raw
    FROM dnipro_m.worten.raw_order_lines l
    JOIN dnipro_m.worten.raw_orders o
        ON o.shop_id = l.shop_id AND o.order_id = l.order_id
    WHERE o.shop_id = '18499'
      AND o.channel_code = 'WRT_PT_ONLINE'
      -- WRT_NOT_SALE — тот же список, что в v_wrt_sales_fees_cogs_pt
      AND l.order_line_state NOT IN ('STAGING', 'WAITING_ACCEPTANCE', 'WAITING_DEBIT', 'WAITING_DEBIT_PAYMENT', 'CANCELED', 'REFUSED')
),
lines_padded AS (
    SELECT
        created_date,
        order_id,
        quantity,
        price,
        CASE WHEN LENGTH(clean_sku_raw) < 8 THEN LPAD(clean_sku_raw, 8, '0') ELSE clean_sku_raw END AS clean_sku
    FROM lines
)
SELECT
    MIN(created_date)                                                    AS purchase_date,
    order_id,
    'Worten'                                                             AS marketplace,
    'Portugal'                                                           AS country,
    SUM(quantity)                                                        AS items_quantity_ordered,
    COUNT(DISTINCT CASE WHEN quantity > 0 THEN clean_sku END)            AS unique_sku_ordered,
    SUM(price)                                                           AS order_total_amount_eur
FROM lines_padded
GROUP BY order_id;
