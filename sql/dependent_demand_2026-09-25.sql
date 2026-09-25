-- ТЗ 011: расчёт зависимой потребности базовых SKU из действующих прогнозов составных.
-- Отдельного регистра не нужно: forecast_register изначально спроектирован под это —
-- record_type = 'dependent', composite_sku, component_qty, source_forecast_id, forecast_quantity,
-- calculation_status, calculation_version, source_snapshot_id, error_code/error_text, calculated_at,
-- и частичный уникальный индекс ровно по логическому ключу §6
-- (object_type, object_id, month, sku, composite_sku, source_forecast_id).
--
-- Расчёт — функция, чтобы у него было одно место: её зовёт страница сразу после проведения документа
-- (§7: триггер — проведение) и ночная джоба как страховка. Публикация атомарна: всё в одной транзакции.

-- ── состав, сохранённый на момент проведения ──────────────────────────────────────────────────────
-- §11 требует прямо этого: «прогноз создан для M1/M2; справочник изменён на M1/M3 без общей замены —
-- расчёт использует сохранённый состав действующего прогноза, а не текущий состав справочника».
-- По ТЗ 005 состав неизменяем (другой состав — другой SKU), но справочник собирает загрузчик из Odoo,
-- и молчаливая правка BOM меняла бы числа уже проведённого прогноза при каждом ночном пересчёте.
CREATE TABLE IF NOT EXISTS kabinet_data.forecast_composition_snapshot (
    document_id   int  NOT NULL REFERENCES kabinet_data.forecast_documents(id),
    composite_sku text NOT NULL,
    base_sku      text NOT NULL,
    quantity      int  NOT NULL,
    captured_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, composite_sku, base_sku)
);
COMMENT ON TABLE kabinet_data.forecast_composition_snapshot IS
    'ТЗ 011 §11: состав наборов на момент проведения документа. Пусто по документу = считать по справочнику (документы до 25.09.2026).';

-- ── что расчёт хочет видеть ───────────────────────────────────────────────────────────────────────
-- Строка на пару «действующий прогноз набора × компонент состава». Отдельной функцией, а не временной
-- таблицей внутри расчёта: временный объект живёт до COMMIT, и второй вызов в той же транзакции падал
-- бы «relation already exists» — а вызывать дважды в одной транзакции придётся (ночной прогон по всем
-- объектам идёт одной транзакцией).
-- Набор колонок функции менялся по ходу работы, а CREATE OR REPLACE сменить его не может —
-- поэтому пересоздаём. Это чистая функция-помощник, данных в ней нет.
DROP FUNCTION IF EXISTS kabinet_data.dependent_demand_plan(text, int);
CREATE OR REPLACE FUNCTION kabinet_data.dependent_demand_plan(
    p_object_type text,
    p_object_id   int
) RETURNS TABLE (
    source_forecast_id bigint,
    document_id        int,
    status             text,
    version            int,
    object_type        text,
    object_id          int,
    composite_sku      text,
    month              date,
    forecast_quantity  int,
    sku                text,
    component_qty      int,
    calculation_status text,
    dependent_quantity int,
    error_code         text,
    error_text         text,
    keep_previous      boolean
) LANGUAGE sql STABLE AS $plan$
    WITH src AS (
        SELECT r.id AS source_forecast_id, r.document_id, r.status, r.version,
               r.object_type, r.object_id, r.sku AS composite_sku, r.month,
               r.quantity AS forecast_quantity
        FROM kabinet_data.forecast_register r
        JOIN kabinet_data.sku_master m ON m.sku = r.sku AND m.sku_type = 'composite'
        WHERE r.is_current AND r.record_type = 'sales'
          AND r.object_type = p_object_type AND r.object_id = p_object_id
          -- §3: прошедшие месяцы новым прогнозом не пересчитываются, их результаты остаются как были
          AND r.month >= date_trunc('month', current_date)::date
    ), comp AS (
        SELECT s.*, c.base_sku, c.quantity AS component_qty,
               (mb.sku IS NULL AND c.base_sku IS NOT NULL) AS unknown_base
        FROM src s
        LEFT JOIN LATERAL (
            -- сохранённый состав документа, а если его нет (документы до 25.09.2026) — справочник
            SELECT f.base_sku, f.quantity FROM kabinet_data.forecast_composition_snapshot f
            WHERE f.document_id = s.document_id AND f.composite_sku = s.composite_sku
            UNION ALL
            SELECT k.base_sku, k.quantity FROM kabinet_data.sku_composition k
            WHERE k.composite_sku = s.composite_sku
              AND NOT EXISTS (SELECT 1 FROM kabinet_data.forecast_composition_snapshot f2
                              WHERE f2.document_id = s.document_id AND f2.composite_sku = s.composite_sku)
        ) c ON true
        LEFT JOIN kabinet_data.sku_master mb ON mb.sku = c.base_sku
    ), flags AS (
        -- состав не раскрылся вовсе — это ошибка всего набора (§6), а не одной детали
        SELECT source_forecast_id, bool_or(base_sku IS NULL OR forecast_quantity IS NULL) AS whole_failed
        FROM comp GROUP BY 1
    )
    SELECT s.source_forecast_id, s.document_id, s.status, s.version, s.object_type, s.object_id,
           s.composite_sku, s.month, s.forecast_quantity,
           -- у ошибки состава базового SKU нет вовсе; sku в реестре NOT NULL, поэтому там код набора
           COALESCE(s.base_sku, s.composite_sku) AS sku,
           s.component_qty,
           CASE WHEN s.base_sku IS NULL OR s.forecast_quantity IS NULL OR s.unknown_base
                THEN 'ERROR' ELSE 'CALCULATED' END AS calculation_status,
           -- §4: явный ноль даёт рассчитанный ноль; пусто и ошибка в ноль НЕ превращаются
           CASE WHEN s.base_sku IS NULL OR s.forecast_quantity IS NULL OR s.unknown_base THEN NULL
                ELSE s.forecast_quantity * s.component_qty END AS dependent_quantity,
           CASE WHEN s.base_sku IS NULL OR s.unknown_base THEN 'DEPENDENT_DEMAND_SOURCE_INVALID'
                WHEN s.forecast_quantity IS NULL THEN 'DEPENDENT_DEMAND_SOURCE_INVALID' END AS error_code,
           CASE WHEN s.base_sku IS NULL THEN 'нет состава у набора ' || s.composite_sku
                WHEN s.unknown_base THEN 'компонента ' || s.base_sku || ' нет в справочнике SKU'
                WHEN s.forecast_quantity IS NULL THEN 'у прогноза набора ' || s.composite_sku || ' пустое количество' END AS error_text,
           -- §7: пересчёт НЕизменного источника упал, а успешный результат по нему есть — он остаётся
           -- действующим, а эта попытка ложится историей и показывается отдельно
           (f.whole_failed AND EXISTS (
                SELECT 1 FROM kabinet_data.forecast_register d
                WHERE d.is_current AND d.record_type = 'dependent'
                  AND d.source_forecast_id = s.source_forecast_id AND d.calculation_status = 'CALCULATED')) AS keep_previous
    FROM comp s
    JOIN flags f ON f.source_forecast_id = s.source_forecast_id
$plan$;

CREATE OR REPLACE FUNCTION kabinet_data.dependent_demand_rebuild(
    p_object_type text,
    p_object_id   int,
    p_calc_version text DEFAULT 'v1'
) RETURNS TABLE (calculated int, errors int, superseded int, touched int)
LANGUAGE plpgsql AS $fn$
DECLARE
    v_snap  text := to_char(clock_timestamp(), 'YYYYMMDD"T"HH24MISSUS');
    v_calc  int := 0;
    v_err   int := 0;
    v_sup   int := 0;
    v_touch int := 0;
BEGIN
    -- 1. Что перестало быть верным: источник уже не действует, числа изменились или сменилась версия
    --    алгоритма. §7: прежние результаты становятся историческими и получают SUPERSEDED.
    WITH want AS (
        SELECT * FROM kabinet_data.dependent_demand_plan(p_object_type, p_object_id)
    ), obsolete AS (
        SELECT d.id
        FROM kabinet_data.forecast_register d
        LEFT JOIN want w
               ON w.object_type = d.object_type AND w.object_id = d.object_id AND w.month = d.month
              AND w.sku = d.sku AND w.composite_sku = d.composite_sku
              AND w.source_forecast_id = d.source_forecast_id
        WHERE d.is_current AND d.record_type = 'dependent'
          AND d.object_type = p_object_type AND d.object_id = p_object_id
          AND d.month >= date_trunc('month', current_date)::date      -- §3: прошедшее не трогаем
          -- §7: источник не менялся, а расчёт по нему упал — прежний успешный результат остаётся
          AND NOT EXISTS (SELECT 1 FROM want k WHERE k.source_forecast_id = d.source_forecast_id AND k.keep_previous)
          AND (w.source_forecast_id IS NULL
               OR w.dependent_quantity IS DISTINCT FROM d.quantity
               OR w.component_qty IS DISTINCT FROM d.component_qty
               OR w.forecast_quantity IS DISTINCT FROM d.forecast_quantity
               OR w.calculation_status IS DISTINCT FROM d.calculation_status
               OR d.calculation_version IS DISTINCT FROM p_calc_version)
    )
    UPDATE kabinet_data.forecast_register r
       SET is_current = false, calculation_status = 'SUPERSEDED', superseded_at = now(), changed_at = now()
      FROM obsolete o WHERE r.id = o.id;
    GET DIAGNOSTICS v_sup = ROW_COUNT;

    -- 2. Что не изменилось: §6 — повторный запуск не создаёт дубль, только освежает технические метки.
    WITH want AS (
        SELECT * FROM kabinet_data.dependent_demand_plan(p_object_type, p_object_id)
    ), same AS (
        SELECT d.id
        FROM kabinet_data.forecast_register d
        JOIN want w
          ON w.object_type = d.object_type AND w.object_id = d.object_id AND w.month = d.month
         AND w.sku = d.sku AND w.composite_sku = d.composite_sku AND w.source_forecast_id = d.source_forecast_id
        WHERE d.is_current AND d.record_type = 'dependent'
          AND d.object_type = p_object_type AND d.object_id = p_object_id
          AND NOT w.keep_previous
    )
    UPDATE kabinet_data.forecast_register r
       SET calculated_at = now(), source_snapshot_id = v_snap, calculation_version = p_calc_version
      FROM same s WHERE r.id = s.id;
    GET DIAGNOSTICS v_touch = ROW_COUNT;

    -- 3. Чего ещё нет — публикуем. Всё в одной транзакции: частичный набор действующим не становится.
    INSERT INTO kabinet_data.forecast_register
        (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id,
         composite_sku, component_qty, source_forecast_id, forecast_quantity,
         calculation_status, calculation_version, source_snapshot_id, error_code, error_text, calculated_at, created_by)
    SELECT 'dependent', w.object_type, w.object_id, w.sku, w.month, w.dependent_quantity, w.version, w.status, true,
           w.document_id, w.composite_sku, w.component_qty, w.source_forecast_id, w.forecast_quantity,
           w.calculation_status, p_calc_version, v_snap, w.error_code, w.error_text, now(), 'dependent-demand'
    FROM kabinet_data.dependent_demand_plan(p_object_type, p_object_id) w
    WHERE NOT w.keep_previous
      AND NOT EXISTS (
        SELECT 1 FROM kabinet_data.forecast_register d
        WHERE d.is_current AND d.record_type = 'dependent'
          AND d.object_type = w.object_type AND d.object_id = w.object_id AND d.month = w.month
          AND d.sku = w.sku AND d.composite_sku = w.composite_sku AND d.source_forecast_id = w.source_forecast_id);
    GET DIAGNOSTICS v_calc = ROW_COUNT;

    -- 4. Неудачная попытка по НЕизменному источнику (§7): действующий успешный результат остаётся, а ошибка
    --    ложится историей — иначе она известна только тому, кто читал лог. Повторные прогоны её не множат.
    INSERT INTO kabinet_data.forecast_register
        (record_type, object_type, object_id, sku, month, quantity, version, status, is_current, document_id,
         composite_sku, component_qty, source_forecast_id, forecast_quantity,
         calculation_status, calculation_version, source_snapshot_id, error_code, error_text, calculated_at, created_by)
    SELECT 'dependent', w.object_type, w.object_id, w.sku, w.month, NULL, w.version, w.status, false,
           w.document_id, w.composite_sku, w.component_qty, w.source_forecast_id, w.forecast_quantity,
           'ERROR', p_calc_version, v_snap, w.error_code, w.error_text, now(), 'dependent-demand'
    FROM kabinet_data.dependent_demand_plan(p_object_type, p_object_id) w
    WHERE w.keep_previous
      AND NOT EXISTS (
        SELECT 1 FROM kabinet_data.forecast_register d
        WHERE NOT d.is_current AND d.record_type = 'dependent' AND d.calculation_status = 'ERROR'
          AND d.object_type = w.object_type AND d.object_id = w.object_id AND d.month = w.month
          AND d.sku = w.sku AND d.composite_sku = w.composite_sku AND d.source_forecast_id = w.source_forecast_id
          AND d.calculation_version = p_calc_version AND d.error_code IS NOT DISTINCT FROM w.error_code);

    SELECT count(*) FILTER (WHERE p.calculation_status = 'ERROR') INTO v_err
      FROM kabinet_data.dependent_demand_plan(p_object_type, p_object_id) p;
    RETURN QUERY SELECT v_calc, v_err, v_sup, v_touch;
END;
$fn$;

COMMENT ON FUNCTION kabinet_data.dependent_demand_rebuild(text, int, text) IS
    'ТЗ 011: пересобирает зависимую потребность объекта из действующих прогнозов составных SKU. Идемпотентна.';

-- Итог по базовому SKU, объекту и месяцу (§6: сумма действующих деталей; поверх деталей не учитывается)
CREATE OR REPLACE VIEW kabinet_data.v_dependent_demand_current AS
SELECT object_type, object_id, sku AS base_sku, month,
       sum(quantity)                      AS dependent_quantity,
       count(*)                           AS details,
       count(*) FILTER (WHERE calculation_status = 'ERROR') AS errors,
       max(calculated_at)                 AS calculated_at
FROM kabinet_data.forecast_register
WHERE is_current AND record_type = 'dependent'
GROUP BY 1, 2, 3, 4;

GRANT SELECT ON kabinet_data.v_dependent_demand_current TO claude_code_ro,
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT ON kabinet_data.forecast_composition_snapshot TO
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.forecast_composition_snapshot TO claude_code_ro;
GRANT EXECUTE ON FUNCTION kabinet_data.dependent_demand_plan(text, int) TO
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT EXECUTE ON FUNCTION kabinet_data.dependent_demand_rebuild(text, int, text) TO
      "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
