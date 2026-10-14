-- Plan Matrix: запись средних цен вкладкой на маркетплейс (avg_Amazon_ES … avg_TikTok_ES), формат согласован с
-- аналитиком 14.10.2026. Выполнять после мержа PR, до прогона ноутбука с новой ячейкой 3.
--
-- Журнал записей нужен проверке перед записью: новая вкладка сравнивается с прошлой удачной записью в ту же таблицу
-- (цен стало резко меньше или не осталось вовсе — не перезаписываем, тревога). Журнал по таблице, а не общий: копия
-- для показа и таблица аналитика не должны сравниваться друг с другом.

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.plan_price_sheet_log (
    id           bigserial PRIMARY KEY,
    written_at   timestamptz NOT NULL DEFAULT now(),
    target_sheet text        NOT NULL,                 -- ключ Google-таблицы
    tab          text        NOT NULL,                 -- avg_Amazon_ES …
    n_rows       integer     NOT NULL,
    n_prices     integer     NOT NULL,                 -- непустых цен на вкладке
    status       text        NOT NULL CHECK (status IN ('written', 'skipped')),
    note         text
);
CREATE INDEX IF NOT EXISTS plan_price_sheet_log_last ON kabinet_data.plan_price_sheet_log (target_sheet, tab, written_at DESC);
COMMENT ON TABLE kabinet_data.plan_price_sheet_log IS
    'Plan Matrix: журнал записи вкладок avg_* в Google-таблицу. skipped — проверка перед записью не пустила '
    '(цен меньше прошлой записи больше plan_price_sheet_guard_drop_pct). Пишет Kabinet - Plan Matrix Prices.';

GRANT SELECT, INSERT ON kabinet_data.plan_price_sheet_log TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE ON SEQUENCE kabinet_data.plan_price_sheet_log_id_seq TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.plan_price_sheet_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('plan_price_sheet_guard_drop_pct', 30,
  'Plan Matrix: на вкладке avg_* цен стало меньше прошлой записи больше чем на этот % (или ноль) — вкладку не '
  'перезаписываем, тревога plan_price_sheet_guard', now()),
 ('plan_price_months_ahead', 15,
  'Plan Matrix: минимум месяцев вперёд от текущего, на которые считается цена и есть колонка во вкладках avg_*', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('plan_price_sheet_guard', 'task', 'High', 'Plan Matrix: цены не перезаписаны',
        'Перед записью вкладки avg_* в таблицу Plan Matrix цен оказалось резко меньше, чем в прошлой записи, или не '
        'осталось ни одной. Вкладку не перезаписали — в таблице цены прошлой записи. Закрывается сама, когда все '
        'вкладки записаны.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

COMMIT;

SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'plan_price_%' ORDER BY key;
