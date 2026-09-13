-- Поправки к марже из settlement: то, чего в Data Kiosk (economics_fees) нет.
-- Lakebase, kabinet_data.
--
-- Суммы — без НДС на сборы. У хранения, removal, Vine, купонов IVA идёт
-- отдельной строкой «Tax on fee» — её не берём. У промо НДС-часть скидки —
-- строка «TaxDiscount», тоже не берём. У chargeback/HB/financing IVA зашит в
-- сумму и не отделяется — они идут как есть, это 150–300 € в квартал.
--
-- Знак как у Amazon: расходы отрицательные. Сборы с заказа, которые уже есть
-- в economics (комиссия, FBA fulfilment, DST, комиссия за возврат), сюда
-- НЕ входят — иначе посчитаем дважды. Реклама — в ads_spend. Резервы и
-- возмещения — не поправки к марже.
--
-- base_sku заполнен там, где Amazon его даёт: промо и сборы с заказа.
-- Хранение, removal, Vine, подписка приходят без SKU — attributable = false,
-- страница раскладывает их пропорционально выручке и подписывает это.

CREATE OR REPLACE VIEW kabinet_data.v_margin_adjustments AS
WITH b AS (
    SELECT marketplace, posted_date, amount,
           substring(sku FROM '([0-9]{5,})') AS base_sku,
           CASE
             WHEN amount_type = 'Promotion' AND amount_description IN ('Principal', 'Shipping')
                  THEN 'promo'
             WHEN amount_type = 'ItemFees'
                  AND amount_description IN ('ShippingChargeback', 'ShippingHB', 'Flexible Customer Financing fee')
                  THEN 'order_fees_other'
             WHEN amount_type LIKE 'FBA%Storage%' AND amount_description = 'Base fee'
                  THEN 'storage'
             WHEN (amount_type LIKE 'FBA Removal%' AND amount_description IN ('Base fee', 'Discount on Fee'))
                  OR amount_description = 'RemovalComplete'
                  THEN 'removal'
             WHEN amount_type = 'Vine Enrollment Fee' AND amount_description = 'Base fee'
                  THEN 'vine'
             WHEN amount_description = 'Subscription Fee'
                  THEN 'subscription'
             WHEN amount_description LIKE 'Shipping label purchase%'
                  THEN 'return_labels'
             WHEN (amount_type LIKE '%Coupon%' OR amount_type LIKE '%Deal%') AND amount_description = 'Base fee'
                  THEN 'coupons_deals'
           END AS bucket
    FROM kabinet_data.raw_amazon_settlements
    WHERE row_no > 0 AND marketplace IS NOT NULL
)
SELECT marketplace, posted_date, bucket,
       CASE WHEN bucket IN ('promo', 'order_fees_other') THEN base_sku END AS base_sku,
       bucket IN ('promo', 'order_fees_other') AS attributable,
       sum(amount)::numeric(14,2) AS amount,
       count(*) AS provodok
  FROM b
 WHERE bucket IS NOT NULL
 GROUP BY 1, 2, 3, 4, 5;

COMMENT ON VIEW kabinet_data.v_margin_adjustments IS
    'Поправки к марже из settlement, без НДС на сборы: промо, хранение, removal, Vine, '
    'подписка, ярлыки возврата, купоны, прочие сборы с заказа. attributable — есть SKU.';

GRANT SELECT ON kabinet_data.v_margin_adjustments TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_margin_adjustments TO claude_code_ro;

SELECT bucket, attributable, sum(amount) AS eur, sum(provodok) AS provodok
  FROM kabinet_data.v_margin_adjustments
 WHERE marketplace = 'ES' AND posted_date >= '2026-07-01' AND posted_date < '2026-09-01'
 GROUP BY 1, 2 ORDER BY 3;
