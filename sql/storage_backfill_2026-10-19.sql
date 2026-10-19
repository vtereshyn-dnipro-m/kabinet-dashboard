-- Добор деталей хранения FBA (19.10.2026, T-14). Применять ПОСЛЕ мержа. job_id правила — после создания джобы
-- (nb/jobs/storage_backfill_2026-10-19). Окно и ночной лимит — общие с добором возвратов (returns_backfill_*).

-- value в reorder_params — numeric, поэтому месяцы записаны как ГГГГММ
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
  ('storage_backfill_from', 202411,
   'Добор деталей хранения FBA: с какого месяца (ГГГГММ). Идёт от новых к старым; первый CANCELLED останавливает.', now()),
  ('storage_backfill_to', 202606,
   'Добор деталей хранения FBA: по какой месяц (ГГГГММ). Дальше месяцы берёт сам Kabinet - FBA Charges Loader.', now())
ON CONFLICT (key) DO NOTHING;

-- Одна джоба — одна метка — одно правило. Временное, удаляется вместе с джобой по окончании добора.
-- :job_id — id созданной джобы «Kabinet - Storage Fees Backfill».
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, created_at, note)
VALUES (:job_id, 'Kabinet - Storage Fees Backfill', 30, 'ежедневно 01:30 Kyiv, временная', true, now(),
        'Добор деталей хранения FBA. Удалить вместе с джобой, когда в пульсе «осталось месяцев 0».');
