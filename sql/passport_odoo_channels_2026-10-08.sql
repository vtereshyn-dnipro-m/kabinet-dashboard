-- Паспорт данных: Wallapop и сайт с 08.10.2026 загружаются из Odoo (Kabinet - Odoo Channels Loader) — примечания
-- «не загружаются» больше не правда.
UPDATE kabinet_data.data_source_origins SET note =
 'Последний день Amazon всегда неполный — это лаг площадки, не загрузчика. По Mirakl цифры отстают до суток. Wallapop и сайт (WP_ES, WEB_ES) с 08.10.2026 приходят из заказов Odoo — загрузчик Kabinet - Odoo Channels Loader, 10:30 Kyiv; история с 15.05.2026, как у Amazon.'
 WHERE table_name = 'kabinet_data.economics_summary';
UPDATE kabinet_data.data_source_origins SET note =
 'ACOS = весь расход на рекламу (SP+SB+SD) / продажи с рекламы; TACOS = весь расход / все продажи с НДС — с 08.10.2026 вместе с Wallapop и сайтом, как в Power BI.'
 WHERE table_name = 'kabinet_data.ads_market_daily';
-- ACOS / TACOS с Wallapop и сайтом совпадают с Power BI до сотой (сентябрь: расход 7 601,39 €, продажи с НДС 79 678,59 €)
UPDATE kabinet_data.data_source_origins SET darina_verdict = 'same', darina_reason =
 'формулы и данные совпадают с Power BI: сентябрь — ACOS 28,0 % в обоих, TACOS 9,54 % = 9,54 % (расход 7 601,39 €, продажи с НДС 79 678,59 € — с Wallapop и сайтом, подключены 08.10.2026)'
 WHERE table_name = 'kabinet_data.ads_market_daily';
UPDATE kabinet_data.data_source_origins SET darina_reason =
 replace(darina_reason, 'Wallapop и сайт −90 / −109 € — подключаем.', 'Wallapop и сайт −90 / −109 € — с 08.10.2026 загружаются из Odoo, доставка по ним считается с 09.10.')
 WHERE table_name = 'kabinet_data.economics_summary';
