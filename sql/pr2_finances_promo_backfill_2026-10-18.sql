-- PR №2: Finances, промо Seller Analytics, добор экономики Data Kiosk за два года (решения владельца 18.10.2026).
-- Выполнять ПОСЛЕ создания трёх джоб (nb/jobs/pr2_2026-10-18/*.json): вместо <JOB_ID_FIN>, <JOB_ID_PROMO>,
-- <JOB_ID_BACKFILL> — id, которые вернёт `databricks jobs create`. Имена — символ в символ как в Databricks и в
-- метках system_pulse ноутбуков.
BEGIN;
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('finances_reread_days', 30,
  'Finances API: сколько последних дней перечитывать каждым прогоном (статус транзакции меняется: отложенная → выплаченная)', now()),
 ('promotions_reread_days', 35,
  'Промо Seller Analytics (Data Kiosk): сколько последних дней перечитывать каждым прогоном — Amazon уточняет промо задним числом', now()),
 ('econ_backfill_deadline_hhmm', 430,
  'Добор экономики Data Kiosk: после этого времени (Kyiv, ЧЧММ) новых запросов не создаём — остаток следующей ночью', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note) VALUES
 (<JOB_ID_FIN>, 'Kabinet - Amazon Finances Loader', 26, '08:40 Kyiv daily',
  'Транзакции Amazon (Finances API v2024-06-19) без данных покупателя; источник nb/finances_loader.py'),
 (<JOB_ID_PROMO>, 'Kabinet - Amazon Promotions Loader', 26, '08:50 Kyiv daily',
  'Промо Amazon по ASIN × день (Data Kiosk Seller Analytics); источник nb/promotions_loader.py'),
 (<JOB_ID_BACKFILL>, 'Kabinet - Economics DK Backfill', 26, '00:30 Kyiv nightly, пока история не полная',
  'Добор экономики Data Kiosk до 15.05.2026; источник nb/economics_dk_backfill.py. Правило удалить вместе с паузой '
  'джобы, когда в пульсе «история полная»')
ON CONFLICT DO NOTHING;

INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours, content_date_column, max_content_age_hours,
        source_type, owner_role, is_active, comment, updated_at) VALUES
 ('dnipro_m.dnipro_m.raw_amazon_finances_transactions', 'loaded_at', 30, 'posted_at', 72,
  'spark', 'finance', true,
  'Транзакции Amazon (Finances API). Содержимое: последняя проводка — у Amazon проводки идут каждый день', now()),
 ('dnipro_m.dnipro_m.raw_amazon_seller_analytics_promotions', 'loaded_at', 30, NULL, NULL,
  'spark', 'economics', true,
  'Промо Amazon по ASIN (Data Kiosk). По содержимому не проверяем: дни без акций — норма', now())
ON CONFLICT (table_name) DO NOTHING;
COMMIT;

SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules
 WHERE job_name IN ('Kabinet - Amazon Finances Loader', 'Kabinet - Amazon Promotions Loader', 'Kabinet - Economics DK Backfill');
SELECT key, value FROM kabinet_data.reorder_params
 WHERE key IN ('finances_reread_days', 'promotions_reread_days', 'econ_backfill_deadline_hhmm');
SELECT table_name, max_age_hours FROM kabinet_data.data_freshness_rules
 WHERE table_name LIKE 'dnipro_m.dnipro_m.raw_amazon_finances%' OR table_name LIKE '%seller_analytics_promotions';
