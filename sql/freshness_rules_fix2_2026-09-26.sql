-- Разбор двух открытых инцидентов 26.09.2026. Оба оказались про правила, а не про данные.
--
-- 1. kabinet_data.raw_lm_orders — ЛОЖНАЯ ТРЕВОГА. Правило на реплику считало «синком» колонку
--    created_date, то есть дату последнего ЗАКАЗА, с порогом 26 ч. На Leroy Merlin 1–11 заказов в
--    день и тихие дни бывают (25.09 и 15.09 — ни одного), поэтому инцидент загорался каждый раз,
--    когда сутки прошли без заказа, хотя загрузчик отработал. Соседние правила на те же реплики
--    (raw_lm_offers, raw_lm_order_lines) считают синк по loaded_at — этому надо было так же.
--    «Нет заказов» и «загрузчик встал» — разные события, и путать их нельзя: ложные тревоги
--    приучают не читать алерты.
UPDATE kabinet_data.data_freshness_rules
   SET date_column = 'loaded_at', max_age_hours = 26,
       content_date_column = 'created_date', max_content_age_hours = 72,
       comment = 'Реплика UC→LB, LM Orders Loader 09:30/15:30 Kyiv. Синк — loaded_at; created_date как содержимое с порогом 72 ч: на LM бывают сутки без заказов.',
       updated_at = now()
 WHERE table_name = 'kabinet_data.raw_lm_orders';

-- 2. Возвраты ES — таблица Дарины мертва с 27.05.2026 (118 строк, джобы, которая её пишет, в
--    воркспейсе нет вообще), а сами возвраты грузит наш Kabinet - Returns Loader (06:00) в
--    kabinet_data.raw_amazon_returns: по ES последний возврат 25.09, 117 строк, и на сырьё в UC
--    есть рабочее правило. Источник заменён ещё в августе — инцидент от 09.08 закрыт вручную
--    именно с этой формулировкой, но правило осталось активным и воспроизводило тревогу каждый
--    месяц. Выключаем: мёртвая таблица чужого загрузчика не должна изображать проверку.
UPDATE kabinet_data.data_freshness_rules
   SET is_active = false, updated_at = now(),
       comment = 'Выключено 26.09.2026: таблица не обновляется с 27.05, пишущей джобы нет. Возвраты ES грузит Kabinet - Returns Loader в kabinet_data.raw_amazon_returns (правило на dnipro_m.kabinet_data.raw_amazon_returns).'
 WHERE table_name = 'dnipro_m.dnipro_m.raw_amazon_seller_central_returns_es';
