-- Пулы по ТЗ 004 — ЧЕРНОВИК для подтверждения Ярославом. Lakebase, kabinet_data.
--
-- Пул — витрины, которые кормятся из одного запаса и прогнозируются вместе.
-- Из данных решение не выводится, но структура очевидна:
--   Amazon EU — один запас FBA на континентальные страны (pan-EU), один пул.
--   Amazon UK — после Brexit вне общеевропейского распределения, отдельно.
--   Каждый Mirakl-канал — со своего склада, отдельный пул.
-- Пометка «черновик» в названии и комментарии: страница пулов покажет её
-- как есть, снять — переименовать после подтверждения.
--
-- Требует INSERT на pools и pool_members; у claude_code_rw их нет.

BEGIN;

INSERT INTO kabinet_data.pools (name, comment) VALUES
  ('Amazon EU (черновик)',        'Черновик 14.09.2026: один запас FBA на ES, DE, FR, IT, NL, BE, SE, IE, PL. Подтвердить или разбить — Ярослав.'),
  ('Amazon UK (черновик)',        'Черновик 14.09.2026: Британия вне pan-EU распределения, отдельный запас.'),
  ('Leroy Merlin ES (черновик)',  'Черновик 14.09.2026: Mirakl, отгрузка со своего склада.'),
  ('ManoMano (черновик)',         'Черновик 14.09.2026: ES и FR под одним аккаунтом и складом.'),
  ('Carrefour ES (черновик)',     'Черновик 14.09.2026: Mirakl, отгрузка со своего склада.');

INSERT INTO kabinet_data.pool_members (pool_id, marketplace_id, valid_from)
SELECT p.id, m.id, current_date
FROM kabinet_data.pools p
JOIN kabinet_data.marketplaces m ON
     (p.name = 'Amazon EU (черновик)'       AND m.channel = 'Amazon' AND m.country <> 'GB')
  OR (p.name = 'Amazon UK (черновик)'       AND m.channel = 'Amazon' AND m.country = 'GB')
  OR (p.name = 'Leroy Merlin ES (черновик)' AND m.channel = 'Leroy Merlin')
  OR (p.name = 'ManoMano (черновик)'        AND m.channel = 'ManoMano')
  OR (p.name = 'Carrefour ES (черновик)'    AND m.channel = 'Carrefour')
WHERE p.name LIKE '%(черновик)';

COMMIT;

SELECT p.name, count(pm.marketplace_id) AS vitrin, string_agg(m.code, ', ' ORDER BY m.code) AS sostav
FROM kabinet_data.pools p LEFT JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id
LEFT JOIN kabinet_data.marketplaces m ON m.id = pm.marketplace_id
GROUP BY p.id, p.name ORDER BY p.id;
