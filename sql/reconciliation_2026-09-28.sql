-- Таблица результатов сверки и настройки допусков.
--
-- Почему отдельная таблица, а не только три поля в `data_source_origins`: в паспорте нужна одна
-- строка на источник («с чем, когда, чем кончилось»), а чтобы её объяснить, нужен разрез —
-- по метрике, рынку и дню. Паспорт читает сводку, человек с вопросом «а где именно разошлось»
-- читает детали. Хранить только сводку значит каждый раз пересчитывать, чтобы ответить.
CREATE TABLE IF NOT EXISTS kabinet_data.reconciliation_results (
    calc_date      DATE        NOT NULL,
    source_table   TEXT        NOT NULL,   -- наша таблица, как в data_source_origins
    against        TEXT        NOT NULL,   -- с чем сверяли
    metric         TEXT        NOT NULL,   -- продажи / штуки / себестоимость / комиссии / ...
    scope          TEXT        NOT NULL,   -- рынок или канал
    period_start   DATE,
    period_end     DATE,
    ours           NUMERIC(16,2),
    theirs         NUMERIC(16,2),
    diff_pct       NUMERIC(8,2),
    tolerance_pct  NUMERIC(6,2),
    days_total     INT,
    days_off       INT,                    -- сколько дней вышло за допуск
    verdict        TEXT        NOT NULL,   -- ok | off | no_data
    note           TEXT,
    PRIMARY KEY (calc_date, source_table, against, metric, scope)
);
CREATE INDEX IF NOT EXISTS reconciliation_results_last_ix
    ON kabinet_data.reconciliation_results (calc_date DESC, verdict);

-- Допуски по решению владельца 28.09.2026. В коде их нет — читаются отсюда.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('recon_tolerance_sales_pct', '1',
     'Допуск сверки: продажи и штуки, по рынку и дню'),
    ('recon_tolerance_cogs_pct', '1',
     'Допуск сверки: себестоимость'),
    ('recon_tolerance_costs_pct', '2',
     'Допуск сверки: комиссии, логистика, реклама — каждая колонка отдельно'),
    ('recon_tolerance_settlement_pct', '2',
     'Допуск сверки с settlement. Больше, чем у витрины: settlement приходит по дате расчёта '
     'Amazon, а не по дате заказа, поэтому сравнивается сумма за период, а не день с днём'),
    ('recon_window_days', '30', 'Окно сверки с витриной Дарины')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();

GRANT SELECT ON kabinet_data.reconciliation_results TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.reconciliation_results
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Сводку сверки пишет джоба, а она идёт под принципалом: без этого гранта расчёт проходит
-- целиком и падает на последней строке — «permission denied for table data_source_origins».
GRANT SELECT, UPDATE ON kabinet_data.data_source_origins
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Одно имя джобы в трёх местах: Databricks, метка пульса и правило здоровья.
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (453710724542368, 'Kabinet - Reconciliation', 26, '13:00 Kyiv', true,
        'Сверка с витриной Дарины и settlement; результат в паспорте, колонка «Сверка»')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name,
    expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description,
    is_active = EXCLUDED.is_active, note = EXCLUDED.note;

-- Свежесть самой сверки: если она встанет, паспорт будет показывать вчерашний результат как
-- сегодняшний. Порог 30 ч — сутки с запасом на сдвиг прогона.
INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, content_date_column,
     max_content_age_hours, owner_role, is_active, comment)
VALUES ('kabinet_data.reconciliation_results', 'calc_date', 30, 'lakebase', NULL, NULL,
        'DATA_OWNER', true, 'Результаты сверки. Питают колонку «Сверка» в паспорте данных.')
ON CONFLICT (table_name) DO UPDATE SET date_column = EXCLUDED.date_column,
    max_age_hours = EXCLUDED.max_age_hours, source_type = EXCLUDED.source_type,
    is_active = EXCLUDED.is_active, comment = EXCLUDED.comment, updated_at = now();
