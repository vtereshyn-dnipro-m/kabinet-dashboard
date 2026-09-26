-- Правило здоровья для загрузчика отгрузок FBA. Имя — символ в символ как в Databricks и в метке
-- system_pulse: расхождение не ломает ничего явно и живёт месяцами (AGENTS.md).
-- Порог 30 ч: расписание суточное, прогон по десяти рынкам занимает десятки минут (createReport —
-- один запрос в минуту на весь аккаунт), поэтому 24 ч давали бы ложные алерты на длинном прогоне.
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, is_active, note, timeout_seconds)
VALUES (821057250140489, 'Kabinet - FBA Shipments Loader', 30, '15:30 Kyiv daily', true,
        'GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL по рынкам Amazon: дата отгрузки по позициям заказов, без данных покупателей',
        7200)
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name,
    expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description,
    is_active = true, note = EXCLUDED.note, timeout_seconds = EXCLUDED.timeout_seconds;

SELECT job_id, job_name, expected_interval_hours, schedule_description, timeout_seconds
FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - FBA Shipments Loader';

-- Сборка факта отгрузки: та же тройка «имя джобы = метка пульса = правило» (AGENTS.md).
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, is_active, note, timeout_seconds)
VALUES (108611324580114, 'Kabinet - Shipment Facts', 30, '16:30 Kyiv daily', true,
        'shipment_facts: Amazon FBA из отчёта отгрузок, Amazon MFN / ManoMano / Carrefour из SendCloud, Leroy Merlin из Mirakl',
        3600)
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name,
    expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description,
    is_active = true, note = EXCLUDED.note, timeout_seconds = EXCLUDED.timeout_seconds;

-- Свежесть: у сырья отчёта и у факта свои строки. Порог 30 ч, как у суточных загрузчиков;
-- content_date_column — событие, а не загрузка: отгрузки доезжают в отчёт с задержкой, поэтому
-- у сырья допуск по дате отгрузки 72 ч, а у факта — 48 ч (в него добавляется SendCloud того же дня).
INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment,
     content_date_column, max_content_age_hours, collection_tier)
VALUES
 ('kabinet_data.raw_amazon_fulfilled_shipments', 'loaded_at', 30, 'lakebase', 'DATA_OWNER', true,
  'Реплика отчёта GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL, 15:30 Kyiv. Данных покупателей не храним.',
  'shipment_date', 72, 'daily'),
 ('kabinet_data.shipment_facts', 'loaded_at', 30, 'lakebase', 'DATA_OWNER', true,
  'Факт по дате отгрузки: Amazon FBA + MFN (SendCloud) + ManoMano/Carrefour (SendCloud) + Leroy Merlin (Mirakl). 16:30 Kyiv.',
  'shipped_date', 48, 'daily')
ON CONFLICT (table_name) DO UPDATE SET date_column = EXCLUDED.date_column,
    max_age_hours = EXCLUDED.max_age_hours, source_type = EXCLUDED.source_type,
    owner_role = EXCLUDED.owner_role, is_active = true, comment = EXCLUDED.comment,
    content_date_column = EXCLUDED.content_date_column,
    max_content_age_hours = EXCLUDED.max_content_age_hours,
    collection_tier = EXCLUDED.collection_tier, updated_at = now();

SELECT job_name, schedule_description FROM kabinet_data.job_health_rules
WHERE job_name IN ('Kabinet - FBA Shipments Loader', 'Kabinet - Shipment Facts') ORDER BY 1;
SELECT table_name, date_column, max_age_hours, content_date_column, max_content_age_hours
FROM kabinet_data.data_freshness_rules
WHERE table_name IN ('kabinet_data.raw_amazon_fulfilled_shipments', 'kabinet_data.shipment_facts') ORDER BY 1;
