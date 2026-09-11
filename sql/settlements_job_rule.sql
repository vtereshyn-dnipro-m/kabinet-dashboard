-- Правило сторожа для Kabinet - Settlements Loader. Lakebase, kabinet_data.
-- job_id 1086798073703615, джоб создан 11.09.2026 сервис-принципалом Claude Code.
--
-- is_active = FALSE намеренно и временно: джоб бежит под принципалом
-- b1698364-…, у которого нет роли в Lakebase, и падает на записи реплики.
-- Сменить владельца может только админ воркспейса. Расписание на паузе по
-- той же причине. Как run_as станет v.tereshyn@dniprom.com — включить обе:
--   UPDATE kabinet_data.job_health_rules SET is_active = TRUE WHERE job_id = 1086798073703615;
-- и снять паузу с расписания.

BEGIN;

INSERT INTO kabinet_data.job_health_rules
       (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (1086798073703615, 'Kabinet - Settlements Loader', 30, '08:30 Kyiv daily', false,
        'Settlement V2 по всем рынкам → dnipro_m.raw_amazon_settlements + реплика в Lakebase. '
        'Выключено при создании 11.09.2026: ждёт run_as = v.tereshyn (у принципала Claude Code '
        'нет роли в Lakebase). Включить вместе со снятием паузы.')
ON CONFLICT (job_id) DO UPDATE
   SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
       schedule_description = EXCLUDED.schedule_description, note = EXCLUDED.note;

COMMIT;

SELECT job_id, job_name, expected_interval_hours, is_active FROM kabinet_data.job_health_rules
 WHERE job_id = 1086798073703615;
