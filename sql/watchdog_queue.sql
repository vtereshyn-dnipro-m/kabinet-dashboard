-- Очередь правок сторожа, накопившаяся с 07.09. Lakebase, kabinet_data.
-- Собрано из четырёх черновиков: watchdog_fix, freshness_rule,
-- watchdog_depth, amc_rules. Пороги свежести и здоровья живут в БД, а не
-- в коде, поэтому правятся здесь.
--
-- Все предпосылки перепроверены запросами непосредственно перед сборкой,
-- а не взяты из черновиков: черновикам сутки, за это время в базе могло
-- измениться что угодно.
--
-- ЧТО СЮДА НЕ ВОШЛО И ПОЧЕМУ — внизу файла, отдельным списком.

BEGIN;

-- ── 1. LM Transactions: 26 → 30 часов ────────────────────────────────
-- Джоба идёт в 03:00 Киев, метка стабильно в 00:01 UTC. При 26 часах
-- сдвиг запуска на два часа даёт ложный алерт. Тридцать оставляют четыре
-- часа запаса и по-прежнему ловят полный пропуск суток.
UPDATE kabinet_data.job_health_rules
   SET expected_interval_hours = 30
 WHERE job_id = 804741971942511;

-- ── 2. AMC Collect: правило смотрело на имя до переименования ─────────
-- Метка «Kabinet - AMC Collect» застыла 31.08, рядом каждые несколько
-- часов пишется «AMC Collect» — та же джоба под новым именем. Правило
-- висело на старом имени и потому слало алерт каждый день при живой
-- джобе. Порог 8 ч не трогаем: в правиле записано «every 6h (Kyiv)».
UPDATE kabinet_data.job_health_rules
   SET job_name = 'AMC Collect'
 WHERE job_id = 990635019399469
   AND job_name = 'Kabinet - AMC Collect';

-- ── 3. Глубина sales_traffic_daily: 96 → 72 часа ─────────────────────
-- Сторож смотрит в 10:01 UTC, загрузчик приносит данные на двое суток
-- назад: норма 58 ч, один пропущенный прогон 82 ч, два подряд 106 ч.
-- Порог 96 ловил только двойной пропуск. У 72 запас четырнадцать часов.
UPDATE kabinet_data.data_freshness_rules
   SET max_content_age_hours = 72,
       comment = 'Sales & Traffic из Data Kiosk. Загрузчик приносит данные на 2 суток '
                 'назад, сторож смотрит в 10:01 — в норме глубина 58 ч. Порог 72 ч '
                 'ловит один пропущенный прогон (82 ч). Прежние 96 ч срабатывали '
                 'только на двух подряд.',
       updated_at = now()
 WHERE table_name = 'kabinet_data.sales_traffic_daily';

-- ── 4. AMC: порог записи 36 → 26 часов ───────────────────────────────
-- При 36 ч пропуск одного прогона (32 ч на момент проверки в 10:01)
-- проходит незамеченным.
UPDATE kabinet_data.data_freshness_rules
   SET max_age_hours = 26, updated_at = now()
 WHERE table_name IN ('kabinet_data.amc_attribution_sync',
                      'kabinet_data.amc_campaign_asin_sync',
                      'kabinet_data.amc_dayparting_sync',
                      'kabinet_data.amc_new_to_brand_sync',
                      'kabinet_data.amc_ntb_by_asin_sync',
                      'kabinet_data.amc_overlap_sync',
                      'kabinet_data.amc_search_terms_sync');

-- ── 5. AMC: сторож начинает смотреть в содержимое ────────────────────
-- У всех семи content_date_column был пуст: проверялось только «когда
-- таблицу писали». Таблицу можно писать каждую ночь пустышкой — алерта
-- не будет. Колонка report_date есть у всех семи, проверено запросом.
-- Порог 72 ч: AMC отдаёт с лагом, при 58 ч нормы это один пропущенный
-- день и четырнадцать часов запаса.
UPDATE kabinet_data.data_freshness_rules
   SET content_date_column = 'report_date',
       max_content_age_hours = 72,
       updated_at = now()
 WHERE table_name IN ('kabinet_data.amc_attribution_sync',
                      'kabinet_data.amc_campaign_asin_sync',
                      'kabinet_data.amc_dayparting_sync',
                      'kabinet_data.amc_new_to_brand_sync',
                      'kabinet_data.amc_ntb_by_asin_sync',
                      'kabinet_data.amc_overlap_sync',
                      'kabinet_data.amc_search_terms_sync');

-- ── 6. Два правила на таблицы, которых нет ───────────────────────────
-- kabinet_data.amc_flat и kabinet_data.amc_results в схеме отсутствуют
-- (to_regclass вернул NULL по обеим). Инциденты №429 и №430 от 01.09
-- были ровно про это.
DELETE FROM kabinet_data.data_freshness_rules
 WHERE table_name IN ('kabinet_data.amc_flat', 'kabinet_data.amc_results');

-- ── 7. Глубина экономики по каналам, а не в целом ────────────────────
-- Правило на economics_summary берёт MAX(sales_date) по всем каналам
-- сразу, и свежий Leroy Merlin закрывает собой отставание Amazon.
--
-- Carrefour и ManoMano правилами НЕ покрываем намеренно: продажи там
-- реже чем через день (12 и 9 суток из 27), старая дата означает
-- «продаж не было», а не «данные не приехали». Правило на них давало бы
-- ложный алерт через день.
CREATE OR REPLACE VIEW kabinet_data.v_economics_amazon AS
SELECT e.sales_date, e.updated_at
  FROM kabinet_data.economics_summary e
  JOIN kabinet_data.v_marketplaces m
    ON upper(trim(e.marketplace)) = m.marketplace_code
 WHERE upper(m.channel) = 'AMAZON';

CREATE OR REPLACE VIEW kabinet_data.v_economics_lm AS
SELECT e.sales_date, e.updated_at
  FROM kabinet_data.economics_summary e
  JOIN kabinet_data.v_marketplaces m
    ON upper(trim(e.marketplace)) = m.marketplace_code
 WHERE upper(m.channel) = 'LEROY MERLIN';

INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours,
        content_date_column, max_content_age_hours,
        source_type, owner_role, is_active, comment, updated_at)
VALUES ('kabinet_data.v_economics_amazon', 'updated_at', 48, 'sales_date', 72,
        'lakebase', 'economics', true,
        'Экономика только по Amazon. Общее правило на economics_summary берёт MAX '
        'по всем каналам, и свежий Mirakl закрывает собой отставание Amazon. '
        'Продажи идут 26 дней из 27, глубина как метрика осмысленна.', now()),
       ('kabinet_data.v_economics_lm', 'updated_at', 48, 'sales_date', 72,
        'lakebase', 'economics', true,
        'Экономика только по Leroy Merlin. Продажи 27 дней из 27. '
        'Carrefour и ManoMano правилом НЕ покрыты намеренно: продажи там '
        'реже чем через день, старая дата означает отсутствие продаж, '
        'а не отсутствие данных.', now())
ON CONFLICT (table_name) DO NOTHING;

COMMIT;

-- ═════════════════════════════════════════════════════════════════════
-- НЕ ВОШЛО, И ВОТ ПОЧЕМУ
-- ═════════════════════════════════════════════════════════════════════
--
-- Удаление застывшей метки «Kabinet - AMC Collect».
--   Удалять метку можно, только если такого имени в Databricks больше
--   нет, — иначе стирается след поломки живой джобы. Jobs API сервис-
--   принципалу закрыт (403 на jobs/get, в списке ноль джоб), проверить
--   нечем. После правки №2 метка просто остаётся без правила: сторож её
--   не читает, вреда нет, след цел.
--
-- Удаление дублирующей метки «Kabinet - Economics Loader (LM)».
--   Ноутбук её всё ещё пишет: обе метки обновились сегодня в 10:02:45 и
--   10:02:47. Удалить сейчас — она вернётся следующим прогоном. Сначала
--   правка ноутбука, потом удаление.
--
-- Правила для пяти джоб без присмотра и для Suppressed Listings Checker.
--   job_id в job_health_rules NOT NULL, а взять его неоткуда: Jobs API
--   закрыт. Нужны CAN_VIEW на джобы.
