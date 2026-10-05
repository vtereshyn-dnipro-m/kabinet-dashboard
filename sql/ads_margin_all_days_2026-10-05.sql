-- Реклама в марже — вся, а не только в дни с продажами (05.10.2026).
--
-- Маржа на «Обзоре», в «Деньгах» и в недельном отчёте присоединяла рекламу к строкам экономики по ключу
-- день × рынок × SKU. Расход SKU в день, когда у него не было ни продажи, ни возврата, строки не находил и
-- в маржу не попадал вовсе. Сентябрь 2026: из 1 212 € SB+SD до маржи доходили 879 €; у ManoMano
-- (продаж мало, реклама каждый день) терялся бы почти весь расход.
--
-- 1) v_ads_spend_margin: в маржу идёт SB + SD + ManoMano, а SP — только там, где строки выплаты нет. SP Amazon
--    удерживает внутри net_proceeds_total строки экономики того же SKU × дня (сверка сентября, до цента), но
--    если строки нет, удерживать ему не из чего — и этот SP раньше не вычитался нигде (сентябрь ≈ 229 €).
-- 2) v_economics_with_ad_days: строки экономики плюс «рекламные дни» — SKU × день, где реклама есть, а строки
--    экономики нет. Деньги в них нулевые, себестоимость за единицу — из цепочки (sku_cogs_current), чтобы SKU
--    остался в периметре «с себестоимостью» тем же правилом; штук ноль, поэтому себестоимость не вычитается.
--    Даты — не позже последней даты экономики своего рынка: рекламный день «впереди» экономики иначе сдвинул бы
--    окно страницы, а когда экономика за этот день придёт, реклама сама сядет на её строку.
CREATE OR REPLACE VIEW kabinet_data.v_ads_spend_margin AS
WITH a AS (
    SELECT date, marketplace, norm_sku,
           sum(total_spend) AS total_spend,
           sum(COALESCE(sp_spend, 0::double precision)) AS sp,
           sum(COALESCE(sb_spend, 0::double precision) + COALESCE(sd_spend, 0::double precision)
               + COALESCE(mm_spend, 0::double precision)) AS sb_sd_mm,
           sum(COALESCE(sp_sd_sales_14d, 0::double precision) + COALESCE(sb_sales_14d, 0::double precision)
               + COALESCE(mm_sales, 0::double precision)) AS ad_sales
    FROM kabinet_data.ads_spend
    GROUP BY date, marketplace, norm_sku
)
SELECT a.date, a.marketplace, a.norm_sku, a.total_spend,
       CASE WHEN e.has_row THEN a.sp ELSE 0 END                AS sp_in_proceeds,
       a.sb_sd_mm + CASE WHEN e.has_row THEN 0 ELSE a.sp END   AS margin_ads,
       a.ad_sales
FROM a
LEFT JOIN LATERAL (SELECT true AS has_row FROM kabinet_data.economics_summary x
                   WHERE x.sales_date = a.date AND x.marketplace = a.marketplace AND x.norm_sku = a.norm_sku
                   LIMIT 1) e ON true;

CREATE OR REPLACE VIEW kabinet_data.v_economics_with_ad_days AS
SELECT sales_date, marketplace, norm_sku, product_name, units_ordered, units_refunded, net_units_sold,
       ordered_product_sales, net_product_sales, total_fees, net_proceeds_total, net_proceeds_per_unit,
       commission_fee, cogs, cogs_source, currency_code, source_currency, updated_at
FROM kabinet_data.v_economics_summary_eur
UNION ALL
SELECT a.date, a.marketplace, a.norm_sku, NULL::text, 0, 0, 0,
       0::double precision, 0::double precision, 0::double precision, 0::double precision, NULL::double precision,
       NULL::double precision, c.cogs, 'ad_day'::text, 'EUR'::text, 'EUR'::varchar, NULL::timestamp
FROM kabinet_data.v_ads_spend_margin a
JOIN (SELECT marketplace, max(sales_date) AS last_day FROM kabinet_data.economics_summary GROUP BY 1) m
  ON m.marketplace = a.marketplace AND a.date <= m.last_day
LEFT JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.sku_cogs_key(a.norm_sku)
WHERE (a.margin_ads <> 0 OR a.total_spend <> 0)
  AND NOT EXISTS (SELECT 1 FROM kabinet_data.economics_summary x
                  WHERE x.sales_date = a.date AND x.marketplace = a.marketplace AND x.norm_sku = a.norm_sku);
GRANT SELECT ON kabinet_data.v_ads_spend_margin, kabinet_data.v_economics_with_ad_days
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";
