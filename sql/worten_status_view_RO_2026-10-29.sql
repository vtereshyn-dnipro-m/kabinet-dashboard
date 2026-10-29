-- Worten во вью статуса данных маркетплейсов (29.10.2026, PR3 #402; решение владельца 29.10.2026, отменяет запись
-- «не добавляем»: «после демо добавляем Worten в представление статусов через claude_code_ro»). РАЗОВОЕ ИСКЛЮЧЕНИЕ
-- из решения владельца 26.10.2026 «писать через claude_code_ro нельзя»: вью kabinet_data.v_marketplace_data_status
-- принадлежит claude_code_ro, а учётка владельца состоит в этой роли без INHERIT и SET — заменить вью может только сам
-- claude_code_ro (то же в sql/kabinet_jobs_sp_2026-10-22_ro.sql).
-- Применяется ПЕРВЫМ, по «применяй», под подключением claude_code_ro:
--   psql "<строка подключения claude_code_ro>" -v ON_ERROR_STOP=1 -f sql/worten_status_view_RO_2026-10-29.sql
-- Потом — sql/worten_page_2026-10-29.sql под учёткой владельца: он проверяет, что ветки Worten во вью уже есть, иначе
-- откатывается (WRT-PT без источников сразу стал бы no_data, и сторож завёл бы marketplace_no_data).
-- Ветки Worten без строки WRT-PT в marketplaces_new ничего не меняют: per_mp строится по маркетплейсам справочника.
-- Определение — живое на 29.10.2026 11:2x (pg_get_viewdef) плюс две ветки: офферы (свежесть — каждый прогон загрузчика)
-- и заказы по стране. Колонки и их порядок прежние; права на вью при CREATE OR REPLACE сохраняются. Только добавляет.
-- Проверено чтением 29.10.2026: новое определение как запрос даёт тем же 20 маркетплейсам те же статусы, что живое вью.

BEGIN;

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
        UNION ALL
         SELECT 'WRT'::text AS text,
            NULL::text AS text,
            'offers'::text AS text,
            max(raw_worten_offers.loaded_at) AS max
           FROM kabinet_data.raw_worten_offers
        UNION ALL
         SELECT 'WRT'::text AS text,
            raw_worten_orders.country,
            'orders'::text AS text,
            max(raw_worten_orders.loaded_at) AS max
           FROM kabinet_data.raw_worten_orders
          GROUP BY raw_worten_orders.country
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

-- Проверка чтением (после применения):
-- SELECT position('raw_worten_offers' in pg_get_viewdef('kabinet_data.v_marketplace_data_status'::regclass)) > 0;   -- t
-- SELECT code, status FROM kabinet_data.v_marketplace_data_status ORDER BY code;   -- статусы как до применения
