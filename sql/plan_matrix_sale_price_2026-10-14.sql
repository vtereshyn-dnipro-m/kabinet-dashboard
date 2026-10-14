-- Plan Matrix: порог контроля «цена SP-API против снимка ScrapingDog» (решение владельца 14.10.2026).
-- Выполнять после мержа PR, до прогона ноутбука с ячейкой Listings Items. Сырьё dnipro_m.raw_amazon_listing_offers
-- (Unity Catalog) создаёт сама джоба при первом прогоне.
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('plan_price_scrape_diff_pct', 15,
  'Plan Matrix: контроль — цена Amazon из SP-API и последний снимок ScrapingDog расходятся больше чем на этот %; '
  'ноутбук печатает число таких пар и первые десять', now())
ON CONFLICT (key) DO NOTHING;
SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'plan_price_scrape_diff_pct';
