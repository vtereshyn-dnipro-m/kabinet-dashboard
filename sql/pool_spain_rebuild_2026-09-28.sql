-- Перестройка пулов Испании (решение Ярослава, 28.09.2026).
--
-- Было: пул Spain (id 6) = AMZ-ES + LM-ES + MM-ES + CF-ES.
-- Стало: Spain распускается, три канала Mirakl собираются в свой пул «Spain Marketplaces»,
-- на него ложится план из листа `Plan_Leroy/ManoMano/Carrefour_ES` (разбивки по каналам нет
-- и не будет — Марко даёт одной суммой). AMZ-ES остаётся со своим планом из `Plan_ES_Amazon`.
--
-- ВНИМАНИЕ, операция ОДНОСТОРОННЯЯ. На `pool_members` висит `UNIQUE (pool_id, marketplace_id)`
-- без даты, поэтому маркетплейс, вышедший из пула, вернуться в НЕГО ЖЕ не может никогда:
-- историческая строка занимает ключ (проверено 28.09.2026 — «duplicate key value violates
-- unique constraint»). Вернуть LM/MM/CF в Spain после этого можно будет только через владельца,
-- заменой ограничения. Поэтому — только после согласования.
--
-- Что НЕ меняется от роспуска Spain: действующих записей прогноза у пула 6 нет (4 документа и
-- 5 833 строки реестра, все superseded с 18.09.2026), правил алертов и нормативов на него нет,
-- в покрытии каналов Mirakl нет вовсе. Проверено симуляцией с откатом: блок «План месяца»
-- до и после совпадает до штуки.
--
-- Период членства полуоткрытый [valid_from, valid_to): valid_to — первый день БЕЗ пула,
-- поэтому закрытие и вступление в новый пул одним днём пересечением не считаются, и триггер
-- `pool_member_single_pool` это пропускает (проверено на живой таблице, случай 5).

BEGIN;

-- 1. Распускаем Spain: закрываем все действующие участия сегодняшним днём.
--    Строки не удаляем — история пула нужна, чтобы прежние документы прогноза читались (ТЗ 004 §11).
UPDATE kabinet_data.pool_members
   SET valid_to = CURRENT_DATE
 WHERE pool_id = 6 AND (valid_to IS NULL OR valid_to > CURRENT_DATE);

-- 2. Новый пул из трёх каналов Mirakl. Все три — Испания, участников три: ТЗ 004 соблюдено.
INSERT INTO kabinet_data.pools (name)
SELECT 'Spain Marketplaces'
 WHERE NOT EXISTS (SELECT 1 FROM kabinet_data.pools WHERE name = 'Spain Marketplaces');

INSERT INTO kabinet_data.pool_members (pool_id, marketplace_id, valid_from)
SELECT p.id, m.id, CURRENT_DATE
  FROM kabinet_data.pools p, kabinet_data.marketplaces_new m
 WHERE p.name = 'Spain Marketplaces'
   AND m.code IN ('LM-ES', 'MM-ES', 'CF-ES')
   AND NOT EXISTS (SELECT 1 FROM kabinet_data.pool_members x
                    WHERE x.pool_id = p.id AND x.marketplace_id = m.id);

-- 3. Проверка глазами до COMMIT: у Spain не должно остаться действующих участий,
--    у нового пула должно быть ровно три.
SELECT p.id, p.name,
       count(*) FILTER (WHERE pm.valid_to IS NULL OR pm.valid_to > CURRENT_DATE) AS действующих,
       count(*) AS всего_в_истории,
       string_agg(m.code, ', ' ORDER BY m.code)
         FILTER (WHERE pm.valid_to IS NULL OR pm.valid_to > CURRENT_DATE) AS состав
  FROM kabinet_data.pools p
  LEFT JOIN kabinet_data.pool_members pm ON pm.pool_id = p.id
  LEFT JOIN kabinet_data.marketplaces_new m ON m.id = pm.marketplace_id
 GROUP BY p.id, p.name ORDER BY p.id;

COMMIT;
