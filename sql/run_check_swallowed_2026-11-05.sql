-- Amazon Run Check: новые id джоб Дарины и тревога «зелёная, но с проглоченной ошибкой» (05.11.2026, решение владельца).
-- Применять ПОСЛЕ мержа и ДО выкладки ноутбука: новый nb/amazon_run_check.py пишет в новые колонки amazon_run_checks.
-- 02.11.2026 Дарина пересоздала джобы: старых id в Databricks больше нет (проверено jobs get), а в реестре они остались,
-- поэтому Run Check не видел бы её прогонов вовсе. Таблицы и настройки у строк те же, меняются только id и имя.
-- source_job_checks и pbi_source_jobs намеренно не меняем: их читает Power BI Self-Heal, он на паузе и умеет
-- перезапускать джобы Дарины, это отдельное решение. Пока Ledger Summary в source_job_checks под старым id, его
-- новая джоба проверяется здесь, а не уходит в Self-Heal.

BEGIN;

ALTER TABLE kabinet_data.amazon_run_checks
    ADD COLUMN IF NOT EXISTS n_swallowed      int,
    ADD COLUMN IF NOT EXISTS swallowed_sample text;

UPDATE kabinet_data.amazon_api_jobs AS j
SET job_id = v.new_id, job_name = v.new_name, updated_at = now()
FROM (VALUES
    (520728352816387::bigint, 316166064136505::bigint,  'Amazon Ads Reports (First) Job'),
    (117677202912960::bigint, 973768234848665::bigint,  'Amazon Ads Reports (Second) Job'),
    (917636032470555::bigint, 954976844729880::bigint,  'Amazon Fees + Listings Data Job'),
    (697545970063925::bigint, 1008081809785527::bigint, 'Amazon FBA Inventory Ledger Summary Job'),
    (450852904255938::bigint, 428707652593052::bigint,  'Amazon Sales & Traffic Report Job'),
    (240320825848727::bigint, 19812285864163::bigint,   'Amazon Orders + Sendcloud Job')
) AS v(old_id, new_id, new_name)
WHERE j.job_id = v.old_id;

-- Как у silent_success: тот же список и исполнители, что у job_health. ClickUp Sync сейчас на паузе, поэтому до его
-- включения задачи не создаются; сообщение в бот отправляет сам Run Check.
INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, due_days, watch_close, telegram_digest,
                                         clickup_list_id, clickup_list_name, assignee_group_id, assignee_group_name,
                                         enabled_since, title, description, note, updated_by)
SELECT 'swallowed_errors', 'task', 'High', 1, true, 'daily', clickup_list_id, clickup_list_name,
       assignee_group_id, assignee_group_name, DATE '2026-11-05',
       'Джоба Amazon успешна, но пропустила ошибки',
       'Прогон зелёный, но в его выводе есть строки об ошибках: часть отчётов или заказов не получена, данные могут быть неполными.',
       'Kabinet - Amazon Run Check; закрывается сама, когда следующий успешный прогон прошёл без ошибок', 'claude_code'
FROM kabinet_data.incident_types WHERE incident_type = 'job_health'
ON CONFLICT (incident_type) DO NOTHING;

COMMIT;
