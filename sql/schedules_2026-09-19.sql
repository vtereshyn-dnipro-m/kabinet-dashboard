-- Развод расписаний по квоте createReport, вторая итерация 19.09.2026 (см. карту в CLAUDE.md).
-- Джобы Дарины: FBA Fees + Listings 09:30 → 06:15, FBA Inventory Ledger Summary 10:25 → 07:40 — оба
-- вышли из окна Sales & Traffic (08:00–10:40); их потребители в 10:30–10:45 не трогались и получают
-- данные раньше. Правил в job_health_rules на джобы Дарины нет.
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:15 Kyiv daily' WHERE job_id = 565517931588672;   -- MYI
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:30 Kyiv daily' WHERE job_id = 1070371622017059;  -- FBA Charges
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:15 Kyiv daily' WHERE job_id = 909831072825007;   -- SKU Master
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:30 Kyiv daily' WHERE job_id = 761137342699876;   -- Product Entities
UPDATE kabinet_data.job_health_rules SET schedule_description = '07:45 Kyiv daily' WHERE job_id = 630855251229041;   -- Assortment Matrix
UPDATE kabinet_data.job_health_rules SET schedule_description = '04:00 Kyiv daily' WHERE job_name = 'Kabinet - Inventory Age Loader';
UPDATE kabinet_data.job_health_rules SET schedule_description = '04:15 Kyiv daily' WHERE job_name = 'Kabinet - Account Health Loader';
-- SQP: прогон 55 мин, шесть слотов вне чужих окон; самый длинный промежуток между успехами 05:25 → 12:25 = 7 ч,
-- поэтому порог правила 6 ч → 8 ч, иначе каждое утро ложный «no success».
UPDATE kabinet_data.job_health_rules SET schedule_description = '02:30, 04:30, 11:30, 13:30, 17:30, 22:30 Kyiv',
       expected_interval_hours = 8 WHERE job_id = 597550726435861;
SELECT job_name, schedule_description, expected_interval_hours FROM kabinet_data.job_health_rules
WHERE job_name ~ 'MYI|FBA Charges|SQP|SKU Master|Product Entities|Assortment|Inventory Age|Account Health' ORDER BY job_name;
