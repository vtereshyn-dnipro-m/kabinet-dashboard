-- 17.09.2026: пороги инцидентов out_of_stock / low_stock — из БД, не константами в Stock Loader.
-- Наблюдение только за SKU с продажами на канале за окно (решение владельца): выключенные
-- офферы ManoMano с вечным нулём инцидентами больше не считаются, а SKU, закончившийся
-- в FBA полностью, из проверки не выпадает.
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
  ('low_stock_threshold', '3',
   'low_stock при остатке 1..N на складе канала; было константой LOW_STOCK_THRESHOLD в Stock Loader', now()),
  ('stock_incident_sales_window_days', '90',
   'out_of_stock/low_stock только по SKU с продажами на канале за N дней (Amazon — через FBA, ManoMano — заказы страны); плюс всё, что физически лежит в FBA', now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();
