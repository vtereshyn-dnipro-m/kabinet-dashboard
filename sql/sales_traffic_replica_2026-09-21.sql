-- 21.09.2026. Sales & Traffic Кабинет больше не тянет сам: читает сырьё Дарины (raw_amazon_seller_central_sales_and_traffic_*)
-- джобой «Kabinet - Sales & Traffic Replica» в 10:50 Kyiv — после её загрузчика (08:00–10:40). Экономия 8 createReport в день,
-- данные в Кабинете на два часа раньше, а не через четыре с половиной. PL/SE (у неё таблиц нет) — по-прежнему через API внутри той же джобы.
INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (32157082853424, 'Kabinet - Sales & Traffic Replica', 30, '10:50 Kyiv daily', true,
        'sales_traffic_daily из сырья Дарины (S&T по ASIN → сумма по дню × рынку); PL/SE через SP-API')
ON CONFLICT DO NOTHING;
SELECT job_id, job_name, schedule_description FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Sales & Traffic Replica';
