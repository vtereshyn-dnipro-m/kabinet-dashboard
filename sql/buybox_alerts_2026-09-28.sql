-- Алерты по Buy Box (28.09.2026): пороги и типы.
--
-- Два РАЗНЫХ типа, а не один. За 05–27.09 по четырём рынкам было восемь «потерь Buy Box»,
-- но семь из них — снимки, где разом нет ни цены, ни продавца, ни наличия: это не конкурент,
-- а нечитанный оффер. В одном алерте они похоронили бы настоящие случаи.
--
-- Рост цены в условие НЕ входит: подорожаний больше 2 % за те же три недели было 58,
-- а совпадений с потерей Buy Box — одно. Цена идёт в текст как объяснение.

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('buybox_snapshot_max_age_hours', '72',
   'По снимку старше этого срока о Buy Box не судим: снимки собираются по 120–130 ASIN в сутки из 287, то есть карточка освежается раз в два дня.'),
  ('snapshot_empty_min_pct', '10',
   'Доля ASIN с нечитанным оффером, с которой заводится инцидент о качестве снимков. Ниже порога это фон, а не событие.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;

INSERT INTO kabinet_data.incident_types (incident_type, title, description, risk) VALUES
  ('buybox_lost', 'Buy Box у нас нет',
   'В последнем снимке витрины кнопку покупки держит другой продавец (чаще всего сам Amazon) или её нет вовсе при живой цене. Рост цены, если он был, назван в тексте.',
   'High'),
  ('listing_snapshot_empty', 'Снимки витрины не читаются',
   'У части ASIN в снимке разом нет цены, продавца и наличия. Это не потеря Buy Box, а качество сбора: по таким карточкам Buy Box не проверяется вовсе.',
   'Low')
ON CONFLICT (incident_type) DO UPDATE
  SET title = COALESCE(kabinet_data.incident_types.title, EXCLUDED.title),
      description = COALESCE(kabinet_data.incident_types.description, EXCLUDED.description),
      risk = COALESCE(kabinet_data.incident_types.risk, EXCLUDED.risk);

SELECT key, value FROM kabinet_data.reorder_params
 WHERE key IN ('buybox_snapshot_max_age_hours','snapshot_empty_min_pct');
SELECT incident_type, title, risk FROM kabinet_data.incident_types
 WHERE incident_type IN ('buybox_lost','listing_snapshot_empty');
