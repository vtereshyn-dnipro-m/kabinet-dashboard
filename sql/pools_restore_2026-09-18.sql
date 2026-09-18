-- 18.09.2026: пулы Spain (6) и France (7) по ТЗ 004 исчезли из pools / pool_members (по статистике
-- Postgres — удалены, не нами; вероятно, через вкладку «Пулы» при тестировании). Восстанавливаем
-- с прежними id: на них ссылаются исторические документы прогноза (forecast_documents 17.09).
INSERT INTO kabinet_data.pools (id, name, comment) VALUES
  (6, 'Spain',  'ТЗ 004: все marketplace Испании — AMZ-ES, LM-ES, MM-ES, CF-ES. Восстановлен 18.09.2026 после удаления'),
  (7, 'France', 'ТЗ 004: все marketplace Франции — AMZ-FR, MM-FR. Восстановлен 18.09.2026 после удаления')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, comment = EXCLUDED.comment, updated_at = now();
-- setval на pools_id_seq недоступен rw (последовательность владельца); явные id 6 и 7 ниже текущего значения последовательности не мешают
INSERT INTO kabinet_data.pool_members (pool_id, marketplace_id, valid_from)
SELECT p.pool_id, m.id, DATE '2026-09-17'
FROM (VALUES (6, 'AMZ-ES'), (6, 'LM-ES'), (6, 'MM-ES'), (6, 'CF-ES'), (7, 'AMZ-FR'), (7, 'MM-FR')) AS p(pool_id, code)
JOIN kabinet_data.marketplaces_new m ON m.code = p.code
WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.pool_members x WHERE x.pool_id = p.pool_id AND x.marketplace_id = m.id AND x.valid_to IS NULL);
SELECT p.id, p.name, string_agg(m.code, ' + ' ORDER BY m.code) AS members FROM kabinet_data.pools p
JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id GROUP BY 1,2 ORDER BY 1;
