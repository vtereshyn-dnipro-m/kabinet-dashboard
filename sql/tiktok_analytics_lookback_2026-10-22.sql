-- TikTok Shop, аналитика: окно истории API у товаров, SKU, видео и эфиров (22.10.2026). Проба: 180 дней назад
-- отдаётся, 181 — код 28001022 «вне окна истории этой версии API»; у магазина окно не меньше года. Без этой настройки
-- первый прогон с tiktok_history_days = 200 падал на 05.04. Применяет владелец под своей учёткой, Lakebase Кабинета.
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('tiktok_analytics_lookback_days', 180, 'TikTok Shop аналитика: окно истории API у товаров, SKU, видео и эфиров (сутки) — глубже загрузчик не идёт', now())
ON CONFLICT (key) DO NOTHING;
