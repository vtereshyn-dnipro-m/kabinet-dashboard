-- Правила сторожа и свежести для Kabinet - FBA Charges Loader (job 1070371622017059).
BEGIN;
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (1070371622017059, 'Kabinet - FBA Charges Loader', 30, '09:00 Kyiv daily', true,
        'Хранение FBA (два последних месяца) и возмещения FBA (60 дней) → dnipro_m.raw_amazon_fba_* + реплики. Один запрос на весь EU-аккаунт.')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
   schedule_description = EXCLUDED.schedule_description, is_active = EXCLUDED.is_active, note = EXCLUDED.note;

-- Хранение: месяц закрывается раз в месяц, содержимое старше 45 дней — пропущен месяц.
INSERT INTO kabinet_data.data_freshness_rules (table_name, date_column, max_age_hours, content_date_column, max_content_age_hours, source_type, owner_role, is_active, comment, updated_at)
VALUES ('kabinet_data.raw_amazon_fba_storage_fees', 'loaded_at', 30, NULL, NULL, 'lakebase', 'finance', true,
        'Хранение FBA по ASIN и центру, помесячно. Загрузчик ежедневный, содержимое по месяцам — content-порог не ставим: month_of_charge не дата.', now()),
       ('kabinet_data.raw_amazon_fba_reimbursements', 'loaded_at', 30, 'approval_date', 720, 'lakebase', 'finance', true,
        'Возмещения FBA. Приходят нерегулярно — 47 за полгода; порог содержимого 30 дней ловит только полную тишину.', now())
ON CONFLICT (table_name) DO UPDATE SET max_age_hours = EXCLUDED.max_age_hours, content_date_column = EXCLUDED.content_date_column,
   max_content_age_hours = EXCLUDED.max_content_age_hours, comment = EXCLUDED.comment, updated_at = now();
COMMIT;
SELECT job_name, is_active FROM kabinet_data.job_health_rules WHERE job_id = 1070371622017059;
