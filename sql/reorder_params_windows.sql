-- 19.09.2026: окна автозаказа — в reorder_params, не константами в Stock Loader (правило «пороги живут в БД»).
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
  ('velocity_window_days', '30', 'окно спроса автозаказа: скорость = продажи по всем каналам за N дней / N', now()),
  ('cover_target_days', '60', 'горизонт автозаказа: заказываем столько, чтобы хватило на N дней вперёд', now())
ON CONFLICT (key) DO UPDATE SET note = EXCLUDED.note, updated_at = now();
-- снимок расчёта до правки — для сравнения «было / стало»
CREATE TABLE IF NOT EXISTS kabinet_data.reorder_recommendations_before_20260919 AS
SELECT * FROM kabinet_data.reorder_recommendations WHERE calc_date = '2026-09-19';
GRANT SELECT ON kabinet_data.reorder_recommendations_before_20260919 TO claude_code_ro;
SELECT count(*) FROM kabinet_data.reorder_recommendations_before_20260919;
