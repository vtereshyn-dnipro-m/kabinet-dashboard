-- 17.09.2026. Пулы по ТЗ 004 v0.2: одна страна на пул, минимум два участника, исключения для Pan-EU нет.
-- Черновики от 14.09 были собраны по складам (Amazon EU на 9 стран, ManoMano ES+FR, три одиночных) —
-- ошибка при заведении; в расчётах и прогнозах не участвовали (coverage_norms.pool_id пуст,
-- forecast_documents по пулам нет), внешних ссылок на pools нет → по §10 удаляются физически.
BEGIN;

DELETE FROM kabinet_data.pool_members WHERE pool_id IN (SELECT id FROM kabinet_data.pools WHERE name LIKE '%(черновик)%');
DELETE FROM kabinet_data.pools WHERE name LIKE '%(черновик)%';

INSERT INTO kabinet_data.pools (name, comment) VALUES
 ('Spain',  'ТЗ 004 v0.2 §2: одна страна на пул. AMZ-ES + LM-ES + MM-ES + CF-ES. Решение владельца 17.09.2026'),
 ('France', 'ТЗ 004 v0.2 §2: одна страна на пул. AMZ-FR + MM-FR. Решение владельца 17.09.2026');

INSERT INTO kabinet_data.pool_members (pool_id, marketplace_id, valid_from)
SELECT p.id, m.id, current_date
FROM kabinet_data.pools p
JOIN kabinet_data.marketplaces_new m ON (p.name = 'Spain'  AND m.code IN ('AMZ-ES', 'LM-ES', 'MM-ES', 'CF-ES'))
                                     OR (p.name = 'France' AND m.code IN ('AMZ-FR', 'MM-FR'));

COMMIT;

-- Контроль §2: страна участников едина; §9: действующих связей ≥ 2
SELECT p.id, p.name, count(*) AS members, string_agg(m.code, ', ' ORDER BY m.code) AS codes,
       count(DISTINCT m.country_alpha2) AS countries
FROM kabinet_data.pools p JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id
WHERE pm.valid_to IS NULL OR pm.valid_to >= current_date GROUP BY 1, 2 ORDER BY 1;
