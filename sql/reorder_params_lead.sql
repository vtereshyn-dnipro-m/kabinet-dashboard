-- 15.09.2026. Срок поставки в автозаказе больше не константа LEAD_TIME_DAYS = 30 (догадка).
-- Плечи PL и UA считаются из supply_chains (Piasecznie→Мадрид 8 + ожидание рейса 5 + Мадрид→FBA ES 3;
-- Тернополь→Piasecznie 14 сверху). У поставщика (Китай) маршрута в справочнике нет — срок остаётся
-- оценкой, но лежит здесь, а не в коде, и помечен как оценка в reorder_recommendations.lead_source.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
 ('safety_days', 14, 'страховой запас, дней; было константой SAFETY_DAYS в Stock Loader'),
 ('supplier_lead_days', 30, 'ОЦЕНКА: срок от поставщика (Китай) до Мадрида; маршрута в supply_chains нет, уточнить у снабжения')
ON CONFLICT (key) DO NOTHING;
SELECT key, value, note FROM kabinet_data.reorder_params ORDER BY key;
