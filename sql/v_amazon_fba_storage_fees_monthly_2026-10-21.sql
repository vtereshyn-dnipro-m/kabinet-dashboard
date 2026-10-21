-- Хранение FBA по месяцам (21.10.2026, решение владельца): вью поверх dnipro_m.dnipro_m.raw_amazon_fba_storage_fees.
-- Только вью — сырая таблица не меняется. Unity Catalog (Spark SQL), применять ПОСЛЕ мержа через SQL-склад.
--
-- Строка — как в сырье: месяц × центр × ASIN/FNSKU (отчёт GET_FBA_STORAGE_FEE_CHARGES_DATA).
-- market — страна центра (country_code отчёта). SKU в отчёте хранения нет: sku — ключ norm_sku экономики Amazon по FNSKU
--   из истории MYI, тем же правилом, что Economics Loader (`CLEAN_SQL` + `NORM_SQL`, docs/facts/economics.md): хвосты
--   -FBA/-FBM/_ срезаются, ядро — до 8 знаков, вариант-комплект (-A, -B, -1) и префикс набора S…_ СОХРАНЯЮТСЯ — это
--   другие товары. У одного FNSKU по нескольку SKU продавца (41324000-A и 41324000-A-FBA по рынкам), а ключ один:
--   78 FNSKU из 78 за всю историю MYI (21.10.2026). amzn.gr.… (Amazon Grade & Resell) — артикул без варианта: после
--   него у Amazon случайный код, и правило прочло бы его кусок как вариант (41324000-WJ); Economics Loader такие строки
--   не берёт вовсе.
--   Нет FNSKU в MYI — sku NULL (сентябрь 2026: 12 строк из 292 — снятые с продажи товары).
--   Источник — реплика dnipro_m.kabinet_data.raw_amazon_fba_myi_inventory, а не dnipro_m.raw_* (AGENTS.md, «Слои
--   данных»): осознанное исключение — в dnipro_m FNSKU покрыт хуже (fee preview 56 из 76, inventory planning 35 из 76,
--   MYI 57 из 76).
-- storage_fee — estimated_monthly_storage_fee отчёта, без НДС, в валюте отчёта; storage_fee_eur — по курсу ЕЦБ на
--   последний день месяца начисления (dnipro_m.dnipro_m.raw_ecb_fx_rates, правило docs/currency.md: EUR как есть, нет
--   курса — NULL, а не исходная сумма). Пустая валюта — евро, как в kabinet_data.to_eur (её заполняют не везде);
--   сейчас все 857 строк отчёта с валютой EUR.
-- season — 'high' за октябрь–декабрь (у Amazon повышенный тариф хранения), 'low' за январь–сентябрь.
--
-- Права: на каталог dnipro_m у группы `account users` ALL PRIVILEGES (SHOW GRANTS 21.10.2026), отдельных грантов на
-- raw_amazon_fba_storage_fees нет — вью в той же схеме видна тем же читателям; свой GRANT не нужен.
CREATE OR REPLACE VIEW dnipro_m.dnipro_m.v_amazon_fba_storage_fees_monthly
COMMENT 'Хранение FBA по месяцам: месяц, рынок, ASIN, SKU, объём, класс размера, средний остаток, плата (валюта и EUR), сезон high/low. Поверх raw_amazon_fba_storage_fees.'
AS
WITH sku_map AS (
    SELECT fnsku, min(norm) AS sku                    -- один на FNSKU (78 из 78); min — на случай второго
    FROM (
        SELECT fnsku,
               CASE WHEN lower(sku) LIKE 'amzn.gr.%' THEN lpad(regexp_extract(sku, '([0-9]{5,})', 1), 8, '0')
                    WHEN x RLIKE '^(S[0-9]*_)?[0-9]{5,}'
                    THEN concat(regexp_extract(x, '^(S[0-9]*_)?', 1),
                                lpad(regexp_extract(x, '^(?:S[0-9]*_)?([0-9]{5,})', 1), 8, '0'),
                                regexp_extract(x, '^(?:S[0-9]*_)?[0-9]{5,}(-[A-Z0-9]{1,2})?', 1))
                    ELSE '' END AS norm
        FROM (SELECT fnsku, sku,
                     regexp_replace(regexp_replace(upper(trim(sku)), '^(AMZN\\.GR\\.)?', ''),
                                    '[-_ ]*(FBA|FBM)([-_].*)?$', '') AS x
              FROM dnipro_m.kabinet_data.raw_amazon_fba_myi_inventory
              WHERE fnsku IS NOT NULL AND sku IS NOT NULL) c
    ) k
    WHERE norm <> ''
    GROUP BY fnsku
)
SELECT
    to_date(s.month_of_charge || '-01')                         AS month,
    s.country_code                                               AS market,
    s.fulfillment_center,
    s.asin,
    s.fnsku,
    m.sku,
    s.item_volume,
    s.volume_units,
    s.estimated_total_item_volume                                AS total_volume,
    s.product_size_tier                                          AS size_tier,
    s.average_quantity_on_hand                                   AS avg_qty_on_hand,
    s.estimated_monthly_storage_fee                              AS storage_fee,
    s.currency,
    CASE WHEN s.estimated_monthly_storage_fee IS NULL THEN NULL
         WHEN s.currency IS NULL OR s.currency = '' OR upper(s.currency) = 'EUR' THEN s.estimated_monthly_storage_fee
         ELSE s.estimated_monthly_storage_fee / fx.units_per_eur END AS storage_fee_eur,
    CASE WHEN month(to_date(s.month_of_charge || '-01')) IN (10, 11, 12) THEN 'high' ELSE 'low' END AS season
FROM dnipro_m.dnipro_m.raw_amazon_fba_storage_fees s
LEFT JOIN sku_map m ON m.fnsku = s.fnsku
LEFT JOIN dnipro_m.dnipro_m.raw_ecb_fx_rates fx
       ON fx.currency = upper(s.currency) AND fx.date = last_day(to_date(s.month_of_charge || '-01'));
