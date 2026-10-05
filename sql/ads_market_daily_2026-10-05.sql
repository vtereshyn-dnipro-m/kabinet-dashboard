-- ACOS и TACOS по формулам Дарины (Power BI, 05.10.2026):
--   ACOS  = расход на ВСЮ рекламу (SP + SB + SD) / продажи с рекламы (SP + SB + SD);
--   TACOS = весь расход на рекламу / все продажи С НДС.
-- Продажи с рекламы по SB есть только по КУПЛЕННОМУ ASIN (raw_amazon_ads_sb_purchased_product_*), не по рекламируемому
-- SKU, поэтому в ads_spend (строка = SKU) их нет. Для ACOS разрез по SKU не нужен — достаточно дня × рынка, и
-- здесь он хранится отдельной таблицей. Пишет Economics Loader, ячейка «Реклама по рынкам», ровно из тех же
-- источников, что её витрина: SP — sp_advertised_product (spend, sales14d), SD — sd_advertised_product (cost, sales),
-- SB — v_amazon_sb_metrics_recalculated_* (её разнос расхода + продажи по купленным ASIN), ManoMano —
-- raw_mm_ads_statistic_by_product_date (spend, paidSales; только Испания — по Франции таблицы нет).
CREATE TABLE IF NOT EXISTS kabinet_data.ads_market_daily (
    date         date    NOT NULL,
    marketplace  text    NOT NULL,          -- коды как в economics_summary: ES, IT, GB …, MM_ES
    ad_type      text    NOT NULL CHECK (ad_type IN ('SP', 'SB', 'SD', 'MM')),
    spend        double precision NOT NULL DEFAULT 0,
    ad_sales     double precision NOT NULL DEFAULT 0,
    ad_units     integer,
    clicks       bigint,
    impressions  bigint,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (date, marketplace, ad_type)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.ads_market_daily TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.ads_market_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Все продажи С НДС по дню × рынку — знаменатель TACOS. Amazon — витрина Sales & Traffic в евро (как карточка
-- «Продажи по заказам»); Mirakl — строки заказов с НДС, тем же отбором, что у Дарины: LM без REFUNDED по дате заказа,
-- ManoMano и Carrefour без отменённых. Wallapop и сайта в Кабинете нет (сентябрь у неё 446 € с НДС).
CREATE OR REPLACE VIEW kabinet_data.v_sales_vat_incl_daily AS
SELECT snapshot_date AS date, marketplace, SUM(ordered_sales)::double precision AS sales_vat_incl
FROM kabinet_data.v_sales_traffic_daily_eur
GROUP BY 1, 2
UNION ALL
SELECT o.created_date::date, 'LM', SUM(l.price)::double precision
FROM kabinet_data.raw_lm_order_lines l
JOIN kabinet_data.raw_lm_orders o USING (order_id)
WHERE l.order_line_state NOT IN ('REFUNDED', 'CANCELED', 'REFUSED')
GROUP BY 1
UNION ALL
SELECT order_date::date, 'MM_' || upper(country), SUM(total_price)::double precision
FROM kabinet_data.raw_mm_order_lines
WHERE upper(coalesce(order_status, '')) NOT IN ('CANCELED', 'REFUSED')
GROUP BY 1, 2
UNION ALL
SELECT order_date::date, 'CF_' || upper(country), SUM(total_price)::double precision
FROM kabinet_data.raw_cf_order_lines
WHERE upper(coalesce(order_status, '')) NOT IN ('CANCELED', 'REFUSED')
GROUP BY 1, 2;
GRANT SELECT ON kabinet_data.v_sales_vat_incl_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- Расход и продажи с рекламы в ЕВРО: у GB, SE и PL Ads API отдаёт суммы в валюте рынка (на 05.10.2026 рекламы там
-- нет вовсе, но молча сложить фунты с евро — та же ошибка, что была в экономике до 01.10). Читатели берут эту вью.
CREATE OR REPLACE VIEW kabinet_data.v_ads_market_daily_eur AS
SELECT a.date, a.marketplace, a.ad_type,
       kabinet_data.to_eur(a.spend, c.cur, a.date)    AS spend,
       kabinet_data.to_eur(a.ad_sales, c.cur, a.date) AS ad_sales,
       a.ad_units, a.clicks, a.impressions
FROM kabinet_data.ads_market_daily a
CROSS JOIN LATERAL (SELECT CASE a.marketplace WHEN 'GB' THEN 'GBP' WHEN 'SE' THEN 'SEK' WHEN 'PL' THEN 'PLN'
                                ELSE 'EUR' END AS cur) c;
GRANT SELECT ON kabinet_data.v_ads_market_daily_eur TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- Свежесть и паспорт: новая таблица кормит ACOS и TACOS на «Рекламе» и «Обзоре» — без правила сторож её не видит,
-- а паспорт не может сказать, по какое число цифра.
INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment, content_date_column, max_content_age_hours)
VALUES ('kabinet_data.ads_market_daily', 'updated_at', 26, 'lakebase', 'economics', true,
        'Реклама по рынкам для ACOS/TACOS (Economics Loader, ячейка 3b). Amazon отдаёт день с лагом до трёх суток.',
        'date', 96)
ON CONFLICT (table_name) DO UPDATE SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
    comment = EXCLUDED.comment, content_date_column = EXCLUDED.content_date_column,
    max_content_age_hours = EXCLUDED.max_content_age_hours, is_active = true, updated_at = now();

INSERT INTO kabinet_data.data_source_origins
    (table_name, platform_source, platform_refresh, our_refresh, verdict, note, darina_method, darina_verdict, darina_reason)
VALUES ('kabinet_data.ads_market_daily',
        'Amazon Ads API: SP и SD по рекламируемому товару, SB — расход из разноса Дарины и продажи по купленным ASIN; ManoMano — статистика рекламы по товарам',
        'суточно; атрибуция уточняется до 14 дней', 'Kabinet - Economics Loader 12:30 Kyiv', 'ok',
        'ACOS = весь расход на рекламу (SP+SB+SD) / продажи с рекламы; TACOS = весь расход / все продажи с НДС. Wallapop и сайта в Кабинете нет — их продажи (у Дарины 446 € за сентябрь) в знаменатель TACOS не входят.',
        'ACOS = расход SP+SB+SD / продажи с рекламы SP+SB+SD (sales14d, у SB — по купленным ASIN), TACOS = весь расход / все продажи с НДС (Power BI).',
        'same',
        'формулы совпадают с Power BI Дарины: те же источники и то же определение; сентябрь — ACOS 28,0 % у обоих, TACOS 9,6 % против её 9 % (в её знаменателе ещё Wallapop и сайт)')
ON CONFLICT (table_name) DO UPDATE SET platform_source = EXCLUDED.platform_source, platform_refresh = EXCLUDED.platform_refresh,
    our_refresh = EXCLUDED.our_refresh, verdict = EXCLUDED.verdict, note = EXCLUDED.note,
    darina_method = EXCLUDED.darina_method, darina_verdict = EXCLUDED.darina_verdict,
    darina_reason = EXCLUDED.darina_reason, updated_at = now();

UPDATE kabinet_data.data_source_origins
SET darina_reason = 'расход совпадает до евро — SB мы берём из её же пересчёта; продажи с рекламы в этой таблице только SP и SD (строка = SKU), поэтому ACOS и TACOS считаются по ads_market_daily, где SB есть',
    updated_at = now()
WHERE table_name = 'kabinet_data.ads_spend';
