-- Правило свежести на сырьё сессий Seller Analytics (12.10.2026).
-- Применять ПОСЛЕ первого прогона реплики с ячейкой 2: таблицу создаёт она, а правило на несуществующую
-- таблицу сторож считает сломанным.
--
-- Синк — время загрузки (окно 14 дней переписывается каждым прогоном реплики, основной запуск по событию утром,
-- запасной 11:00), порог 30 ч. Содержимое — последний день с трафиком: в норме вчера, порог 72 ч.

INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment,
     content_date_column, max_content_age_hours)
VALUES
    ('dnipro_m.dnipro_m.raw_amazon_seller_analytics_traffic', 'loaded_at', 30, 'spark', 'economics', true,
     'Сессии и просмотры по рынку и по ASIN × день из Data Kiosk Seller Analytics. Пишет Kabinet - Sales & Traffic Replica, ячейка 2, окно 14 дней каждым прогоном. Из неё — sessions в sales_traffic_daily и sales_traffic_asin.',
     'date', 72)
ON CONFLICT (table_name) DO UPDATE SET
    date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours, source_type = EXCLUDED.source_type,
    owner_role = EXCLUDED.owner_role, is_active = EXCLUDED.is_active, comment = EXCLUDED.comment,
    content_date_column = EXCLUDED.content_date_column, max_content_age_hours = EXCLUDED.max_content_age_hours;
