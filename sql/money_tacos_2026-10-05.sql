-- TACOS и ACOS по SKU на «Деньгах» (05.10.2026): формулы Power BI Дарины, как на «Рекламе» и «Обзоре».
--   TACOS = весь расход на рекламу / продажи С НДС;  ACOS = весь расход / продажи с рекламы (SP + SB + SD).

-- Ключ экономики Amazon из seller SKU — то же правило, что в Economics Loader (ячейки 2 и 3, NORM_SQL/CLEAN_SQL,
-- с 05.10.2026): префикс набора S…_ СОХРАНЯЕТСЯ, ядро до 8 знаков, вариант не длиннее двух, хвосты FBA/FBM срезаются.
-- Отличие от amz_norm_sku ровно в префиксе набора: та его срезает и сводит набор к одиночному товару.
CREATE OR REPLACE FUNCTION kabinet_data.amz_econ_key(p text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH c AS (
        SELECT regexp_replace(regexp_replace(upper(btrim(coalesce(p, ''))), '^(AMZN\.GR\.)?', ''),
                              '[-_ ]*(FBA|FBM)([-_].*)?$', '') AS x)
    SELECT CASE WHEN x ~ '^(S[0-9]*_)?[0-9]{5,}'
                THEN coalesce(substring(x from '^(S[0-9]*_)'), '')
                     || lpad(substring(x from '^(?:S[0-9]*_)?([0-9]{5,})'), 8, '0')
                     || coalesce(substring(x from '^(?:S[0-9]*_)?[0-9]{5,}(-[A-Z0-9]{1,2})'), '')
                ELSE '' END
    FROM c
$$;

-- Продажи с НДС по SKU × день × рынок — знаменатель TACOS по SKU.
--  • Amazon — витрина Sales & Traffic по ASIN × SKU (тот же отчёт, что у Дарины), в евро, ключ — amz_econ_key;
--  • Mirakl — продажи без НДС из экономики, умноженные на отношение «с НДС / без НДС» того же дня и рынка из
--    v_sales_vat_incl_daily. Ставка на рынке Mirakl одна (Испания 21 %, Франция 20 %), поэтому доля точная, а ключ
--    SKU остаётся тем, каким его записал загрузчик канала — второго правила нормализации заводить не пришлось.
--    Для Amazon так нельзя: экономика Data Kiosk отстаёт от витрины, и в день с неполной экономикой отношение
--    раздуло бы продажи SKU в разы.
CREATE OR REPLACE VIEW kabinet_data.v_sku_sales_vat_incl_daily AS
SELECT a.snapshot_date AS date, a.marketplace, kabinet_data.amz_econ_key(a.sku) AS norm_sku,
       SUM(kabinet_data.to_eur(a.ordered_sales,
           CASE a.marketplace WHEN 'GB' THEN 'GBP' WHEN 'SE' THEN 'SEK' WHEN 'PL' THEN 'PLN' ELSE 'EUR' END,
           a.snapshot_date)) AS sales_vat_incl
FROM kabinet_data.sales_traffic_asin a
WHERE kabinet_data.amz_econ_key(a.sku) <> ''
GROUP BY 1, 2, 3
UNION ALL
SELECT e.sales_date, e.marketplace, e.norm_sku,
       SUM(e.ordered_product_sales) * MAX(v.sales_vat_incl / NULLIF(t.ex_vat, 0))
FROM kabinet_data.v_economics_summary_eur e
JOIN (SELECT sales_date, marketplace, SUM(ordered_product_sales) AS ex_vat
      FROM kabinet_data.v_economics_summary_eur
      WHERE marketplace IN ('LM', 'MM_ES', 'MM_FR', 'CF_ES') GROUP BY 1, 2) t
  ON t.sales_date = e.sales_date AND t.marketplace = e.marketplace
JOIN kabinet_data.v_sales_vat_incl_daily v ON v.date = e.sales_date AND v.marketplace = e.marketplace
WHERE e.marketplace IN ('LM', 'MM_ES', 'MM_FR', 'CF_ES')
GROUP BY 1, 2, 3;
GRANT SELECT ON kabinet_data.v_sku_sales_vat_incl_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- Продажи с рекламы по SKU — SP + SD по рекламируемому SKU плюс SB по купленному ASIN (колонка sb_sales_14d в
-- ads_spend, пишет Economics Loader, ячейка 3, с 05.10.2026). Колонка добавлена в конец вью — читатели прежних
-- колонок не затронуты.
CREATE OR REPLACE VIEW kabinet_data.v_ads_spend_margin AS
SELECT date, marketplace, norm_sku,
       sum(total_spend) AS total_spend,
       sum(COALESCE(sp_spend, 0::double precision)) AS sp_in_proceeds,
       sum(COALESCE(sb_spend, 0::double precision) + COALESCE(sd_spend, 0::double precision)) AS margin_ads,
       sum(COALESCE(sp_sd_sales_14d, 0::double precision) + COALESCE(sb_sales_14d, 0::double precision)) AS ad_sales
FROM kabinet_data.ads_spend
GROUP BY date, marketplace, norm_sku;
