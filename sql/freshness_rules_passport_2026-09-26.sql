-- Паспорт данных берёт пороги «устарело» из data_freshness_rules — там они уже живут для сторожа,
-- и второй копии в коде быть не должно. У трёх таблиц, которые читают Обзор и Автозаказ, правила
-- не было: паспорт показывал бы порог «по умолчанию», а сторож их вообще не проверял.
-- Пороги: расчёты Stock Loader идут раз в сутки (38 ч = сутки с запасом на сдвиг прогона),
-- логистика в марже следует за экономикой (96 ч, как у economics_summary с её лагом в 3 дня).
INSERT INTO kabinet_data.data_freshness_rules
    (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment,
     content_date_column, max_content_age_hours)
VALUES
    ('kabinet_data.reorder_recommendations', 'calc_date', 38, 'lakebase', 'SUPPLY_DATA_OWNER', true,
     'Автозаказ: расчёт Kabinet - Stock Loader раз в сутки. calc_date = дата расчёта.', NULL, NULL),
    ('kabinet_data.transfer_recommendations', 'calc_date', 38, 'lakebase', 'SUPPLY_DATA_OWNER', true,
     'Переброски: расчёт Kabinet - Stock Loader раз в сутки. calc_date = дата расчёта.', NULL, NULL),
    ('kabinet_data.economics_logistics', 'updated_at', 48, 'lakebase', 'economics', true,
     'Упаковка и доставка в марже, ячейка 11 Kabinet - Economics Loader. Содержимое следует за экономикой: лаг 3 дня.',
     'sales_date', 96)
ON CONFLICT (table_name) DO UPDATE SET
    date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
    content_date_column = EXCLUDED.content_date_column,
    max_content_age_hours = EXCLUDED.max_content_age_hours,
    is_active = true, comment = EXCLUDED.comment, updated_at = now();
