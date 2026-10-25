-- Автозагрузка TikTok под kabinet-jobs-sp (поверх #364, решение владельца 25.10.2026). Применяет владелец, не агент.
-- Запуск — psql под владельцем базы, одной транзакцией, ПОСЛЕ #364 (роль :"sp" заведена в A1) и ПОСЛЕ создания двух
-- джоб (их job_id подставляются переменными):
--   psql "<строка владельца>" -v sp=<Application ID> -v orders_job_id=<id> -v analytics_job_id=<id> \
--        -v ON_ERROR_STOP=1 -1 -f sql/tiktok_jobs_2026-10-25.sql
-- Только добавить: ничего не отнимает и не переименовывает.

-- ── 1. Запись в реплики TikTok для загрузчика заказов ──
-- Загрузчик пишет только INSERT … ON CONFLICT DO UPDATE (nb/tiktok_loader.py, реплика): нужны INSERT и UPDATE, SELECT —
-- для ON CONFLICT. DELETE не нужен. Чтение reorder_params и запись system_pulse принципал получает по #364 (A3).
GRANT SELECT, INSERT, UPDATE ON kabinet_data.raw_tiktok_orders, kabinet_data.raw_tiktok_order_lines,
      kabinet_data.raw_tiktok_finance_tx TO :"sp";

-- ── 2. Правила здоровья — имя джобы = имя метки пульса = имя в Databricks (AGENTS.md, «Одно имя джоба в трёх местах») ──
-- Порог 26 ч — раз в сутки с запасом, как у других ежедневных джоб.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:orders_job_id, 'Kabinet - TikTok Shop Loader', 26, 'ежедневно 06:30 Kyiv', true,
        'TikTok Shop: заказы, товары, финансы и реплика для страниц; run_as kabinet-jobs-sp'),
       (:analytics_job_id, 'Kabinet - TikTok Shop Analytics Loader', 26, 'ежедневно 06:45 Kyiv', true,
        'TikTok Shop: аналитика магазина, товаров, видео, эфиров; run_as kabinet-jobs-sp')
ON CONFLICT (job_id) DO NOTHING;

-- Проверка чтением (после применения):
-- SELECT has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_orders', 'INSERT'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_finance_tx', 'UPDATE'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_order_lines', 'DELETE');          -- t, t, f
-- SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name LIKE 'Kabinet - TikTok%';
