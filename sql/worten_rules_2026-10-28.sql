-- Worten: правило сторожа и правило свежести (28.10.2026; docs/worten.md). Применяется ПОСЛЕДНИМ — после
-- sql/worten_uc_2026-10-28.sql, sql/worten_2026-10-28.sql, создания джобы `Kabinet - Worten Loader` и её первого
-- прогона без сбоев. Владелец или агент по прямому «применяй», под учёткой владельца, одной транзакцией:
--   psql "<строка владельца>" -v worten_job_id=<id> -v ON_ERROR_STOP=1 -1 -f sql/worten_rules_2026-10-28.sql
-- Только добавляет.

-- Свежесть — по loaded_at реплики офферов: он переносится из сырья (время снимка), а не ставится now() при записи
-- реплики, поэтому упавший OF21 виден как старение.
INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours, content_date_column, max_content_age_hours,
        source_type, owner_role, is_active, comment, updated_at) VALUES
 ('kabinet_data.raw_worten_offers', 'loaded_at', 26, NULL, NULL, 'lakebase', NULL, true,
  'Worten: офферы (реплика). По содержимому не проверяем — снимок целиком', now())
ON CONFLICT (table_name) DO NOTHING;
-- Имя = метка пульса = имя джобы (AGENTS.md, «Одно имя джоба в трёх местах»). Два прогона в сутки (07:20 и 15:20),
-- самый длинный промежуток 16 ч — порог 18 ч: тревога после первого же пропущенного прогона.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:worten_job_id, 'Kabinet - Worten Loader', 18, 'ежедневно 07:20, 15:20 Kyiv', true,
        'Worten (Mirakl): офферы и заказы, реплика для страниц; run_as kabinet-jobs-sp')
ON CONFLICT (job_id) DO NOTHING;

-- Проверка чтением:
-- SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Worten Loader';
-- SELECT table_name, max_age_hours FROM kabinet_data.data_freshness_rules WHERE table_name = 'kabinet_data.raw_worten_offers';
