-- Присмотр за переводом ERP (задание владельца 02.10.2026).
--
-- Просили «правило свежести в сторож», но правильный инструмент здесь ДРУГОЙ, и это не
-- придирка. Правило свежести смотрит на дату содержимого: у словаря переводов это
-- `translated_at`, то есть «когда последний раз что-то перевели». А словарь по делу
-- молчит в любой день, когда новых текстов в ERP не появилось, — и правило свежести
-- загоралось бы «перевод встал» ровно там, где всё в порядке. Ровно так уже обжигались
-- на Leroy Merlin: «нет заказов» подменяло «загрузчик встал».
--
-- Поэтому за живостью следим правилом по ДЖОБЕ (Jobs API, пульс ей не нужен), а
-- `translated_at` остаётся тем, ради чего он и нужен: по нему видно, когда перевели
-- каждую конкретную строку, и можно спросить «что перевели за вчера».

INSERT INTO kabinet_data.job_health_rules
       (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (435540825696316, 'Translate new SKUs', 30, '07:00 Kyiv daily', true,
        'Перевод новых текстов ERP на английский (Groq) в dnipro_m.dim_translation_en. Правило по джобе, а не по свежести словаря: в день без новых текстов словарь не меняется по делу.')
ON CONFLICT (job_id) DO UPDATE
   SET job_name = EXCLUDED.job_name,
       expected_interval_hours = EXCLUDED.expected_interval_hours,
       schedule_description = EXCLUDED.schedule_description,
       is_active = true, note = EXCLUDED.note;

SELECT job_id, job_name, expected_interval_hours, schedule_description, is_active
  FROM kabinet_data.job_health_rules WHERE job_name = 'Translate new SKUs';
