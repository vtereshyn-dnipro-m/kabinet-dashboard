-- Самовосстановление Power BI: первый запуск с 10:15 перенесён на 11:15, дальше каждые 30 мин до 17:45 (решение владельца
-- 16.10.2026). Причина — тревога сторожа schedule_order: в 10:15 сборка витрины (Test spiderweb Amazon, старт 10:00,
-- ~20 мин) ещё не закончена. Одним расписанием Databricks «10:30, затем 10:45, 11:15…» не задать — выбран шаг 30 мин с 11:15.
-- Выполнять после мержа PR и `databricks jobs update` (nb/jobs/pbi_self_heal_schedule_2026-10-16/update_schedule.json).
BEGIN;
UPDATE kabinet_data.job_health_rules
   SET schedule_description = 'каждые 30 мин 11:15–17:45 Kyiv'
 WHERE job_name = 'Kabinet - Power BI Self-Heal';
UPDATE kabinet_data.incidents
   SET status = 'resolved', resolved_at = now(),
       resolved_by = 'claude-code по указанию владельца: первый запуск Self-Heal перенесён на 11:15 (16.10.2026)'
 WHERE incident_type = 'schedule_order' AND status <> 'resolved'
   AND message LIKE '[SCHED:Kabinet - Power BI Self-Heal 10:15%';
COMMIT;
SELECT job_name, schedule_description FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Power BI Self-Heal';
