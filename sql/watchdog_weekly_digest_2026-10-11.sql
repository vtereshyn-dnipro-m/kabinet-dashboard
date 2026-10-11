-- Сводка сторожа: что каждый день, что раз в неделю (решение владельца 11.10.2026).
--
-- В ежедневной сводке 10.10 висело 126 тревог, из них поимённо — пять самых старых, и это всегда были блокировки
-- листингов по 20+ дней. Тревоги, по которым надо действовать сегодня (дефицит раньше поставки, Buy Box, здоровье
-- аккаунта critical/high), тонули под ними. Решение:
--   ежедневно — 🔴 сверка 1:1, новые, «устранено» и то, что требует действия сейчас;
--   по понедельникам одной сводкой — блокировки листингов (группами «рынок × причина»), нет прогноза, нельзя купить,
--   здоровье аккаунта low/medium.
-- Правило — свойство ТИПА тревоги в справочнике, а не список в коде сторожа: так же, как порог ClickUp
-- (clickup_min_severity). Выполнять ПОСЛЕ мержа PR и ДО выкладки сторожа: сторож без этих колонок считает все типы
-- ежедневными, то есть ведёт себя как раньше.

BEGIN;

ALTER TABLE kabinet_data.incident_types
    ADD COLUMN IF NOT EXISTS telegram_digest text NOT NULL DEFAULT 'daily'
        CHECK (telegram_digest IN ('daily', 'weekly')),
    ADD COLUMN IF NOT EXISTS telegram_daily_min_severity text
        CHECK (telegram_daily_min_severity IN ('low', 'medium', 'high', 'critical'));
COMMENT ON COLUMN kabinet_data.incident_types.telegram_digest IS
    'Где висящая тревога этого типа напоминает о себе в Telegram: daily — каждый день в «⏳ висит», weekly — в '
    'понедельничной сводке. Новые и устранённые идут в ежедневное сообщение всегда.';
COMMENT ON COLUMN kabinet_data.incident_types.telegram_daily_min_severity IS
    'Для weekly-типов: тревога с этой важностью и выше остаётся ежедневной. NULL — весь тип раз в неделю.';

UPDATE kabinet_data.incident_types
   SET telegram_digest = 'weekly', telegram_daily_min_severity = NULL,
       updated_at = now(), updated_by = 'claude-code по указанию v.tereshyn'
 WHERE incident_type IN ('listing_pair_blocked', 'missing_forecast', 'buybox_no_offers');
-- здоровье аккаунта: critical и high — каждый день (GB AT_RISK, ES политика листингов), low и medium — раз в неделю
UPDATE kabinet_data.incident_types
   SET telegram_digest = 'weekly', telegram_daily_min_severity = 'high',
       updated_at = now(), updated_by = 'claude-code по указанию v.tereshyn'
 WHERE incident_type = 'account_health';

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at)
VALUES ('watchdog_weekly_digest_dow', '1',
        'День недельной сводки сторожа в Telegram, ISO: 1 — понедельник. Сторож идёт в 13:00 Kyiv.', now())
ON CONFLICT (key) DO NOTHING;

-- TikTok Shop: загрузчика нет, поэтому «нет данных» по TTS-ES — не поломка, а ожидаемое состояние. Отметка живёт на
-- маркетплейсе и гаснет сама: как только придёт первая строка данных, статус снова считается обычным правилом.
ALTER TABLE kabinet_data.marketplace_attributes
    ADD COLUMN IF NOT EXISTS no_loader_since date,
    ADD COLUMN IF NOT EXISTS no_loader_note text;
COMMENT ON COLUMN kabinet_data.marketplace_attributes.no_loader_since IS
    'С какой даты известно, что загрузчика данных по маркетплейсу нет. Пока данных нет вовсе, статус — no_loader, '
    'сторож не тревожит; первая строка данных возвращает обычную проверку.';

INSERT INTO kabinet_data.marketplace_attributes (marketplace_id, no_loader_since, no_loader_note, updated_at, updated_by)
SELECT id, DATE '2026-10-11', 'Загрузчика TikTok Shop нет — проверка данных выключена до первой загрузки.', now(),
       'claude-code по указанию v.tereshyn'
  FROM kabinet_data.marketplaces_new WHERE code = 'TTS-ES'
ON CONFLICT (marketplace_id) DO UPDATE
   SET no_loader_since = EXCLUDED.no_loader_since, no_loader_note = EXCLUDED.no_loader_note,
       updated_at = now(), updated_by = EXCLUDED.updated_by;

-- Вью то же, что с 08.10.2026 (Wallapop и сайт), плюс статус 'no_loader' и колонка no_loader_note в конце: читатели
-- выбирают колонки по имени, порядок прежних не меняется.
CREATE OR REPLACE VIEW kabinet_data.v_marketplace_data_status AS
 WITH src AS (
         SELECT 'AMZ'::text AS platform,
            orders_history.marketplace_code AS country,
            'orders'::text AS source,
            max(orders_history.purchase_date) AS last_at
           FROM kabinet_data.orders_history
          GROUP BY orders_history.marketplace_code
        UNION ALL
         SELECT 'AMZ'::text AS text,
            sales_traffic_daily.marketplace,
            'sales_traffic'::text AS text,
            max(sales_traffic_daily.loaded_at) AS max
           FROM kabinet_data.sales_traffic_daily
          GROUP BY sales_traffic_daily.marketplace
        UNION ALL
         SELECT
                CASE
                    WHEN ads_market_daily.marketplace ~ '^[A-Z]{2}$'::text THEN 'AMZ'::text
                    ELSE split_part(ads_market_daily.marketplace, '_'::text, 1)
                END AS split_part,
                CASE
                    WHEN ads_market_daily.marketplace ~ '^[A-Z]{2}$'::text THEN ads_market_daily.marketplace
                    ELSE split_part(ads_market_daily.marketplace, '_'::text, 2)
                END AS split_part,
            'ads'::text AS text,
            max(ads_market_daily.updated_at) AS max
           FROM kabinet_data.ads_market_daily
          GROUP BY ads_market_daily.marketplace
        UNION ALL
         SELECT split_part(raw_mm_offers.marketplace_code, '-'::text, 1) AS split_part,
            split_part(raw_mm_offers.marketplace_code, '-'::text, 2) AS split_part,
            'offers'::text AS text,
            max(raw_mm_offers.loaded_at) AS max
           FROM kabinet_data.raw_mm_offers
          GROUP BY raw_mm_offers.marketplace_code
        UNION ALL
         SELECT
                CASE
                    WHEN raw_mm_order_lines.country = 'ES_B2B'::text THEN 'MMB'::text
                    ELSE 'MM'::text
                END AS platform,
                CASE
                    WHEN raw_mm_order_lines.country = 'ES_B2B'::text THEN 'ES'::text
                    ELSE raw_mm_order_lines.country
                END AS country,
            'orders'::text AS text,
            max(raw_mm_order_lines.loaded_at) AS max
           FROM kabinet_data.raw_mm_order_lines
          GROUP BY raw_mm_order_lines.country
        UNION ALL
         SELECT 'CF'::text AS text,
            raw_cf_order_lines.country,
            'orders'::text AS text,
            max(raw_cf_order_lines.loaded_at) AS max
           FROM kabinet_data.raw_cf_order_lines
          GROUP BY raw_cf_order_lines.country
        UNION ALL
         SELECT 'CF'::text AS text,
            NULL::text AS text,
            'offers'::text AS text,
            max(raw_cf_offers.loaded_at) AS max
           FROM kabinet_data.raw_cf_offers
        UNION ALL
         SELECT 'LM'::text AS text,
            raw_lm_orders.customer_country,
            'orders'::text AS text,
            max(raw_lm_orders.loaded_at) AS max
           FROM kabinet_data.raw_lm_orders
          GROUP BY raw_lm_orders.customer_country
        UNION ALL
         SELECT 'LM'::text AS text,
            NULL::text AS text,
            'offers'::text AS text,
            max(raw_lm_offers.loaded_at) AS max
           FROM kabinet_data.raw_lm_offers
        UNION ALL
         SELECT p_1.short_name,
            NULLIF(s.warehouse_country::text, ''::text) AS "nullif",
            'stock'::text AS text,
            max(s.created_at) AS max
           FROM kabinet_data.stock_local s
             JOIN kabinet_data.platforms p_1 ON p_1.full_name = s.channel
          WHERE s.source <> 'ledger-summary'::text
          GROUP BY p_1.short_name, (NULLIF(s.warehouse_country::text, ''::text))
        UNION ALL
         SELECT
                CASE raw_odoo_channel_sales.marketplace
                    WHEN 'WP_ES'::text THEN 'WP'::text
                    WHEN 'WEB_ES'::text THEN 'WEB'::text
                    ELSE NULL::text
                END AS platform,
            'ES'::text AS country,
            'orders'::text AS source,
            max(raw_odoo_channel_sales.loaded_at) AS max
           FROM kabinet_data.raw_odoo_channel_sales
          GROUP BY raw_odoo_channel_sales.marketplace
        ), per_mp AS (
         SELECT m_1.id,
            max(s.last_at) AS last_data_at,
            (array_agg(s.source ORDER BY s.last_at DESC NULLS LAST))[1] AS last_source,
            jsonb_object_agg(s.source, s.last_at) FILTER (WHERE s.source IS NOT NULL) AS by_source
           FROM kabinet_data.marketplaces_new m_1
             LEFT JOIN src s ON s.platform = m_1.platform_short::text AND (s.country = m_1.country_alpha2::text OR s.country IS NULL)
          GROUP BY m_1.id
        ), win AS (
         SELECT COALESCE(( SELECT reorder_params.value::integer AS value
                   FROM kabinet_data.reorder_params
                  WHERE reorder_params.key = 'mp_no_data_days'::text), 14) AS days
        )
 SELECT m.id AS marketplace_id,
    m.code,
    m.is_active,
    array_remove(ARRAY[
        CASE
            WHEN m.legacy_code IS NULL OR m.legacy_code::text = ''::text THEN 'legacy_code'::text
            ELSE NULL::text
        END,
        CASE
            WHEN m.platform_short::text = 'AMZ'::text AND (m.amazon_id IS NULL OR m.amazon_id = ''::text) THEN 'amazon_id'::text
            ELSE NULL::text
        END,
        CASE
            WHEN m.platform_short::text = 'AMZ'::text AND NOT m.sync_economics THEN 'sync_economics'::text
            ELSE NULL::text
        END], NULL::text) AS config_missing,
    p.last_data_at,
    p.last_source,
    p.by_source,
    w.days AS window_days,
        CASE
            WHEN NOT m.is_active THEN 'inactive'::text
            WHEN m.legacy_code IS NULL OR m.legacy_code::text = ''::text OR m.platform_short::text = 'AMZ'::text AND (m.amazon_id IS NULL OR m.amazon_id = ''::text OR NOT m.sync_economics) THEN 'no_config'::text
            WHEN a.trial_until >= CURRENT_DATE AND NOT COALESCE(p.by_source ? 'orders'::text, false) THEN 'trial'::text
            -- загрузчика нет и данных не было ни разу: ожидаемо, не тревога; первая строка данных снимает отметку
            WHEN a.no_loader_since IS NOT NULL AND p.last_data_at IS NULL THEN 'no_loader'::text
            WHEN p.last_data_at IS NULL OR p.last_data_at < (now() - make_interval(days => w.days)) THEN 'no_data'::text
            ELSE 'ok'::text
        END AS status,
    a.trial_until,
    a.no_loader_note
   FROM kabinet_data.marketplaces_new m
     JOIN per_mp p ON p.id = m.id
     CROSS JOIN win w
     LEFT JOIN kabinet_data.marketplace_attributes a ON a.marketplace_id = m.id;

COMMIT;
