-- ТЗ 011 v0.2 §5, §6, §99, §100, §153: общий логический ключ результата и алерта.
--
-- Зачем. До сих пор инцидент помечался токеном `[DD:объект/набор/компонент/месяц]`, и в нём
-- НЕ БЫЛО `forecast_record_id`. Следствие ровно то, от чего страхует ТЗ: после замены
-- прогноза-источника ошибка по той же четвёрке обновляла ТОТ ЖЕ алерт, хотя по §153 это уже
-- другой ключ, а связь «старый ключ → преемник» (§100) не велась вовсе.
--
-- §99 прямо разрешает разное ТЕКСТОВОЕ представление у результата и алерта («побайтовое
-- совпадение не требуется»), поэтому ключ хранится канонической строкой здесь, а в сообщение
-- инцидента уходит его же составляющие в читаемом виде. Важно не оформление, а то, что обе
-- стороны собираются из одних и тех же шести значений.
--
-- §98 задаёт порядок элементов, если используется JSON: ["DD1", object_type, object_id, month,
-- base_sku_id, composite_sku_id, forecast_record_id]. Берём именно его — тогда §97 («null и
-- строка "null" различаются») выполняется самим форматом, а не договорённостью.

-- Функция объявлена IMMUTABLE осознанно: на вход идут только текст и число, месяц собирается
-- из extract/lpad, а не через to_char, который зависит от DateStyle. При таких входах результат
-- действительно не меняется от настроек сессии — иначе генерируемую колонку на ней строить было
-- бы нельзя.
CREATE OR REPLACE FUNCTION kabinet_data.dependent_source_object_id(
        p_object_type TEXT, p_object_id BIGINT, p_month DATE,
        p_base_sku TEXT, p_composite_sku TEXT, p_forecast_id BIGINT)
RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT json_build_array(
        'DD1',
        p_object_type,
        CASE WHEN p_object_id IS NULL THEN NULL ELSE p_object_id::text END,
        CASE WHEN p_month IS NULL THEN NULL ELSE
             lpad(extract(year FROM p_month)::int::text, 4, '0') || '-' ||
             lpad(extract(month FROM p_month)::int::text, 2, '0') END,
        p_base_sku,                     -- §99: null, если состав не раскрылся и SKU неизвестен
        p_composite_sku,
        CASE WHEN p_forecast_id IS NULL THEN NULL ELSE p_forecast_id::text END
    )::text;
$$;

-- Ключ — ГЕНЕРИРУЕМАЯ колонка, а не заполняемая кодом: иначе она разойдётся с составляющими
-- ровно в тот день, когда кто-то вставит строку мимо функции расчёта. Для строк прогноза продаж
-- ключа нет — он про зависимую потребность.
ALTER TABLE kabinet_data.forecast_register
    ADD COLUMN IF NOT EXISTS source_object_id TEXT
    GENERATED ALWAYS AS (
        CASE WHEN record_type = 'dependent'
             THEN kabinet_data.dependent_source_object_id(
                    object_type, object_id::bigint, month, sku, composite_sku, source_forecast_id::bigint)
        END) STORED;

-- §5, «Для пула»: сохранённый состав пула, по которому считали. Он лежит в документе прогноза
-- (`forecast_documents.pool_snapshot`), поэтому в строке храним ссылку на документ — и тоже
-- генерируемой колонкой, чтобы она не могла указать не на тот документ.
ALTER TABLE kabinet_data.forecast_register
    ADD COLUMN IF NOT EXISTS pool_composition_snapshot_id INTEGER
    GENERATED ALWAYS AS (
        CASE WHEN record_type = 'dependent' AND object_type = 'pool' THEN document_id END) STORED;

CREATE INDEX IF NOT EXISTS forecast_register_source_object_ix
    ON kabinet_data.forecast_register (source_object_id) WHERE record_type = 'dependent';

GRANT SELECT ON kabinet_data.forecast_register TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
