-- Plan Matrix, вариант «Б» (ждёт решения аналитика): цена оффера Leroy Merlin, выключенного каталогом площадки
-- (PRODUCT_STATUS_REJECTED / PRODUCT_STATUS_NEW), для плана сохраняется. 1 — брать, 0 — нет (как до 15.10.2026).
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at)
VALUES ('plan_price_lm_rejected_offer', 1,
        'Plan Matrix: 1 — у оффера LM, выключенного каталогом площадки (REJECTED/NEW), цена для плана сохраняется; 0 — нет',
        now())
ON CONFLICT (key) DO NOTHING;
SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'plan_price_lm_rejected_offer';
