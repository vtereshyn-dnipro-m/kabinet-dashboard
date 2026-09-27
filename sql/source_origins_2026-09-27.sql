-- Паспорт данных: последнее звено — откуда загрузчик берёт данные у площадки (решение владельца 27.09.2026).
--
-- Три вещи, которых в паспорте не было: конкретный API или отчёт площадки, как часто площадка сама
-- обновляет эти данные и как часто их тянем мы. Из сопоставления второго с третьим видно то, что
-- иначе не видно ниоткуда: тянем чаще, чем площадка обновляет — лишние запросы к общей квоте;
-- тянем реже — цифры на экране могут отставать, и человек должен знать насколько.
--
-- Отдельной таблицей, а не колонками в `data_freshness_rules`: та принадлежит владельцу базы,
-- и ALTER ей роль Кабинета не сделает (та же причина, по которой реквизиты складов лежат в
-- `warehouse_attributes` рядом с `warehouses`).
--
-- Вердикт хранится явно, а не выводится из текста: периодичности здесь — слова («в реальном
-- времени», «раз в месяц»), сравнивать их кодом значило бы разбирать русский язык.
CREATE TABLE IF NOT EXISTS kabinet_data.data_source_origins (
    table_name        text PRIMARY KEY,            -- как в data_freshness_rules и в паспорте
    platform_source   text NOT NULL,               -- конкретный API или отчёт: «Data Kiosk Economics», «GET_FBA_MYI_...»
    platform_refresh  text NOT NULL,               -- как часто обновляет площадка
    our_refresh       text NOT NULL,               -- расписание нашей джобы
    verdict           text NOT NULL DEFAULT 'ok'
        CHECK (verdict IN ('ok', 'we_pull_more', 'we_pull_less')),
    note              text,                        -- чем именно грозит расхождение
    updated_at        timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN kabinet_data.data_source_origins.verdict IS
    'ok — совпадает; we_pull_more — тянем чаще, чем площадка обновляет (лишние запросы к квоте); we_pull_less — тянем реже, данные могут отставать.';

INSERT INTO kabinet_data.data_source_origins
    (table_name, platform_source, platform_refresh, our_refresh, verdict, note) VALUES
 ('kabinet_data.economics_summary', 'Data Kiosk Economics (Amazon) + Mirakl transactions_logs (LM, CF) и Orders API (MM)',
  'Amazon суточно, последний день неполный; Mirakl в реальном времени',
  'Kabinet - Economics Loader 12:30; LM 03:00, CF 10:00, MM 09:00 Kyiv', 'we_pull_less',
  'Последний день Amazon всегда неполный — это лаг площадки, не загрузчика. По Mirakl цифры отстают до суток.'),
 ('kabinet_data.economics_logistics', 'наш расчёт поверх economics_summary и тарифной сетки доставки',
  'источник у площадки отсутствует — считаем сами', 'Kabinet - Economics Loader 12:30 Kyiv', 'ok', NULL),
 ('kabinet_data.ads_spend', 'Amazon Ads API (SP, SD) плюс разнос SB из расчёта Дарины',
  'суточно; атрибуция уточняется до 14 дней', 'Kabinet - Economics Loader 12:30 Kyiv', 'ok',
  'Свежие дни Amazon доуточняет — расхождение за последнюю неделю нормально.'),
 ('kabinet_data.sales_traffic_daily', 'отчёт Sales & Traffic (Seller Central) через сырьё Дарины',
  'суточно, вчерашний день полный', 'реплика Kabinet - Sales & Traffic Replica 10:50 Kyiv (её отчёт 08:00)', 'ok',
  'Мы вторые в очереди: свежесть равна её прогону.'),
 ('kabinet_data.stock_local', 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY (Amazon) и Mirakl /api/offers',
  'Amazon пересобирает несколько раз в сутки, Mirakl в реальном времени',
  'MYI 07:15, Kabinet - Stock Loader 12:00 и 15:00, офферы LM 08:00/16:00, MM 09:30, CF 09:45 Kyiv', 'we_pull_less',
  'Остаток на экране может отставать от витрины на часы: продажи идут между прогонами.'),
 ('kabinet_data.warehouse_stock', 'Odoo XML-RPC (Мадрид, магазины) и выгрузка ERP (Piasecznie, Тернополь)',
  'Odoo в реальном времени; ERP выгружается дважды в сутки — 10:32 и 14:35 Kyiv',
  'Kabinet - Stock Loader 12:00 и 15:00 Kyiv', 'ok',
  'Второй прогон в 15:00 добавлен 27.09.2026 именно под вторую выгрузку ERP: до этого она никем не читалась.'),
 ('kabinet_data.raw_amazon_fba_inventory_planning', 'GET_FBA_INVENTORY_PLANNING_DATA',
  'суточно', 'Kabinet - Inventory Age Loader 04:00 Kyiv', 'ok', NULL),
 ('kabinet_data.fba_ledger_detail', 'GET_LEDGER_DETAIL_VIEW_DATA',
  'суточно, но данные приходят с лагом день+2', 'Kabinet - FBA Ledger Detail 11:00 Kyiv', 'ok',
  'Два последних дня в ledger всегда пустые — так отдаёт Amazon.'),
 ('kabinet_data.raw_amazon_fba_storage_fees', 'GET_FBA_STORAGE_FEE_CHARGES_DATA',
  'помесячно — хранение считается за календарный месяц',
  'Kabinet - FBA Charges Loader понедельник 07:30 Kyiv', 'ok',
  'До 27.09.2026 тянули ежедневно: ~30 лишних createReport в месяц из общей квоты аккаунта.'),
 ('kabinet_data.raw_amazon_returns', 'GET_XML_RETURNS_DATA_BY_RETURN_DATE',
  'суточно', 'Kabinet - Returns Loader 06:00 Kyiv', 'ok', NULL),
 ('kabinet_data.raw_amazon_settlements', 'settlement-отчёты V2 — Amazon создаёт их сам по закрытии периода',
  'раз в ~14 дней на рынок', 'Kabinet - Settlements Loader 08:30 Kyiv ежедневно', 'we_pull_more',
  'Опрос ежедневный, но через getReports — квоту createReport он не тратит, поэтому оставлен.'),
 ('kabinet_data.raw_amazon_fulfilled_shipments', 'GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL',
  'суточно; строки доезжают с задержкой до нескольких суток',
  'Kabinet - FBA Shipments Loader 15:30 Kyiv', 'ok',
  'Задержку закрывает окно перечитывания (reorder_params.fba_shipments_window_days).'),
 ('kabinet_data.shipment_facts', 'сборка: отчёт отгрузок FBA, SendCloud Orders API, Mirakl /api/orders',
  'FBA суточно, SendCloud и Mirakl в реальном времени',
  'Kabinet - Shipment Facts 16:30 Kyiv (SendCloud Дарины 09:11)', 'we_pull_less',
  'Отгрузки последнего дня доезжают на следующий прогон.'),
 ('kabinet_data.raw_lm_orders', 'Mirakl /api/orders (Leroy Merlin)', 'в реальном времени',
  'Kabinet - LM Orders Loader 09:30 и 15:30 Kyiv', 'we_pull_less', 'Заказы после 15:30 видны утром.'),
 ('kabinet_data.raw_mm_orders', 'ManoMano Orders API', 'в реальном времени',
  'Kabinet - MM Orders Loader 09:00 Kyiv', 'we_pull_less', 'Заказы после 09:00 видны на следующий день.'),
 ('kabinet_data.raw_cf_orders', 'Mirakl /api/orders (Carrefour)', 'в реальном времени',
  'Kabinet - CF Orders Loader 09:30 Kyiv', 'we_pull_less', 'Заказы после 09:30 видны на следующий день.'),
 ('kabinet_data.raw_amazon_listing_snapshots', 'витрина Amazon через Scrapingdog (Listing Suite)',
  'витрина меняется в реальном времени', 'Listing Suite Auto Collector 13:00 Kyiv, 120–130 ASIN из 287 в сутки',
  'we_pull_less', 'Каждая карточка обновляется примерно раз в два дня — цена и BSR в паспорте с датой снимка.'),
 ('kabinet_data.asin_reviews_daily', 'витрина Amazon через те же снимки',
  'отзывы появляются в реальном времени', 'Listing Suite Sync Reviews Daily 07:30 Kyiv', 'we_pull_less',
  'Отзыв виден на следующий прогон.'),
 ('listing_data.search_query_performance', 'отчёт Search Query Performance (Brand Analytics)',
  'недельно, неделя вс–сб; Amazon публикует с задержкой около 10 дней',
  'Listing Suite SQP Loader, шесть слотов в сутки — очередь по ASIN × рынок × неделя', 'ok',
  'Шесть прогонов — не переопрос: один отчёт на ASIN × рынок × неделю, слоты нужны из-за квоты один отчёт в минуту.'),
 ('kabinet_data.raw_amazon_seller_performance', 'GET_V2_SELLER_PERFORMANCE_REPORT',
  'суточно', 'Kabinet - Account Health Loader 04:15 Kyiv', 'ok', NULL),
 ('kabinet_data.coverage_summary', 'наш расчёт поверх остатка, поступлений и спроса',
  'источника у площадки нет — считаем сами', 'Kabinet - Coverage Projection 13:15 Kyiv', 'ok', NULL),
 ('kabinet_data.reorder_recommendations', 'наш расчёт поверх остатка, скорости и сроков поставки',
  'источника у площадки нет — считаем сами', 'Kabinet - Stock Loader 12:00 и 15:00 Kyiv', 'ok', NULL),
 ('kabinet_data.transfer_recommendations', 'наш расчёт поверх остатков складов и маршрутов',
  'источника у площадки нет — считаем сами', 'Kabinet - Stock Loader 12:00 и 15:00 Kyiv', 'ok', NULL),
 ('kabinet_data.forecast_register', 'лист Google «Amazon Product Planning» плюс ввод человека на «Прогнозе»',
  'меняется, когда его правят люди', 'Kabinet - Forecast Plan Loader, запуск по триггеру около 03:00 Kyiv', 'ok', NULL),
 ('kabinet_data.incidents', 'наш сторож поверх правил свежести и качества',
  'источника у площадки нет — считаем сами', 'Kabinet - Watchdog 13:00 Kyiv', 'ok', NULL)
ON CONFLICT (table_name) DO UPDATE SET
    platform_source = EXCLUDED.platform_source, platform_refresh = EXCLUDED.platform_refresh,
    our_refresh = EXCLUDED.our_refresh, verdict = EXCLUDED.verdict, note = EXCLUDED.note,
    updated_at = now();

GRANT SELECT ON kabinet_data.data_source_origins TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.data_source_origins TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.data_source_origins TO claude_code_ro;

-- Расписания, изменённые тем же решением: правило здоровья и порог свежести идут за джобой,
-- иначе сторож будет ругаться на живую джобу (AGENTS.md, «одно имя джоба в трёх местах»).
UPDATE kabinet_data.job_health_rules
   SET schedule_description = 'MON 07:30 Kyiv weekly', expected_interval_hours = 192
 WHERE job_name = 'Kabinet - FBA Charges Loader';
UPDATE kabinet_data.job_health_rules
   SET schedule_description = '12:00 и 15:00 Kyiv daily'
 WHERE job_name = 'Kabinet - Stock Loader';
UPDATE kabinet_data.data_freshness_rules
   SET max_age_hours = 192, comment = 'Хранение FBA: отчёт помесячный, загрузчик по понедельникам (с 27.09.2026).',
       updated_at = now()
 WHERE table_name = 'kabinet_data.raw_amazon_fba_storage_fees';

SELECT verdict, count(*) FROM kabinet_data.data_source_origins GROUP BY 1 ORDER BY 2 DESC;
SELECT job_name, schedule_description, expected_interval_hours FROM kabinet_data.job_health_rules
 WHERE job_name IN ('Kabinet - FBA Charges Loader', 'Kabinet - Stock Loader') ORDER BY 1;
