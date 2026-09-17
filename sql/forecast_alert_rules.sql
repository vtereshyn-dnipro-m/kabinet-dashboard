-- 17.09.2026. Правила прогнозных алертов по объектам (ТЗ 010 §13 темп, §18 MISSING/PARTIAL_FORECAST)
-- и пороги — в БД, не в коде. Решение владельца: Spain и France грузятся как прогноз пула, но
-- план там только по Amazon, а факт пула — по четырём каналам; темп по ним временно выключен.
CREATE TABLE IF NOT EXISTS kabinet_data.forecast_alert_rules (
    object_type   TEXT NOT NULL CHECK (object_type IN ('marketplace', 'pool')),
    object_id     INT  NOT NULL,
    pace_alert    BOOLEAN NOT NULL DEFAULT TRUE,    -- «продаём быстрее / медленнее плана» (темп по календарю)
    missing_alert BOOLEAN NOT NULL DEFAULT TRUE,    -- MISSING_FORECAST / PARTIAL_FORECAST на 6 месяцев
    note          TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (object_type, object_id)
);
GRANT SELECT ON kabinet_data.forecast_alert_rules TO claude_code_ro, "b1698364-6ec5-4240-8cd6-e06dd6e60856";

INSERT INTO kabinet_data.forecast_alert_rules (object_type, object_id, pace_alert, missing_alert, note) VALUES
 ('pool', 6, FALSE, TRUE, 'Spain: план только Amazon ES, факт пула — 4 канала; темп выключен до плана по LM/MM/CF (17.09.2026)'),
 ('pool', 7, FALSE, TRUE, 'France: план только Amazon FR, факт пула — AMZ+MM; темп выключен (17.09.2026)'),
 ('marketplace', 2, TRUE, TRUE, 'DE: объект и план совпадают'),
 ('marketplace', 4, TRUE, TRUE, 'IT: объект и план совпадают')
ON CONFLICT (object_type, object_id) DO UPDATE SET pace_alert = EXCLUDED.pace_alert, missing_alert = EXCLUDED.missing_alert, note = EXCLUDED.note, updated_at = now();

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
 ('forecast_pace_threshold_pct', 25, 'ТЗ 010 §13: порог относительного отклонения от календарного темпа, по умолчанию 25 %'),
 ('forecast_pace_min_units', 10, 'темп не считаем, пока факта с начала месяца меньше N штук — в первые дни месяца дробь скачет'),
 ('missing_forecast_min_units_90d', 5, 'MISSING/PARTIAL_FORECAST только по SKU с продажами ≥ N шт за 90 дней на объекте: товар без продаж и без плана — норма (владелец, 17.09.2026)')
ON CONFLICT (key) DO NOTHING;

-- Загрузчик плана (run_as сервис-принципал) читает состав пулов и справочники
GRANT SELECT ON kabinet_data.pool_members, kabinet_data.pools, kabinet_data.marketplaces_new, kabinet_data.marketplaces, kabinet_data.reorder_params TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- 17.09.2026, вечер: типы прогнозных алертов в справочнике (список ClickUp назначается на экране).
INSERT INTO kabinet_data.incident_types (incident_type, title, description, mode, risk, due_days) VALUES
  ('forecast_pace',    'Продаём быстрее плана',   'Отгрузки с начала месяца опережают календарный темп плана больше чем на forecast_pace_threshold_pct (или план 0, а отгрузки есть). В тексте — покрытие остатком против срока поставки.', 'task', 'High', 3),
  ('missing_forecast', 'Прогноза нет',            'SKU продаётся на объекте (≥ missing_forecast_min_units_90d шт за 90 дн), а прогноза нет ни на один из 6 месяцев. ТЗ 010 §18, ответственный — country manager.', 'task', 'High', 5),
  ('partial_forecast', 'Прогноз не на все месяцы','Прогноз есть не на все 6 обязательных месяцев; недостающие перечислены в тексте. ТЗ 010 §18.', 'task', 'Medium', 5)
ON CONFLICT (incident_type) DO UPDATE SET title = EXCLUDED.title, description = EXCLUDED.description;
