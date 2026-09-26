-- ТЗ 010 сценарии 12 и 21: пересоздание прогнозов после изменения состава пула
-- и единое действие «Заменить прогнозы после изменения пула».
--
-- Ключевое решение: индикатор «Требуется пересоздание» НЕ хранится, а считается — вью сравнивает
-- состав пула, сохранённый в документе на момент проведения (`pool_snapshot`), с действующим
-- составом `pool_members`. Хранимый флаг пришлось бы ставить всем, кто правит состав, и он бы
-- расходился с действительностью: состав можно поменять и из SQL, минуя экран справочника, а
-- снять флаг забыть. Расчётный индикатор гаснет сам ровно тогда, когда причина ушла: после
-- успешной общей замены старые записи перестают быть действующими, и документ выпадает из вью.

-- ── Индикатор: расхождение состава действующего прогноза пула с составом пула ────────────────
CREATE OR REPLACE VIEW kabinet_data.v_forecast_pool_drift AS
WITH eff AS (          -- только документы, у которых есть ДЕЙСТВУЮЩИЕ записи: историю не трогаем
    SELECT d.id AS document_id, d.number, d.object_id AS pool_id, d.pool_snapshot, d.pool_snapshot_date,
           count(*) AS current_rows,
           count(*) FILTER (WHERE r.month >= date_trunc('month', current_date)) AS rows_ahead,
           min(r.month) FILTER (WHERE r.month >= date_trunc('month', current_date)) AS first_month_ahead,
           max(r.month) AS last_month
    FROM kabinet_data.forecast_documents d
    JOIN kabinet_data.forecast_register r ON r.document_id = d.id
                                         AND r.record_type = 'sales' AND r.is_current
    WHERE d.object_type = 'pool'
    GROUP BY 1, 2, 3, 4, 5
), snap AS (
    SELECT e.*, ARRAY(SELECT DISTINCT x::int FROM jsonb_array_elements_text(e.pool_snapshot) AS t(x) ORDER BY 1) AS snapshot_ids
    FROM eff e
), members AS (
    SELECT pool_id, ARRAY(SELECT DISTINCT m2.marketplace_id FROM kabinet_data.pool_members m2
                          WHERE m2.pool_id = m.pool_id AND m2.valid_from <= current_date
                            AND (m2.valid_to IS NULL OR m2.valid_to > current_date)
                          ORDER BY 1) AS current_ids
    FROM kabinet_data.pool_members m GROUP BY pool_id
)
SELECT s.document_id, s.number, s.pool_id, p.name AS pool_name,
       s.snapshot_ids, coalesce(mb.current_ids, '{}'::int[]) AS current_ids,
       ARRAY(SELECT x FROM unnest(coalesce(mb.current_ids, '{}'::int[])) AS t(x)
             WHERE NOT x = ANY(s.snapshot_ids) ORDER BY 1) AS added_ids,
       ARRAY(SELECT x FROM unnest(s.snapshot_ids) AS t(x)
             WHERE NOT x = ANY(coalesce(mb.current_ids, '{}'::int[])) ORDER BY 1) AS removed_ids,
       coalesce(array_length(mb.current_ids, 1), 0) = 0 AS disbanded,
       s.current_rows, s.rows_ahead, s.first_month_ahead, s.last_month, s.pool_snapshot_date
FROM snap s
JOIN kabinet_data.pools p ON p.id = s.pool_id
LEFT JOIN members mb ON mb.pool_id = s.pool_id
WHERE coalesce(mb.current_ids, '{}'::int[]) <> s.snapshot_ids;

-- ── Единое действие: журнал выполненных общих замен ──────────────────────────────────────────
-- Пишется в момент выполнения, а не как черновик: до выполнения выбор живёт на экране, и
-- полусохранённая операция только запутала бы — по ТЗ либо переключается всё сразу, либо ничего.
CREATE TABLE IF NOT EXISTS kabinet_data.forecast_replacements (
    id              bigserial PRIMARY KEY,
    pool_id         int         NOT NULL REFERENCES kabinet_data.pools(id),
    reason          text        NOT NULL,                  -- причина изменения состава, ТЗ 010 §12
    change_summary  text,                                  -- что именно изменилось на момент замены
    documents       int         NOT NULL DEFAULT 0,        -- сколько новых документов проведено
    superseded_rows int         NOT NULL DEFAULT 0,        -- сколько записей ушло в «Заменено новой версией»
    terminated_rows int         NOT NULL DEFAULT 0,        -- сколько прекращено без нового прогноза
    actor           text        NOT NULL,
    executed_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.forecast_replacements IS
    'ТЗ 010 §21: выполненные общие замены прогнозов после изменения состава пула. Одна строка — одно успешное действие.';

-- Что вошло в операцию: новый документ на объект либо прекращение без нового прогноза
CREATE TABLE IF NOT EXISTS kabinet_data.forecast_replacement_items (
    id                 bigserial PRIMARY KEY,
    replacement_id     bigint  NOT NULL REFERENCES kabinet_data.forecast_replacements(id) ON DELETE CASCADE,
    kind               text    NOT NULL CHECK (kind IN ('document', 'termination')),
    object_type        text    NOT NULL CHECK (object_type IN ('marketplace', 'pool')),
    object_id          int     NOT NULL,
    marketplace_id     int,                                -- затронутый маркетплейс, если речь о нём
    new_document_id    int     REFERENCES kabinet_data.forecast_documents(id),
    termination_reason text,                               -- для деактивированного маркетплейса, §21
    rows_affected      int     NOT NULL DEFAULT 0,
    CONSTRAINT repl_item_shape CHECK (
        (kind = 'document'    AND new_document_id IS NOT NULL AND termination_reason IS NULL) OR
        (kind = 'termination' AND new_document_id IS NULL     AND termination_reason IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS forecast_replacement_items_repl_idx
    ON kabinet_data.forecast_replacement_items (replacement_id);
COMMENT ON COLUMN kabinet_data.forecast_replacement_items.termination_reason IS
    'ТЗ 010 §21: у деактивированного маркетплейса нового прогноза нет — ссылка на несуществующий документ не нужна, нужна причина.';

-- Гранты: приложение пишет операцию с экрана, джобы читают
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.v_forecast_pool_drift TO claude_code_ro;
GRANT SELECT, INSERT ON kabinet_data.forecast_replacements, kabinet_data.forecast_replacement_items
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.forecast_replacements_id_seq,
    kabinet_data.forecast_replacement_items_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.forecast_replacements, kabinet_data.forecast_replacement_items
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", claude_code_ro;

SELECT 'дрейф состава сейчас' AS what, count(*) FROM kabinet_data.v_forecast_pool_drift;
