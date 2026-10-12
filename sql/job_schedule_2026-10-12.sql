-- Расписание джоб: снимок, зависимости, изменения (12.10.2026, «Паспорт данных» → вкладка «Расписание»).
--
-- Пишет джоба Kabinet - Job Schedule Snapshot (раз в час, под владельцем: только он видит все джобы воркспейса и журнал
-- аудита). Только чтение чужих джоб через Jobs API: расписание, прогоны, код ноутбуков — по коду определяется, какие
-- таблицы джоба пишет и читает, а значит, чья джоба от чьей зависит. Журнал аудита (system.access.audit) даёт историю
-- расписаний «было → стало» без ожидания: Jobs API знает только текущее.
--
-- Читают: вкладка «Расписание» в паспорте данных (приложение) и сторож (тревога «порядок нарушен»).
-- Выполнять после мержа PR и ДО первой выкладки джобы.

BEGIN;

-- Текущее состояние джоб: одна строка на джобу, переписывается целиком каждым прогоном.
CREATE TABLE IF NOT EXISTS kabinet_data.job_schedule_snapshot (
    job_id          bigint PRIMARY KEY,
    job_name        text NOT NULL,
    system          text NOT NULL,         -- kabinet / powerbi / tableau / listing_suite / other
    schedule_kind   text NOT NULL,         -- cron / event / continuous / manual
    cron            text,
    timezone        text,
    paused          boolean NOT NULL DEFAULT false,
    slots           jsonb NOT NULL DEFAULT '[]',   -- [{"t":"10:40","dows":[1..7],"median_min":1.2,"p90_min":1.5,"runs":9}]
    median_min      numeric,               -- по всем успешным прогонам за 14 дней
    last_run_start  timestamptz,
    last_run_end    timestamptz,
    last_run_state  text,                  -- success / failed / running / canceled / skipped
    writes          text[] NOT NULL DEFAULT '{}',
    reads           text[] NOT NULL DEFAULT '{}',
    code_read       boolean NOT NULL DEFAULT false,  -- код ноутбука прочитан: без него зависимости неполные
    cluster_kind    text,                  -- all_purpose / job / serverless
    cluster_name    text,
    observed_at     timestamptz NOT NULL DEFAULT now()
);

-- Зависимости «наша джоба ждёт источник»: по таблицам, которые наша читает, а источник пишет.
-- Строка — наш запуск × источник; статус — худший по дням недели.
CREATE TABLE IF NOT EXISTS kabinet_data.job_dependencies (
    our_job_id      bigint NOT NULL,
    our_job         text NOT NULL,
    source_job_id   bigint NOT NULL,
    source_job      text NOT NULL,
    source_system   text NOT NULL,
    tables          text[] NOT NULL,
    our_time        text NOT NULL,         -- HH:MM по Киеву; 'event' — запуск по событию
    source_start    text,                  -- HH:MM по Киеву, последний запуск источника не позже нашего
    source_end      text,
    margin_min      integer,
    status          text NOT NULL,         -- ok / warn / broken / prev_day / event / source_event
    days            text,                  -- дни недели, на которых статус худший (пусто — каждый день)
    observed_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (our_job_id, source_job_id, our_time)
);

-- История расписаний из журнала аудита: одна строка на изменение расписания, триггера или паузы.
CREATE TABLE IF NOT EXISTS kabinet_data.job_schedule_changes (
    job_id          bigint NOT NULL,
    event_time      timestamptz NOT NULL,
    job_name        text NOT NULL,
    system          text NOT NULL,
    before          jsonb,                 -- {"kind","cron","timezone","paused","slots"}; NULL — до окна аудита неизвестно
    after           jsonb NOT NULL,
    affects_ours    boolean NOT NULL DEFAULT false,
    affected_jobs   text[] NOT NULL DEFAULT '{}',
    notified_at     timestamptz,           -- когда ушло сообщение в Telegram (только если задевает наши)
    observed_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, event_time)
);

-- Ручная поправка «чья это система», если правило по имени ошиблось. Имён людей здесь нет и быть не должно.
CREATE TABLE IF NOT EXISTS kabinet_data.job_systems (
    job_id      bigint PRIMARY KEY,
    system      text NOT NULL CHECK (system IN ('kabinet', 'powerbi', 'tableau', 'listing_suite', 'other')),
    note        text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
-- Витрина Power BI: Amazon-часть собирает эта джоба (её таблицу читает v_all_marketplaces_spiderweb_report)
INSERT INTO kabinet_data.job_systems (job_id, system, note)
VALUES (347595451511001, 'powerbi', 'Test spiderweb Amazon — таблица raw_amazon_spiderweb_report для витрины Power BI')
ON CONFLICT (job_id) DO NOTHING;

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at)
VALUES ('schedule_margin_warn_min', '10',
        'Расписание: запас между окончанием источника и стартом нашей джобы меньше этого числа минут — жёлтый; '
        'отрицательный — порядок нарушен.', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('schedule_order', 'task', 'High', 'Порядок расписания нарушен',
        'Источник по своей обычной длительности заканчивается позже, чем стартует наша джоба, которая читает его '
        'таблицу: наша джоба возьмёт вчерашние или неполные данные.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.job_schedule_snapshot, kabinet_data.job_dependencies,
      kabinet_data.job_schedule_changes, kabinet_data.job_systems
   TO "v.tereshyn@dniprom.com", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.job_schedule_snapshot, kabinet_data.job_dependencies,
      kabinet_data.job_schedule_changes, kabinet_data.job_systems
   TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

COMMIT;
