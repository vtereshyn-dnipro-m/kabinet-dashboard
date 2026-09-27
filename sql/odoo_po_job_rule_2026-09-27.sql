-- Правило здоровья джобы загрузчика заказов Odoo.
--
-- Имя джобы в Databricks, метка в `system_pulse` и `job_name` здесь — одна строка символ
-- в символ: «Kabinet - Odoo Purchase Orders». Без этой строки джоба пишет пульс, но её никто
-- не проверяет — умрёт молча, и план снабжения тихо схлопнется до недельного листа.
--
-- Интервал 26 часов, хотя прогонов два (11:30 и 16:30 Kyiv): порог считается от последнего
-- успеха, и сутки с запасом ловят пропуск ОБОИХ прогонов, не поднимая тревогу из-за одного.
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (386823324031566, 'Kabinet - Odoo Purchase Orders', 26, '11:30 и 16:30 Kyiv', true,
        'Заказы Odoo — основной источник плана снабжения в автозаказе; лист Дарины запасной')
ON CONFLICT (job_id) DO UPDATE SET
    job_name = EXCLUDED.job_name,
    expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description,
    is_active = EXCLUDED.is_active,
    note = EXCLUDED.note;
