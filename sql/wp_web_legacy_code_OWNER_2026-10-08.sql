-- Wallapop (WP-ES) и сайт (WEB-ES): технические коды рынков. ВЫПОЛНЯЕТ ВЛАДЕЛЕЦ БАЗЫ, ПОСЛЕ того как площадки WP и
-- WEB и маркетплейсы WP-ES и WEB-ES заведены через «Справочники» (08.10.2026).
--
-- 1. marketplaces_new.legacy_code = 'wp_es' / 'web_es': по нему экономика (WP_ES, WEB_ES), паспорт и статус загрузки
--    данных узнают маркетплейс. Без него сторож заведёт «маркетплейс не настроен».
-- 2. Строки в marketplaces_legacy: из них страницы (вью v_marketplaces) берут канал. Канал обязан совпадать с ПОЛНЫМ
--    названием площадки — по нему граница полных дней находит задержку площадки (kpi_day_settle_days_wp / _web).
-- Обе таблицы принадлежат владельцу: роль Кабинета их не правит.
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM kabinet_data.marketplaces_new WHERE code = 'WP-ES') THEN
        RAISE EXCEPTION 'Маркетплейса WP-ES ещё нет: сначала заведите площадку WP и маркетплейс через «Справочники»';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM kabinet_data.marketplaces_new WHERE code = 'WEB-ES') THEN
        RAISE EXCEPTION 'Маркетплейса WEB-ES ещё нет: сначала заведите площадку WEB и маркетплейс через «Справочники»';
    END IF;
END $$;

UPDATE kabinet_data.marketplaces_new SET legacy_code = 'wp_es'  WHERE code = 'WP-ES';
UPDATE kabinet_data.marketplaces_new SET legacy_code = 'web_es' WHERE code = 'WEB-ES';

INSERT INTO kabinet_data.marketplaces_legacy (id, code, name, country, currency, is_active, vat_rate, channel)
SELECT m.id, lower(replace(m.code, '-', '_')), m.name, 'ES', m.currency, true, 0.21, p.full_name
FROM kabinet_data.marketplaces_new m
JOIN kabinet_data.platforms p ON p.short_name = m.platform_short
WHERE m.code IN ('WP-ES', 'WEB-ES')
ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name, channel = EXCLUDED.channel;

-- проверка: две строки — WP-ES · wp_es · Wallapop · WP_ES и WEB-ES · web_es · <название площадки> · WEB_ES
SELECT m.code, m.legacy_code, l.channel, v.marketplace_code, s.status
FROM kabinet_data.marketplaces_new m
JOIN kabinet_data.marketplaces_legacy l ON l.id = m.id
JOIN kabinet_data.v_marketplaces v ON v.id = m.id
JOIN kabinet_data.v_marketplace_data_status s ON s.marketplace_id = m.id
WHERE m.code IN ('WP-ES', 'WEB-ES');
COMMIT;
