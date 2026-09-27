-- Окно перечитывания у загрузчика отгрузок — настройка, а не константа в коде (AGENTS.md).
-- Отсюда же делается разовый добор истории: поднять значение, прогнать джобу, вернуть обратно.
-- Строки отчёта доезжают с задержкой, поэтому хвост перечитываем ежедневно, а не берём только вчера.
INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('fba_shipments_window_days', 14,
        'Kabinet - FBA Shipments Loader: сколько суток назад перечитывать отчёт отгрузок FBA. Для добора истории поднять разово и вернуть.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();

SELECT key, value, note FROM kabinet_data.reorder_params WHERE key = 'fba_shipments_window_days';
