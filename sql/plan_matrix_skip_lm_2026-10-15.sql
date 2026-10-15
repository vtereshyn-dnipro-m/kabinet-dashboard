-- Plan Matrix: вкладку avg_LM_ES в таблицу аналитика пока не пишем (решение владельца 15.10.2026, вариант «В»).
-- 15.10 утром Leroy Merlin отклонил в каталоге 302 оффера из 357 (PRODUCT_STATUS_REJECTED) — по правилу «цена листинга
-- только у выставленного SKU» цены LM на ноябрь и дальше сократились бы примерно вдвое. Пока аналитик не решит, брать ли
-- цену отклонённого оффера (вариант «Б», отдельный PR), вкладку не трогаем. Снять паузу — value = 0.
-- Ноутбук читает ключи plan_price_sheet_skip_<вкладка> (код с этого PR); без ключа вкладка пишется как обычно.
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at)
VALUES ('plan_price_sheet_skip_LM_ES', 1,
        'Plan Matrix: 1 — вкладку avg_LM_ES в таблицу не писать (пауза до решения по отклонённым офферам LM, 15.10.2026); 0 — писать',
        now())
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = now();
SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'plan_price_sheet_%' ORDER BY key;
