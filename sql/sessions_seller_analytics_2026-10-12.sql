-- Сессии по ASIN — из Seller Analytics, а не из сырья Sales & Traffic (12.10.2026).
-- Применять ПОСЛЕ мержа и ДО выкладки ноутбука реплики: ячейка 2 пишет sessions_source.
--
-- В сырье Sales & Traffic строки есть только у ASIN с продажей в этот день, поэтому сессии в sales_traffic_asin
-- были неполными (ES, сентябрь: 10 492 против 22 083 в Seller Central). С этого дня полные сессии пишет
-- Kabinet - Sales & Traffic Replica, ячейка 2, с пометкой sessions_source = 'seller_analytics'; строка без пометки —
-- сессий за этот день не знаем. Прежние неполные значения стираем: число, которое занижено вдвое, хуже пустоты —
-- его прочитают как настоящее.

ALTER TABLE kabinet_data.sales_traffic_asin ADD COLUMN IF NOT EXISTS sessions_source TEXT;

COMMENT ON COLUMN kabinet_data.sales_traffic_asin.sessions_source IS
  'Откуда сессии и просмотры: seller_analytics — полные (Data Kiosk Seller Analytics, ячейка 2 реплики S&T); пусто — сессий за день не знаем, читатели строку не считают.';
COMMENT ON COLUMN kabinet_data.sales_traffic_asin.sessions IS
  'Сессии ASIN за день по Seller Analytics, если sessions_source = seller_analytics; иначе пусто. ASIN без продаж в этот день — строка с нулём штук.';
COMMENT ON TABLE kabinet_data.sales_traffic_asin IS
  'Sales & Traffic по ASIN × день: продажи — из сырья Sales & Traffic (только ASIN с продажей), сессии — из Seller Analytics (все ASIN с трафиком). Пишет Kabinet - Sales & Traffic Replica.';

UPDATE kabinet_data.sales_traffic_asin
   SET sessions = NULL, page_views = NULL
 WHERE sessions_source IS NULL AND (sessions IS NOT NULL OR page_views IS NOT NULL);

SELECT count(*) AS rows_total,
       count(*) FILTER (WHERE sessions_source = 'seller_analytics') AS rows_with_sessions
  FROM kabinet_data.sales_traffic_asin;
