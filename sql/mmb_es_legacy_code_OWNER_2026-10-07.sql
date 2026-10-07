-- ManoMano Pro Spain (MMB-ES): технический код рынка. ВЫПОЛНЯЕТ ВЛАДЕЛЕЦ БАЗЫ, ПОСЛЕ того как площадка MMB и
-- маркетплейс MMB-ES заведены через «Справочники» (07.10.2026).
--
-- 1. marketplaces_new.legacy_code = 'mmb_es': по нему экономика (MMB_ES), план-факт и статус загрузки данных узнают
--    маркетплейс. Без него сторож заведёт «маркетплейс не настроен».
-- 2. Строка в marketplaces_legacy: из неё страницы Кабинета (вью v_marketplaces) берут канал — без неё продажи
--    MMB_ES на «Обзоре» попали бы в «Другое». id тот же, что у marketplaces_new, канал = название площадки.
-- 3. Пробный период до 31.10.2026 (тариф Booster, на 07.10 оставалось 24 дня): пока он идёт и заказов нет, сторож
--    молчит. Можно и в карточке маркетплейса — блок «Пробный период».
-- Обе таблицы (1, 2) принадлежат владельцу: роль Кабинета их не правит.
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM kabinet_data.marketplaces_new WHERE code = 'MMB-ES') THEN
        RAISE EXCEPTION 'Маркетплейса MMB-ES ещё нет: сначала заведите площадку MMB и маркетплейс через «Справочники»';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM kabinet_data.platforms WHERE short_name = 'MMB' AND full_name = 'ManoMano Pro') THEN
        RAISE EXCEPTION 'Площадка MMB должна называться «ManoMano Pro» — по названию площадки страницы определяют канал';
    END IF;
END $$;

UPDATE kabinet_data.marketplaces_new SET legacy_code = 'mmb_es' WHERE code = 'MMB-ES';

INSERT INTO kabinet_data.marketplaces_legacy (id, code, name, country, currency, is_active, vat_rate, channel)
SELECT id, 'mmb_es', name, 'ES', currency, true, 0.21, 'ManoMano Pro'
FROM kabinet_data.marketplaces_new WHERE code = 'MMB-ES'
ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name, channel = EXCLUDED.channel;

INSERT INTO kabinet_data.marketplace_attributes (marketplace_id, trial_until, trial_note)
SELECT id, DATE '2026-10-31', 'тариф Booster, пробный период' FROM kabinet_data.marketplaces_new WHERE code = 'MMB-ES'
ON CONFLICT (marketplace_id) DO UPDATE SET trial_until = EXCLUDED.trial_until, trial_note = EXCLUDED.trial_note;

-- проверка: должно вернуть MMB-ES · mmb_es · ManoMano Pro · MMB_ES · trial
SELECT m.code, m.legacy_code, l.channel, v.marketplace_code, s.status
FROM kabinet_data.marketplaces_new m
JOIN kabinet_data.marketplaces_legacy l ON l.id = m.id
JOIN kabinet_data.v_marketplaces v ON v.id = m.id
JOIN kabinet_data.v_marketplace_data_status s ON s.marketplace_id = m.id
WHERE m.code = 'MMB-ES';
COMMIT;
