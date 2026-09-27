-- Переключатель основания покрытия: загрузчик считает и по темпу продаж, и по плану.
-- Этот флаг решает только одно — писать ли строки, которых нет в периметре по темпу (пары, где план
-- есть, а продаж за 30 дней нет). Пока страница без переключателя, такие строки на ней выглядели бы
-- пустыми «ok», поэтому по умолчанию 0; включаем после деплоя страницы, одной правкой в базе.
INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('coverage_write_plan_rows', 0,
        'Kabinet - Coverage Projection: писать ли строки, которых нет в периметре по темпу продаж (только план). 0 — нет, 1 — да. Включать после деплоя переключателя на «Остатках».')
ON CONFLICT (key) DO UPDATE SET note = EXCLUDED.note, updated_at = now();
SELECT key, value, left(note, 60) AS note FROM kabinet_data.reorder_params WHERE key = 'coverage_write_plan_rows';
