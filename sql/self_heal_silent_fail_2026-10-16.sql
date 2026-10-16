-- Самовосстановление: молчаливый сбой чужой джобы (решение владельца 16.10.2026). Джоба «успешна», а её таблица не
-- обновилась — так 16.10 Ledger Summary аналитика получил 429 на createReport, проглотил ошибку и ничего не записал.
-- Выполнять ПОСЛЕ мержа и выкладки nb/pbi_self_heal.py; затем `databricks jobs update` с
-- nb/jobs/self_heal_silent_2026-10-16/update_schedule.json (проверки до 20:45: вечерний Ledger кончается в ~16:30, а
-- квоту отчётов до ~19:35 держат SQP 17:30 и SQP v2 19:00).
-- Ноутбук без этих таблиц работает как раньше: проверка молчит.

BEGIN;

-- какие джобы и какие их таблицы проверять; список — данные, а не код
CREATE TABLE IF NOT EXISTS kabinet_data.source_job_checks (
    job_id     bigint  PRIMARY KEY,
    job_name   text    NOT NULL,                -- как в Databricks, для текста тревоги
    table_name text    NOT NULL,                -- полное имя в Unity Catalog; запись ищется в DESCRIBE HISTORY
    is_active  boolean NOT NULL DEFAULT true,
    note       text
);
COMMENT ON TABLE kabinet_data.source_job_checks IS
    'Самовосстановление: чужие джобы, у которых успешный прогон без записи в таблицу считается сбоем (тревога и один '
    'перезапуск). Читает Kabinet - Power BI Self-Heal.';
INSERT INTO kabinet_data.source_job_checks (job_id, job_name, table_name, note) VALUES
 (697545970063925, 'FBA Inventory Ledger Summary for Tableau', 'dnipro_m.dnipro_m.raw_amazon_fba_inventory_ledger_summary',
  '16.10.2026: прогон 16:20 и два перезапуска получили 429 на createReport, отмечены успешными, таблицу не записали')
ON CONFLICT (job_id) DO NOTHING;

-- джобы, которые создают отчёты SP-API (квота createReport аккаунта): в их окна перезапуск не ставим
CREATE TABLE IF NOT EXISTS kabinet_data.report_quota_jobs (
    job_id    bigint  PRIMARY KEY,
    job_name  text    NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    note      text
);
COMMENT ON TABLE kabinet_data.report_quota_jobs IS
    'Джобы, которые создают отчёты SP-API и делят квоту createReport аккаунта. Окна — по расписанию и длительности из '
    'job_schedule_snapshot. Новый отчётный загрузчик — строкой сюда. Читает Kabinet - Power BI Self-Heal.';
INSERT INTO kabinet_data.report_quota_jobs (job_id, job_name) VALUES
 (597550726435861, 'Listing Suite SQP Loader'),
 (45883686210360, 'Listing Suite SQP Loader v2'),
 (807913225672389, 'Kabinet - Brand Analytics Loader'),
 (73306181318180, 'Kabinet - Inventory Age Loader'),
 (383948740025305, 'Kabinet - Account Health Loader'),
 (474477518393306, 'Kabinet - Suppressed Listings Checker'),
 (1088358634966851, 'Kabinet - Returns Loader'),
 (917636032470555, 'FBA Fees + Listings data for Tableau'),
 (565517931588672, 'Kabinet - MYI Report Collector'),
 (1070371622017059, 'Kabinet - FBA Charges Loader'),
 (697545970063925, 'FBA Inventory Ledger Summary for Tableau'),
 (450852904255938, 'Sales & Traffic Report for Tableau'),
 (174154625041145, 'Kabinet - FBA Ledger Detail + Listing Cards Sync'),
 (821057250140489, 'Kabinet - FBA Shipments Loader'),
 (735430499286592, 'Listing Suite Sync Catalog Items')
ON CONFLICT (job_id) DO NOTHING;

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('source_silent_restart_after_min', 30,
  'Самовосстановление: молчаливый сбой чужой джобы перезапускаем не раньше чем через столько минут после конца прогона', now()),
 ('source_silent_quota_buffer_min', 10,
  'Самовосстановление: запас в минутах между концом перезапуска и стартом чужого отчётного прогона', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest) VALUES
 ('source_silent_fail', 'task', 'High', 'Джоба отработала, а таблица не обновилась',
  'Чужая джоба (список — source_job_checks) отмечена успешной, но в её таблицу ничего не записано: ошибка внутри '
  'ноутбука проглочена. Самовосстановление перезапускает такой прогон один раз — через 30 минут и вне окон чужих '
  'отчётов; не помогло — тревога «второй раз не перезапускаю». Закрывается сама, когда прогон записал таблицу.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

GRANT SELECT ON kabinet_data.source_job_checks, kabinet_data.report_quota_jobs
    TO "v.tereshyn@dniprom.com", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";

UPDATE kabinet_data.job_health_rules
   SET schedule_description = 'каждые 30 мин 11:15–20:45 Kyiv'
 WHERE job_name = 'Kabinet - Power BI Self-Heal';

COMMIT;

SELECT job_name, table_name FROM kabinet_data.source_job_checks;
SELECT count(*) AS report_jobs FROM kabinet_data.report_quota_jobs;
