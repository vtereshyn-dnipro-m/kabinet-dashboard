-- Курсы валют: правило свежести и правило живости джобы.
--
-- Два правила, а не одно, и это не перестраховка: свежесть смотрит ДАННЫЕ, живость —
-- ПРОГОН. Метка в пульсе без правила — это джоба, которую никто не проверяет: умрёт
-- молча (так уже остались без присмотра пять загрузчиков).
--
-- Следим за `loaded_at` (когда писали) и за `date` (по какой день закрыт календарь).
-- За `rate_date` НЕ следим намеренно: ЕЦБ не публикует курс в выходные и праздники, и
-- на длинных выходных он законно отстаёт на три-четыре дня. Правило на него давало бы
-- ложную тревогу каждую субботу — ровно тот поток, после которого канал перестают
-- читать.

INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, owner_role, is_active,
     content_date_column, max_content_age_hours, weekend_tolerance_hours, comment)
VALUES ('dnipro_m.dnipro_m.raw_ecb_fx_rates', 'loaded_at', 30, 'spark', 'DATA_OWNER', true,
        'date', 30, 0,
        'Курсы ЕЦБ через Frankfurter, джоба Kabinet - FX Rates в 09:00 Kyiv ежедневно. За rate_date не следим: в выходные он отстаёт законно.')
ON CONFLICT (table_name) DO UPDATE
   SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
       source_type = EXCLUDED.source_type, is_active = true,
       content_date_column = EXCLUDED.content_date_column,
       max_content_age_hours = EXCLUDED.max_content_age_hours,
       comment = EXCLUDED.comment, updated_at = now();

-- Имя джобы здесь обязано совпадать с именем в Databricks и с меткой в system_pulse
-- символ в символ.
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (742197017270185, 'Kabinet - FX Rates', 30, 'ежедневно 09:00 Kyiv', true,
        'Курсы GBP, SEK, PLN к евро от ЕЦБ в dnipro_m.raw_ecb_fx_rates')
ON CONFLICT (job_id) DO UPDATE
   SET job_name = EXCLUDED.job_name,
       expected_interval_hours = EXCLUDED.expected_interval_hours,
       schedule_description = EXCLUDED.schedule_description, is_active = true,
       note = EXCLUDED.note;

SELECT 'свежесть' AS rule_, table_name AS obj, max_age_hours::text AS h
  FROM kabinet_data.data_freshness_rules WHERE table_name LIKE '%fx_rates%'
UNION ALL
SELECT 'живость джобы', job_name, expected_interval_hours::text
  FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - FX Rates';
