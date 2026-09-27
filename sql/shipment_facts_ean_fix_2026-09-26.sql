-- Исправление сборки факта отгрузки: позиции посылок SendCloud — это EAN, а не наш артикул.
--
-- Найдено 26.09.2026 при переводе план-факта на дату отгрузки: в `raw_sendcloud_parcel_items.sku`
-- лежит тринадцатизначный штрихкод (`4823102300610`) — 5 049 строк из 5 149. Выглядит как
-- «цифровой SKU» и по формату похож на наши коды, поэтому первая версия сборки приняла его за
-- артикул. Следствие: факт по SKU у Amazon MFN бессмыслен, `norm_sku` — штрихкод, и с планом,
-- который ведётся по артикулам, такие строки не стыкуются вовсе.
--
-- Состав MFN теперь берётся из заказа (`orders_history`: артикул, количество, цена, рынок), а
-- SendCloud остаётся источником одной только ДАТЫ — тем же способом, что уже работает у Mirakl.
-- Все 4 105 амазоновских номеров SendCloud нашлись в `orders_history`, так что потерь нет.
--
-- Старые строки надо снять: у них другой ключ (`SC-<parcel_id>` + EAN), и рядом с новыми
-- (`<номер заказа>` + артикул) они дали бы двойной счёт. Данные восстанавливаемы — сборка
-- строит факт из источников заново каждым прогоном.
DELETE FROM kabinet_data.shipment_facts
WHERE channel = 'AMZ' AND source = 'sendcloud' AND shipment_ref LIKE 'SC-%';

-- Настройки загрузчика отгрузок: добор истории частями и предел ожидания отчёта.
-- Окно в полгода Amazon собирает дольше получаса — прогон 26.09.2026 в 30 минут не уложился,
-- поэтому историю добираем месячными кусками, а предел ожидания стал настройкой.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
 ('fba_shipments_window_end_days', 0,
  'Kabinet - FBA Shipments Loader: конец окна, суток назад. 0 — до сегодня. Поднимают вместе с window_days, чтобы добрать историю куском.'),
 ('fba_shipments_poll_minutes', 45,
  'Kabinet - FBA Shipments Loader: сколько ждать готовности отчёта. Большое окно Amazon собирает дольше суточного.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();

SELECT source, count(*) AS строк,
       count(*) FILTER (WHERE sku ~ '^[0-9]{13}$') AS с_штрихкодом
FROM kabinet_data.shipment_facts GROUP BY 1 ORDER BY 2 DESC;
