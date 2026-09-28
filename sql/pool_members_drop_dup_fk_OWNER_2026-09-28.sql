-- Дубль внешнего ключа на kabinet_data.pool_members.pool_id (замечено владельцем 28.09.2026).
--
-- На колонку `pool_id` висят ДВА одинаковых по поведению ключа:
--   pool_members_pool_id_fkey   FOREIGN KEY (pool_id) REFERENCES kabinet_data.pools(id)
--   fk_pool_members_pool        FOREIGN KEY (pool_id) REFERENCES kabinet_data.pools(id)
-- Сверено по системному каталогу: одна и та же колонка (conkey = {2}), одинаковое поведение
-- при обновлении и удалении (NO ACTION у обоих), оба не отложенные, оба опираются на
-- `pools_pkey`. То есть это не два разных правила, а одно, записанное дважды.
--
-- Вреда от дубля нет, кроме двойной проверки на каждой вставке и лишней строки в описании
-- таблицы, — но при чтении схемы он читается как «тут что-то особенное», и на это тратят время.
--
-- Снимаем `fk_pool_members_pool`, а не второй, по двум причинам: его нет ни в одном файле
-- репозитория (то есть заведён он вне наших скриптов, и ничто его не воссоздаст), а
-- `pool_members_pool_id_fkey` — имя, которое Postgres даёт сам по шаблону `таблица_колонка_fkey`,
-- и рядом на соседней колонке лежит `pool_members_marketplace_id_fkey` того же вида.
--
-- Связь «участник → пул» после этого никуда не девается: оставшийся ключ её и держит.

BEGIN;

ALTER TABLE kabinet_data.pool_members
    DROP CONSTRAINT IF EXISTS fk_pool_members_pool;

-- Проверка глазами до COMMIT: должно остаться ровно три ограничения —
-- первичный ключ и по одному внешнему на pool_id и marketplace_id.
SELECT conname, pg_get_constraintdef(oid) AS определение
  FROM pg_constraint WHERE conrelid = 'kabinet_data.pool_members'::regclass ORDER BY conname;

COMMIT;
