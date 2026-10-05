-- Паспорт данных: колонка «У Дарины» (решение владельца 05.10.2026) — для показателей, которые есть и в её
-- витрине dnipro_m.v_all_marketplaces_spiderweb_report. Откуда она берёт и как считает — по SQL-определению
-- её витрины и вложенных (v_amazon_spiderweb_report, v_amazon_sales_fees_cogs_*, v_products_amazon_ads_*,
-- v_lm/mm/cf_spiderweb_report), прочитанному 05.10.2026; итог — одно из четырёх слов и одна фраза «почему».
-- Пусто = показателя в её витрине нет; паспорт пишет это прочерком, а не «совпадает».
ALTER TABLE kabinet_data.data_source_origins
    ADD COLUMN IF NOT EXISTS darina_method  text,
    ADD COLUMN IF NOT EXISTS darina_verdict text,
    ADD COLUMN IF NOT EXISTS darina_reason  text;
ALTER TABLE kabinet_data.data_source_origins DROP CONSTRAINT IF EXISTS data_source_origins_darina_verdict_check;
ALTER TABLE kabinet_data.data_source_origins ADD CONSTRAINT data_source_origins_darina_verdict_check
    CHECK (darina_verdict IS NULL OR darina_verdict IN ('same', 'ours_better', 'hers_better', 'different'));

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'Amazon: заказанные продажи Sales & Traffic по дате заказа, без НДС — делением на ставку страны; '
               || 'комиссия — модель: реферальный % из оценки Amazon × цена, плюс 3 % от него (digital) и FBA-сбор из '
               || 'оценки сборов; себестоимость — срез на месяц продажи, у набора по составу; возвраты — из settlement, '
               || 'с возвратом себестоимости всех возвращённых штук. Mirakl: строки заказов по дате заказа, отменённые '
               || 'исключены, комиссия из заказа.',
  darina_verdict = 'different',
  darina_reason = 'у неё модельные комиссии на все заказанные штуки и выручка до промо, у нас фактическая выплата '
               || 'Amazon после возвратов, промо и удержаний; себестоимость точнее у неё — на месяц продажи, а не '
               || 'последний срез; возврат себестоимости у нас только с годных к продаже',
  updated_at = now()
WHERE table_name = 'kabinet_data.economics_summary';

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'упаковка 1,5 € за проданную штуку; доставка — тарифная сетка raw_delivery_costs (ES / Other) '
               || 'по весу состава SKU на месяц продажи, только у FBM-листингов (признак листинга), иначе 3,71 €.',
  darina_verdict = 'same',
  darina_reason = 'одна и та же сетка и тот же вес состава; разница только в доле FBM — у неё признак листинга, '
               || 'у нас фактические FBM-заказы (сентябрь: доставка 3 914 против 3 934 €)',
  updated_at = now()
WHERE table_name = 'kabinet_data.economics_logistics';

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'расход SP и SD из Ads API по рекламируемому SKU, SB — пересчитанный по ASIN из названия кампании '
               || 'или из покупок (v_amazon_sb_metrics_recalculated_*); продажи с рекламы — sales14d всех трёх типов.',
  darina_verdict = 'same',
  darina_reason = 'расход совпадает до евро — SB мы берём из её же пересчёта; продажи с рекламы у неё включают SB, '
               || 'у нас только SP и SD',
  updated_at = now()
WHERE table_name = 'kabinet_data.ads_spend';

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'отчёт Sales & Traffic по ASIN × SKU × день (её джоба «Sales & Traffic Report for Tableau», '
               || 'окно 10 дней), orderedProductSales с НДС по дате заказа.',
  darina_verdict = 'same',
  darina_reason = 'мы копируем её таблицы — это сверка трубопровода, а не два независимых счёта',
  updated_at = now()
WHERE table_name = 'kabinet_data.sales_traffic_daily';
