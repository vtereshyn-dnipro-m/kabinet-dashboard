-- Сверка правил свежести со схемами, 26.09.2026. Проверены все 65 активных правил против
-- information_schema Lakebase, Unity Catalog и базы listing-suite. Сломанных нашлось четыре,
-- и каждое было хуже, чем просто «не проверяет»: проверка падала, таблица уходила в
-- «разрешённые», и открытый инцидент stale_data по ней автозакрывался.
--
-- 1. ads_spend: правило ссылалось на loaded_at и report_date, которых в таблице нет вовсе —
--    есть updated_at (когда записал загрузчик) и date (за какой день расход). С 23.08.2026
--    свежесть рекламы не проверялась. Колонки исправлены, пороги прежние.
UPDATE kabinet_data.data_freshness_rules
   SET date_column = 'updated_at', content_date_column = 'date', updated_at = now(),
       comment = 'Ads из Economics Loader. LAG_DAYS=3 от Amazon. Колонки: updated_at — запись, date — день расхода.'
 WHERE table_name = 'kabinet_data.ads_spend';

-- 2. listing_snapshots: source_type был 'lakebase-external', а такой тип сторож намеренно
--    пропускает исключением — правило есть, проверки нет. У suppressed_listings рядом стоит
--    'lakebase-ls' и работает через то же соединение к базе listing-suite; ставим его.
UPDATE kabinet_data.data_freshness_rules
   SET source_type = 'lakebase-ls', updated_at = now()
 WHERE table_name = 'listing_data.listing_snapshots';

-- 3. amc_flat и amc_results: таблицы лежат в Unity Catalog, а не в Lakebase, и ноутбук AMC не
--    пишет их с 31.08.2026 — живой путь это семь amc_*_sync, у каждой своё правило. Правило на
--    заброшенную таблицу выключаем, чтобы не изображать проверку.
UPDATE kabinet_data.data_freshness_rules
   SET is_active = false, updated_at = now(),
       comment = 'Выключено 26.09.2026: ноутбук AMC не пишет эту таблицу с 31.08, живой путь — amc_*_sync в Lakebase.'
 WHERE table_name IN ('kabinet_data.amc_flat', 'kabinet_data.amc_results');

-- 4. synthesis_changes: таблица чужого проекта, и её свежесть — не свежесть данных, а частота
--    решений человека (принятые правки листингов). На 26.09 последняя запись от 30.08, то есть
--    27 дней — и это может быть нормой. Порог по времени здесь измеряет не то, что нужно:
--    выключаем, за таблицу отвечает Listing Suite.
UPDATE kabinet_data.data_freshness_rules
   SET is_active = false, updated_at = now(),
       comment = 'Выключено 26.09.2026: таблица listing-suite, и её возраст — частота решений человека, а не свежесть данных.'
 WHERE table_name = 'listing_data.synthesis_changes';
