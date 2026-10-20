-- Amazon Run Check: проверка записи для джоб, которые пишут в Lakebase, а не в Unity Catalog (20.10.2026, решение
-- владельца). Применять ПОСЛЕ мержа и ДО выкладки ноутбука: новый nb/amazon_run_check.py читает эти колонки.
-- Проверка на истории 30 дней (только чтение, 20.10.2026): у Buy Box, BSR, Review Requests (утро и ES вечер), Suppressed
-- Listings и Listing Suite Auto Collector каждый успешный прогон писал — ложных «без записи» 0 из 22–30 прогонов.
-- Settlements и обе SQP законно пишут не каждый прогон (выплаты раз в ~2 недели, SQP — новая неделя раз в неделю):
-- им правило quiet_days — тревога, если за столько дней ни одной записи. Самый длинный промежуток между записями за 60
-- дней: Settlements 7,0 дн → 10; SQP Loader 3,5 дн → 5; SQP Loader v2 1,0 дн (добор истории), обычный ритм — неделя → 8.
-- Без проверки: Auth Guard (писать нечего, сигнал — пульс), джобы на паузе, доборы, Listing Issues (у listing_issues нет
-- колонки времени), Sync Catalog Items (за 60 дней fetched_at обновился 2 раза из 11 прогонов при 1 119 товарах — колонка
-- не отражает запись), Ads API for Tableau (First) (таблиц не пишет, только номера отчётов в файлы тома).

ALTER TABLE kabinet_data.amazon_api_jobs
    ADD COLUMN IF NOT EXISTS pg_db      text CHECK (pg_db IN ('kabinet', 'listing')),
    ADD COLUMN IF NOT EXISTS pg_table   text,
    ADD COLUMN IF NOT EXISTS pg_ts_col  text,
    ADD COLUMN IF NOT EXISTS quiet_days int  CHECK (quiet_days BETWEEN 1 AND 14);
COMMENT ON COLUMN kabinet_data.amazon_api_jobs.pg_table IS
  'Таблица Lakebase (схема.таблица), запись в которую проверяется по pg_ts_col: timestamp — внутри прогона, date — день начала прогона по Киеву';
COMMENT ON COLUMN kabinet_data.amazon_api_jobs.quiet_days IS
  'Джоба законно пишет не каждый прогон: тревога silent_success — если за столько дней ни одной записи (не больше 14)';

UPDATE kabinet_data.amazon_api_jobs AS j SET check_write = true, pg_db = v.db, pg_table = v.tb, pg_ts_col = v.col,
       quiet_days = v.q, updated_at = now(),
       note = concat_ws('; ', nullif(j.note, ''), 'проверка записи в Lakebase с 20.10.2026')
FROM (VALUES
    (1086620628061334::bigint, 'kabinet', 'kabinet_data.buybox_status',         'checked_at',    NULL::int),
    (376510559038967,          'kabinet', 'kabinet_data.asin_bsr_daily',        'loaded_at',     NULL),
    (760565204236769,          'kabinet', 'kabinet_data.review_request_log',    'checked_at',    NULL),
    (504383462189415,          'kabinet', 'kabinet_data.review_request_log',    'checked_at',    NULL),
    (474477518393306,          'listing', 'listing_data.suppressed_listings',   'snapshot_date', NULL),
    (89677076782805,           'listing', 'listing_data.listing_snapshots',     'fetched_at',    NULL),
    (1086798073703615,         'kabinet', 'kabinet_data.raw_amazon_settlements', 'loaded_at',    10),
    (597550726435861,          'listing', 'listing_data.sqp_reports',           'loaded_at',     5),
    (45883686210360,           'listing', 'listing_data.sqp_reports_v2',        'loaded_at',     8)
) AS v(job_id, db, tb, col, q)
WHERE j.job_id = v.job_id;
