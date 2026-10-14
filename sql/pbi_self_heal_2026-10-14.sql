-- Самовосстановление витрины Power BI и тревоги её источника (14.10.2026, решение владельца;
-- перезапуск чужих джоб — с разрешения владельца витрины от 14.10.2026, только перезапуск).
-- Применять ПОСЛЕ мержа и ДО создания джобы `Kabinet - Power BI Self-Heal`. :self_heal_job_id — id этой джобы
-- (его выдаст `databricks jobs create`), подставляется во вторую часть файла.

-- Какие джобы считаются источником витрины: Amazon-джобы (их перезапускаем, если упали) и сама сборка (Spiderweb —
-- после них). Список — данные, а не код: добавить или выключить джобу — строкой здесь. baseline_* — точка отсчёта для
-- сообщения «изменилось расписание / ноутбук / таблицы»; первую ставит сам прогон.
CREATE TABLE IF NOT EXISTS kabinet_data.pbi_source_jobs (
    job_id            bigint PRIMARY KEY,
    job_name          text NOT NULL,
    role              text NOT NULL CHECK (role IN ('amazon', 'spiderweb')),
    is_active         boolean NOT NULL DEFAULT true,
    baseline_cron     text,
    baseline_paused   boolean,
    baseline_notebook text,
    baseline_writes   text[],
    baseline_at       timestamptz,
    note              text
);
COMMENT ON TABLE kabinet_data.pbi_source_jobs IS
  'Джобы источника витрины Power BI: Amazon-джобы (перезапуск при падении) и сборка Spiderweb; точка отсчёта для сообщений об изменениях.';

INSERT INTO kabinet_data.pbi_source_jobs (job_id, job_name, role, note) VALUES
  (450852904255938, 'Sales & Traffic Report for Tableau', 'amazon', 'SP-API: продажи и трафик — основа Amazon в витрине'),
  (917636032470555, 'FBA Fees + Listings data for Tableau', 'amazon', 'SP-API: сборы FBA и листинги'),
  (520728352816387, 'Amazon Ads API for Tableau (First)', 'amazon', 'Ads API: реклама'),
  (117677202912960, 'Amazon Ads API for Tableau (Second)', 'amazon', 'Ads API: реклама'),
  (240320825848727, 'SendCloud tracking for Tableau', 'amazon', 'SP-API Orders: заказы и позиции'),
  (697545970063925, 'FBA Inventory Ledger Summary for Tableau', 'amazon', 'SP-API: остаток FBA (в витрину не входит, но Amazon-джоба)'),
  (347595451511001, 'Test spiderweb Amazon', 'spiderweb', 'сборка Amazon в витрине Power BI (raw_amazon_spiderweb_report)')
ON CONFLICT (job_id) DO NOTHING;

-- Журнал решений: один перезапуск в день держит он же; первая строка ('started') — с какого момента джоба следит
-- за срабатыванием реплики по записи (раньше триггера могло не быть).
CREATE TABLE IF NOT EXISTS kabinet_data.pbi_self_heal_log (
    id            bigserial PRIMARY KEY,
    day           date NOT NULL,
    kind          text NOT NULL CHECK (kind IN ('started', 'restart', 'helped', 'not_helped', 'job_changed')),
    submit_run_id bigint,          -- restart / helped / not_helped: прогон jobs/submit; job_changed: id джобы
    detail        text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pbi_self_heal_log_day_idx ON kabinet_data.pbi_self_heal_log (day, kind);
COMMENT ON TABLE kabinet_data.pbi_self_heal_log IS
  'Решения Kabinet - Power BI Self-Heal: перезапуски сборки витрины Power BI, их итог и изменения джоб источника.';

GRANT SELECT, INSERT, UPDATE ON kabinet_data.pbi_source_jobs TO "v.tereshyn@dniprom.com";
GRANT SELECT, INSERT ON kabinet_data.pbi_self_heal_log TO "v.tereshyn@dniprom.com";
GRANT USAGE ON SEQUENCE kabinet_data.pbi_self_heal_log_id_seq TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.pbi_source_jobs, kabinet_data.pbi_self_heal_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.pbi_source_jobs, kabinet_data.pbi_self_heal_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('pbi_source_late_hour', 12, 'Витрина Power BI: если к этому часу (Kyiv) сборка Amazon сегодня не записана — тревога «не обновилась»'),
  ('pbi_heal_last_hour', 17, 'Витрина Power BI: после этого часа (Kyiv) упавшую сборку не перезапускаем — длинная сборка пересеклась бы с вечерними загрузчиками; только тревога'),
  ('pbi_trigger_missed_minutes', 30, 'Реплика Power BI: через столько минут после записи в витрину без прогона реплики по записи — тревога «не сработала»'),
  ('pbi_heal_check_after_minutes', 40, 'Самовосстановление витрины: через столько минут после конца перезапуска смотрим, взяла ли реплика полную витрину')
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest) VALUES
  ('pbi_self_heal', 'task', 'High', 'Самовосстановление витрины Power BI',
   'Утренняя сборка витрины Power BI не прошла: перезапуск упавших Amazon-джоб и сборки (раз в день), «не помогло», '
   '«ключи не работают — перезапуск не делаю» или «поздно перезапускать». Закрывается сама, когда сборка в порядке.', 'daily'),
  ('pbi_source_late', 'task', 'High', 'Витрина Power BI не обновилась',
   'К 12:00 сборка Amazon в витрине Power BI сегодня не записана — Кабинет и Power BI показывают вчерашние цифры. '
   'Закрывается сама, когда витрина записана.', 'daily'),
  ('pbi_trigger_missed', 'task', 'High', 'Реплика Power BI не сработала по записи',
   'Витрина Power BI записана, а реплика Кабинета по записи не запустилась — цифры обновятся только сверкой в 13:00 и '
   'запуском в 16:45. Закрывается сама, когда реплика сработала.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

-- ── вторая часть: после `databricks jobs create` ──
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:self_heal_job_id, 'Kabinet - Power BI Self-Heal', 26, 'каждые 30 мин 10:15–17:45 Kyiv', true,
        'Самовосстановление витрины Power BI и тревоги её источника')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
