-- Распределение общего мадридского запаса между рынками при нехватке
-- (ТЗ «Остатки» §3, решения владельца 01.10.2026).
--
-- Своего реестра приоритетов НЕ заводим: приоритет уже есть — `warehouse_priorities`
-- по ТЗ 001, «склад × маркетплейс/пул», значения 1..10. Распределение мадридского
-- запаса идёт по приоритетам склада «RS Spain Madrid (Stock)». Пул в приоритете — это
-- приоритет каждого его действующего участника, а внутри пула делим пропорционально
-- спросу.
--
-- Правило раздачи: сначала каждому рынку откладывается гарантированный минимум
-- (`coverage_reserve_min_weeks` недель спроса), потом остаток раздаётся строго по
-- приоритету, а внутри одного приоритета — пропорционально спросу. **Ноль в настройке
-- превращает правило в строгий приоритет**, поэтому два режима задаются одной строкой,
-- а не флагом рядом с числом.
--
-- Минимум откладывается ТОЛЬКО тем рынкам, где товар реально можно купить: если по
-- Buy Box у всех ASIN пары «покупаемых офферов нет» (так на Ирландии и почти на всей
-- Британии), резервировать туда нечего — это отняло бы запас у работающей витрины.

BEGIN;

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('coverage_reserve_min_weeks', 1,
     'Остатки §3: сколько недель спроса откладывается каждому рынку из общего мадридского запаса до раздачи по приоритету. 0 = строгий приоритет.')
ON CONFLICT (key) DO NOTHING;

-- Колонки добавляет сам загрузчик (`ADD COLUMN IF NOT EXISTS` в ячейке записи) — он
-- идёт под владельцем таблицы. Здесь они перечислены, чтобы смысл лежал рядом с
-- правилом, а не только в коде ноутбука.
COMMENT ON COLUMN kabinet_data.coverage_summary.madrid_share_qty IS
    'Сколько штук общего мадридского запаса досталось этому рынку (основание «по темпу продаж»)';
COMMENT ON COLUMN kabinet_data.coverage_summary.madrid_share_reason IS
    'За что досталось: min — гарантированный минимум, priority — по приоритету склада, shared — пропорционально спросу (приоритет не задан), sole — делить не с кем, no_offers — товар на рынке не купить, none — не досталось';
COMMENT ON COLUMN kabinet_data.coverage_summary.madrid_priority IS
    'Приоритет рынка у склада Мадрид из warehouse_priorities; пусто — приоритет не задан';

COMMIT;

-- Проверка глазами: заполнены ли приоритеты у Мадрида и кто в них стоит.
SELECT w.name AS sklad, p.priority, p.target_type,
       COALESCE(m.code, pl.name) AS komu,
       CASE WHEN m.platform_short = 'AMZ' THEN 'участвует в покрытии'
            ELSE 'в покрытии нет — на расчёт не влияет' END AS kommentariy
  FROM kabinet_data.warehouse_priorities p
  JOIN kabinet_data.warehouses w ON w.id = p.warehouse_id
  LEFT JOIN kabinet_data.marketplaces_new m ON p.target_type = 'marketplace' AND m.id = p.target_id
  LEFT JOIN kabinet_data.pools pl ON p.target_type = 'pool' AND pl.id = p.target_id
 WHERE w.name = 'RS Spain Madrid (Stock)'
 ORDER BY p.priority;
