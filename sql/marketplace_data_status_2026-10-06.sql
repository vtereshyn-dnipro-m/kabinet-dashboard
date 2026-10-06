-- Маркетплейс, по которому данные не загружаются (06.10.2026, решение владельца).
--
-- Новый маркетплейс, заведённый формой в «Справочниках», получает только поля ТЗ 003: технические колонки
-- (`legacy_code`, у Amazon — `amazon_id` и флаги загрузчиков) пустые, и ни один загрузчик его сам не подхватит.
-- Это намеренно, но об этом надо узнать сразу, а не через месяц по пустому отчёту. Поэтому пометка в списке и
-- в карточке маркетплейса и инцидент сторожа — оба читают ЭТО вью, второго написания правила нет.
--
-- Правило (владелец 06.10.2026) — для активных маркетплейсов:
--   (а) нет технических настроек: внутреннего кода (`legacy_code`), а у Amazon ещё id рынка (`amazon_id`)
--       и включённой загрузки экономики (`sync_economics`);
--   (б) за `reorder_params.mp_no_data_days` (14) дней по нему не пришло ни одной строки ни из одного
--       источника: заказы, офферы, остатки, реклама, Sales & Traffic.
-- Рынок с нулём продаж, но со свежими офферами или остатками НЕ помечается: данные идут, продаж просто нет.
--
-- Что считается «пришло»: время загрузки строки (`loaded_at` / `updated_at` / `created_at`), а у заказов
-- Amazon — дата заказа: `orders_history.last_updated` это отметка нашего прогона, одинаковая у всех строк, и
-- «свежей» она была бы у любого рынка (AGENTS.md).
-- Остаток FBA сюда НЕ входит: он общий на весь pan-EU и ни про один рынок отдельно ничего не говорит — иначе
-- новый AMZ-рынок без единой своей строки выглядел бы живым.
-- Источник без страны (офферы Carrefour и Leroy Merlin, заказы LM без страны покупателя) относится ко всем
-- маркетплейсам своей площадки: у этих площадок сейчас по одному рынку.

INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('mp_no_data_days', 14, 'Маркетплейс помечается «данные не загружаются», если за столько дней по нему не пришло ни одной строки ни из одного источника (заказы, офферы, остатки, реклама, Sales & Traffic). Читают «Справочники → Маркетплейсы» и сторож.')
ON CONFLICT (key) DO NOTHING;

CREATE OR REPLACE VIEW kabinet_data.v_marketplace_data_status AS
WITH src AS (
    -- Amazon: заказы (дата заказа), Sales & Traffic, реклама SP/SB/SD
    SELECT 'AMZ'::text AS platform, marketplace_code::text AS country, 'orders'::text AS source,
           max(purchase_date)::timestamptz AS last_at
      FROM kabinet_data.orders_history GROUP BY marketplace_code
    UNION ALL
    SELECT 'AMZ', marketplace::text, 'sales_traffic', max(loaded_at) FROM kabinet_data.sales_traffic_daily GROUP BY marketplace
    UNION ALL
    SELECT CASE WHEN marketplace ~ '^[A-Z]{2}$' THEN 'AMZ' ELSE split_part(marketplace, '_', 1) END,
           CASE WHEN marketplace ~ '^[A-Z]{2}$' THEN marketplace ELSE split_part(marketplace, '_', 2) END,
           'ads', max(updated_at)
      FROM kabinet_data.ads_market_daily GROUP BY marketplace
    UNION ALL
    -- ManoMano
    SELECT split_part(marketplace_code, '-', 1), split_part(marketplace_code, '-', 2), 'offers', max(loaded_at)
      FROM kabinet_data.raw_mm_offers GROUP BY marketplace_code
    UNION ALL
    SELECT 'MM', country, 'orders', max(loaded_at) FROM kabinet_data.raw_mm_order_lines GROUP BY country
    UNION ALL
    -- Carrefour
    SELECT 'CF', country, 'orders', max(loaded_at) FROM kabinet_data.raw_cf_order_lines GROUP BY country
    UNION ALL
    SELECT 'CF', NULL, 'offers', max(loaded_at) FROM kabinet_data.raw_cf_offers
    UNION ALL
    -- Leroy Merlin
    SELECT 'LM', customer_country, 'orders', max(loaded_at) FROM kabinet_data.raw_lm_orders GROUP BY customer_country
    UNION ALL
    SELECT 'LM', NULL, 'offers', max(loaded_at) FROM kabinet_data.raw_lm_offers
    UNION ALL
    -- остатки офферов Mirakl (не FBA): канал называется полным именем площадки
    SELECT p.short_name, NULLIF(s.warehouse_country, ''), 'stock', max(s.created_at)
      FROM kabinet_data.stock_local s
      JOIN kabinet_data.platforms p ON p.full_name = s.channel
     WHERE s.source <> 'ledger-summary'
     GROUP BY p.short_name, NULLIF(s.warehouse_country, '')
),
per_mp AS (
    SELECT m.id,
           max(s.last_at) AS last_data_at,
           (array_agg(s.source ORDER BY s.last_at DESC NULLS LAST))[1] AS last_source,
           jsonb_object_agg(s.source, s.last_at) FILTER (WHERE s.source IS NOT NULL) AS by_source
      FROM kabinet_data.marketplaces_new m
      LEFT JOIN src s ON s.platform = m.platform_short
                     AND (s.country = m.country_alpha2 OR s.country IS NULL)
     GROUP BY m.id
),
win AS (
    SELECT COALESCE((SELECT value::int FROM kabinet_data.reorder_params WHERE key = 'mp_no_data_days'), 14) AS days
)
SELECT m.id AS marketplace_id, m.code, m.is_active,
       array_remove(ARRAY[
           CASE WHEN m.legacy_code IS NULL OR m.legacy_code = '' THEN 'legacy_code' END,
           CASE WHEN m.platform_short = 'AMZ' AND (m.amazon_id IS NULL OR m.amazon_id = '') THEN 'amazon_id' END,
           CASE WHEN m.platform_short = 'AMZ' AND NOT m.sync_economics THEN 'sync_economics' END
       ], NULL) AS config_missing,
       p.last_data_at, p.last_source, p.by_source, w.days AS window_days,
       CASE
           WHEN NOT m.is_active THEN 'inactive'
           WHEN m.legacy_code IS NULL OR m.legacy_code = ''
                OR (m.platform_short = 'AMZ' AND (m.amazon_id IS NULL OR m.amazon_id = '' OR NOT m.sync_economics))
                THEN 'no_config'
           WHEN p.last_data_at IS NULL OR p.last_data_at < now() - make_interval(days => w.days) THEN 'no_data'
           ELSE 'ok'
       END AS status
  FROM kabinet_data.marketplaces_new m
  JOIN per_mp p ON p.id = m.id
 CROSS JOIN win w;

GRANT SELECT ON kabinet_data.v_marketplace_data_status TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_marketplace_data_status TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Тип инцидента для сторожа: название и смысл на экране «Справочники → Алерты». ClickUp не включён (список
-- пуст) — тревога уходит в Telegram; включить можно на том же экране.
INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, due_days, title, description, watch_close, updated_by)
VALUES ('marketplace_no_data', 'task', 'High', 1, 'Маркетплейс без данных',
        'По активному маркетплейсу данные не загружаются: нет технических настроек подключения (внутренний код, у Amazon — id рынка и загрузка экономики) или за 14 дней не пришло ни одной строки ни из одного источника — заказы, офферы, остатки, реклама, Sales & Traffic. Нужна настройка подключения. Закрывается сама, когда данные пошли или маркетплейс ушёл в архив.',
        true, 'claude-code по указанию v.tereshyn')
ON CONFLICT (incident_type) DO NOTHING;
