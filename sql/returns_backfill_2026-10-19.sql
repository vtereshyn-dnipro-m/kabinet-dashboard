-- Добор истории возвратов Amazon (19.10.2026). Применять ПОСЛЕ мержа, до первого ночного прогона
-- «Kabinet - Returns Backfill». job_id правила проставляется после создания джобы (см. nb/jobs/returns_backfill_2026-10-19).

-- value в reorder_params — numeric, поэтому дата начала записана как ГГГГММДД
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
  ('returns_backfill_from', 20241101,
   'Добор возвратов Amazon: с какой даты (ГГГГММДД). Глубже двух лет Amazon отчёты не отдаёт.', now()),
  ('returns_backfill_max_reports', 5,
   'Добор возвратов Amazon: не больше стольких новых createReport за ночь (квота общая на аккаунт).', now()),
  ('returns_backfill_mfn_min_orders', 20,
   'Добор возвратов Amazon: MFN-историю берём только по рынкам, где MFN-заказов за год не меньше стольких.', now()),
  ('returns_backfill_from_hhmm', 120,
   'Добор возвратов Amazon: новые createReport не раньше ЧЧММ по Киеву (в 01:00 идёт Listing Suite SQP Loader v2).', now()),
  ('returns_backfill_to_hhmm', 210,
   'Добор возвратов Amazon: новые createReport не позже ЧЧММ по Киеву (в 02:30 идёт SQP).', now())
ON CONFLICT (key) DO NOTHING;

-- Одна джоба — одна метка — одно правило. Правило временное, удаляется вместе с джобой, когда добор кончится.
-- :job_id — id созданной джобы «Kabinet - Returns Backfill».
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, created_at, note)
VALUES (:job_id, 'Kabinet - Returns Backfill', 30, 'ежедневно 01:20 Kyiv, временная', true, now(),
        'Добор истории возвратов. Удалить вместе с джобой, когда в пульсе «осталось кусков 0».');
