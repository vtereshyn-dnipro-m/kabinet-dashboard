-- Никаких имён людей в интерфейсе (решение владельца 08.10.2026). Источник называем системой:
-- «Power BI», «витрина продаж», «лист Poland-Spain», «сырьё Sales & Traffic», «Odoo».
-- Применять ПОСЛЕ выкладки ноутбуков этого PR (Reconciliation, Watchdog, Stock Loader, Weekly Report):
-- сверка в 13:00 переписывает reconcile_with и строки reconciliation_results своей подписью источника,
-- а сторож — комментарий правила supply_poland_spain из своего списка RULES.
BEGIN;

-- ── паспорт данных (data_source_origins): всё, что видно в блоке «Откуда данные» ──
UPDATE kabinet_data.data_source_origins SET reconcile_with = 'Power BI и settlement Amazon'
 WHERE table_name = 'kabinet_data.economics_summary';
UPDATE kabinet_data.data_source_origins SET note =
 'Последний день Amazon всегда неполный — это лаг площадки, не загрузчика. По Mirakl цифры отстают до суток. Каналы Wallapop и сайт в Кабинет пока не загружаются: в выручке и марже их нет (сентябрь 2026 — 369 € без НДС в Power BI).'
 WHERE table_name = 'kabinet_data.economics_summary';
UPDATE kabinet_data.data_source_origins SET darina_reason =
 'методика разная (в Power BI модельные комиссии и себестоимость на месяц продажи, у нас фактическая выплата Amazon). Подтверждено экраном Power BI 07.10: маржа там — прямая сумма contribution_profit витрины продаж, DAX её не пересчитывает (август −1 746 € сошёлся до евро). Уточняется одно: задумано ли у Mirakl вычитать возврат по строке REFUNDED, исключённой из продаж (сентябрь LM около −50 €)'
 WHERE table_name = 'kabinet_data.economics_summary';
UPDATE kabinet_data.data_source_origins SET note =
 'ACOS = весь расход на рекламу (SP+SB+SD) / продажи с рекламы; TACOS = весь расход / все продажи с НДС. Wallapop и сайта в Кабинете пока нет — их продажи (в Power BI 446 € за сентябрь) в знаменатель TACOS не входят.',
 platform_source =
 'Amazon Ads API: SP и SD по рекламируемому товару, SB — расход из разноса SB по ASIN и продажи по купленным ASIN; ManoMano — статистика рекламы по товарам',
 darina_reason =
 'формулы совпадают с Power BI: те же источники и то же определение; сентябрь — ACOS 28,0 % в обоих, TACOS 9,6 % против 9 % в Power BI (в его знаменателе ещё Wallapop и сайт)'
 WHERE table_name = 'kabinet_data.ads_market_daily';
UPDATE kabinet_data.data_source_origins SET darina_reason =
 'в Power BI — 90 % себестоимости любого возврата, у нас — себестоимость только годного по факту (Amazon или Odoo, включая проверку на складе брака); коэффициент 0,9 — правило или временная заглушка, уточняется'
 WHERE table_name = 'kabinet_data.v_returns_cogs_credit';
UPDATE kabinet_data.data_source_origins SET note =
 'План снабжения вычитается из «Заказать», чтобы не заказать второй раз уже заказанное. Берётся большее из двух источников: заказы Odoo на мадридский склад и Amazon FBA (без партнёра, магазинов и склада запчастей) и недельный лист Poland-Spain.'
 WHERE table_name = 'kabinet_data.reorder_recommendations';
UPDATE kabinet_data.data_source_origins SET our_refresh =
 'Kabinet - Shipment Facts 16:30 Kyiv (SendCloud 09:11)'
 WHERE table_name = 'kabinet_data.shipment_facts';
UPDATE kabinet_data.data_source_origins SET platform_source =
 'Amazon Ads API (SP, SD) плюс разнос SB по ASIN',
 darina_reason =
 'расход совпадает до евро — SB берём из того же разноса по ASIN, что и Power BI; продажи с рекламы в этой таблице только SP и SD (строка = SKU), поэтому ACOS и TACOS считаются по ads_market_daily, где SB есть'
 WHERE table_name = 'kabinet_data.ads_spend';
UPDATE kabinet_data.data_source_origins SET platform_source =
 'отчёт Sales & Traffic (Seller Central) через общее сырьё dnipro_m',
 our_refresh =
 'реплика Kabinet - Sales & Traffic Replica — по обновлению сырья Sales & Traffic (отчёт с 07:00 Kyiv), запасной запуск 11:00',
 note = 'Мы вторые в очереди: свежесть равна прогону загрузчика сырья Sales & Traffic.',
 darina_method =
 'отчёт Sales & Traffic по ASIN × SKU × день (джоба «Sales & Traffic Report for Tableau», окно 10 дней), orderedProductSales с НДС по дате заказа.',
 darina_reason =
 'Power BI и Кабинет читают одни и те же таблицы сырья — это сверка трубопровода, а не два независимых счёта'
 WHERE table_name = 'kabinet_data.sales_traffic_daily';
UPDATE kabinet_data.data_source_origins SET darina_reason =
 'одна и та же сетка и тот же вес состава; разница только в доле FBM — в Power BI признак листинга, у нас фактические FBM-заказы (сентябрь: доставка 3 914 против 3 934 €)'
 WHERE table_name = 'kabinet_data.economics_logistics';

-- ── «Справочники → Алерты»: описание типа ──
UPDATE kabinet_data.incident_types SET description =
 'Наши цифры расходятся с Power BI или с settlement Amazon сверх допуска, и разложение по слагаемым причину не нашло. Объяснимые расхождения (разная база штук, дата себестоимости, сдвиг по дням) сюда не попадают — они подписаны в «Сверке» паспорта.'
 WHERE incident_type = 'reconciliation';

-- ── «Справочники → Подпитка»: примечания связей ──
UPDATE kabinet_data.supply_chains SET note =
 'PL→ES 8 дней + до 5 дней ожидания рейса (машина в Мадрид по средам); снабжение, 15.09.2026'
 WHERE id = 2;
UPDATE kabinet_data.supply_chains SET note =
 'UA→PL 14 дней; снабжение, 15.09.2026. Плечо не считаем сами: оно ведётся в листе Poland-Spain'
 WHERE id = 50;

-- ── сверка: подпись источника. Сторож строит токен инцидента из неё ([RECON:<источник>/…]), поэтому
-- переименовываем разом строки сверки, открытые инциденты и ключи задач ClickUp — иначе сторож закрыл бы
-- четыре инцидента LM и завёл те же четыре заново, а ClickUp Sync — четыре новые задачи вместо старых.
UPDATE kabinet_data.reconciliation_results SET against = 'Power BI' WHERE against = 'витрина Дарины';
UPDATE kabinet_data.incidents
   SET message = replace(message, '[RECON:витрина Дарины/', '[RECON:Power BI/')
 WHERE incident_type = 'reconciliation' AND message LIKE '[RECON:витрина Дарины/%';
UPDATE kabinet_data.clickup_tasks
   SET dedup_key = replace(dedup_key, 'RECON:витрина Дарины/', 'RECON:Power BI/')
 WHERE dedup_key LIKE 'reconciliation:RECON:витрина Дарины/%';

-- ── служебные пояснения: на экран не выводятся, но читаются при разборе — тем же правилом ──
UPDATE kabinet_data.data_freshness_rules SET comment =
 'Google Sheet Poland-Spain. 1-2×/нед вручную, порог 240h (10д). С 27.09.2026 — ЗАПАСНОЙ источник плана снабжения: основной — заказы Odoo, берётся максимум из двух.'
 WHERE table_name = 'kabinet_data.supply_poland_spain';
UPDATE kabinet_data.data_freshness_rules SET comment =
 'Реклама SP (джобы Amazon Ads 09:30+10:20). Если протухло — ads_spend не обновится. 72h = 3 дня с учётом лага Amazon.'
 WHERE table_name = 'dnipro_m.dnipro_m.raw_amazon_ads_sp_advertised_product_es';
UPDATE kabinet_data.job_health_rules SET note = 'реплика listing_data.listing_snapshots → dnipro_m.raw_amazon_listing_snapshots (общее сырьё)'
 WHERE job_name = 'Listing Suite - Snapshots Replica';
UPDATE kabinet_data.job_health_rules SET note = 'Заказы Odoo — основной источник плана снабжения в автозаказе; лист Poland-Spain запасной'
 WHERE job_name = 'Kabinet - Odoo Purchase Orders';
UPDATE kabinet_data.job_health_rules SET note = 'Сверка с Power BI и settlement; результат в паспорте, колонка «Сверка»'
 WHERE job_name = 'Kabinet - Reconciliation';
UPDATE kabinet_data.job_health_rules SET note = 'Недельный отчёт в Telegram в формате еженедельного отчёта продаж: план/факт месяца, неделя к неделе, реклама, конверсия'
 WHERE job_name = 'Kabinet - Weekly Report';
UPDATE kabinet_data.job_health_rules SET note = 'Реплика Sales & Traffic из общего сырья dnipro_m; запуск триггером по таблицам, не по часам',
       schedule_description = 'по изменению таблиц сырья Sales & Traffic (отчёт с 07:00 Kyiv); запасной 11:00'
 WHERE job_name = 'Kabinet - Sales & Traffic Replica';
UPDATE kabinet_data.reorder_params SET note = 'доля отсева на карантине Piasecznie, %; уточняется у снабжения (15.09.2026: ноль)'
 WHERE key = 'quarantine_reject_pct';
UPDATE kabinet_data.reorder_params SET note = 'Упаковка, € за проданную единицу, все каналы (правило витрины продаж, как в Power BI)'
 WHERE key = 'packing_cost_per_unit';
UPDATE kabinet_data.reorder_params SET note = 'Окно сверки с Power BI'
 WHERE key = 'recon_window_days';
UPDATE kabinet_data.reorder_params SET note = 'Сверка комиссий по слагаемым: ставка за штуку у нас и в Power BI должна совпадать в пределах этого процента — тогда разница в сумме объясняется базой штук, а не ошибкой'
 WHERE key = 'recon_rate_tolerance_pct';
UPDATE kabinet_data.reorder_params SET note = 'Сверка себестоимости: расхождение цены за единицу в пределах этого процента объясняется датой цены (в Power BI на месяц продажи, у нас последний срез)'
 WHERE key = 'recon_unit_cost_tolerance_pct';

-- проверка: в видимых текстах имён не осталось
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM kabinet_data.data_source_origins
   WHERE concat_ws(' ', platform_source, platform_refresh, our_refresh, note, reconcile_with, reconcile_result,
                   darina_method, darina_reason) ~* 'Дарин|Darin';
  IF n > 0 THEN RAISE EXCEPTION 'в паспорте осталось имён: %', n; END IF;
  SELECT count(*) INTO n FROM kabinet_data.incident_types WHERE concat_ws(' ', title, description) ~* 'Дарин|Darin';
  IF n > 0 THEN RAISE EXCEPTION 'в типах алертов осталось имён: %', n; END IF;
END $$;
COMMIT;
