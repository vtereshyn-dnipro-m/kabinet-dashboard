-- Запасная джоба вечерней цепочки переименована (12.10.2026): «Kabinet - После Ledger Summary (запасной)» в таблицах
-- обрезалось до имени основной джобы. Одно имя — в трёх местах: джоба, метка пульса (ноутбук), правило здоровья.
-- Метки пульса под старым именем ещё нет — первый прогон запасной джобы 13.10 в 18:30.
UPDATE kabinet_data.job_health_rules SET job_name = 'Kabinet - Запасной прогон после Ledger Summary'
 WHERE job_id = 936210060909607;
DELETE FROM kabinet_data.system_pulse WHERE job_name = 'Kabinet - После Ledger Summary (запасной)';
