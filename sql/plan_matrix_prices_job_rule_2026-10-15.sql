-- Правило сторожа для «Kabinet - Plan Matrix Prices». Выполнять ПОСЛЕ создания джобы
-- (nb/jobs/plan_matrix_prices_2026-10-15/create_plan_matrix_prices.json): вместо <JOB_ID> — id, который вернёт
-- `databricks jobs create`. Имя — символ в символ как в Databricks и в метке system_pulse ноутбука.
-- 26 ч: джоба ежедневная в 16:30 Kyiv; пропуск 15-го числа заметен — месяц M+1 тогда фиксируется расчётом «на 15-е»,
-- дозаполненным задним числом (продажи и витрина воспроизводимы, оффер Mirakl — нет).
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID>, 'Kabinet - Plan Matrix Prices', 26, '16:30 Kyiv daily',
        'Plan Matrix: средняя цена SKU × маркетплейс × месяц, заморозка после 15-го; источник nb/plan_matrix_prices.py')
ON CONFLICT DO NOTHING;
SELECT job_id, job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Plan Matrix Prices';
