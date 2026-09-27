-- Правило свежести на заказы Odoo: из них живёт план снабжения в автозаказе.
--
-- Синк — `loaded_at`: загрузчик переписывает срез целиком двумя прогонами в день (11:30 и 16:30
-- Kyiv, перед Stock Loader в 12:00 и 17:00), поэтому 30 часов ловят пропущенный день.
-- Содержимое — `write_date`, последняя правка заказа в Odoo. Порог 168 часов намеренно большой:
-- тихая неделя без новых заказов бывает, и она не поломка. Это то же различение, что у листа
-- Poland-Spain (там синк 48 ч, содержимое 240 ч): молчание источника и смерть загрузчика —
-- разные сигналы, и мерить их одним порогом значит получать ложные тревоги.
INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, content_date_column,
     max_content_age_hours, owner_role, is_active, comment)
VALUES
    ('dnipro_m.dnipro_m.raw_odoo_purchase_orders', 'loaded_at', 30, 'spark', 'write_date', 168,
     'SUPPLY_DATA_OWNER', true,
     'Заказы Odoo. Основной источник плана снабжения в автозаказе, лист Дарины — запасной.'),
    ('dnipro_m.dnipro_m.raw_odoo_purchase_order_lines', 'loaded_at', 30, 'spark', NULL, NULL,
     'SUPPLY_DATA_OWNER', true,
     'Строки заказов Odoo. Пишутся тем же прогоном, что и заказы.')
ON CONFLICT (table_name) DO UPDATE SET
    date_column = EXCLUDED.date_column,
    max_age_hours = EXCLUDED.max_age_hours,
    source_type = EXCLUDED.source_type,
    content_date_column = EXCLUDED.content_date_column,
    max_content_age_hours = EXCLUDED.max_content_age_hours,
    owner_role = EXCLUDED.owner_role,
    is_active = EXCLUDED.is_active,
    comment = EXCLUDED.comment,
    updated_at = now();
