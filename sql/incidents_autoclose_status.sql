-- Инциденты, закрытые сторожем, но оставшиеся в статусе open.
--
-- Kabinet - Watchdog при автозакрытии пишет resolved_at и resolved_by, но
-- не трогает status. Страница фильтрует по status — и закрытые висят как
-- открытые: 13 job_health и 17 stale_data на 11.09.2026, некоторые с 18.08.
-- Ноутбук правится тем же днём; этот файл — разовая уборка хвоста.

BEGIN;

UPDATE kabinet_data.incidents
   SET status = 'resolved'
 WHERE status = 'open'
   AND resolved_at IS NOT NULL;

COMMIT;

SELECT incident_type, count(*) AS ostalos_open_s_resolved_at
  FROM kabinet_data.incidents
 WHERE status = 'open' AND resolved_at IS NOT NULL
 GROUP BY 1;
