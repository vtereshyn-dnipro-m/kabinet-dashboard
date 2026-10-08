-- Wallapop и сайт из Odoo (08.10.2026): реплика строк, продажи с НДС, статус загрузки маркетплейса, задержка дня.
-- Применять ПОСЛЕ мержа, до первого прогона джобы Kabinet - Odoo Channels Loader. Пишет загрузчик под владельцем.
-- Вью пересобраны из их текущих определений в базе с одной дописанной веткой — остальное без изменений.
BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.raw_odoo_channel_sales (
    order_number       text    NOT NULL,
    line_no            integer NOT NULL,       -- порядковый номер строки в выгрузке: своего id у строки Odoo нет
    sales_team         text    NOT NULL,       -- команда продаж Odoo: Wallapop / Website
    marketplace        text    NOT NULL,       -- код рынка экономики: WP_ES / WEB_ES
    order_state        text,                   -- sale / cancel / draft — в продажи идёт только sale
    order_date         date,                   -- день заказа по Мадриду
    date_order_madrid  timestamp,
    sku                text,                   -- пусто — строка доставки; woo_discount — скидка WooCommerce
    product_title      text,
    qty                numeric,
    price_unit         numeric,
    price_subtotal     numeric,                -- без НДС
    price_total        numeric,                -- с НДС
    order_amount_total numeric,
    loaded_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (order_number, line_no)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.raw_odoo_channel_sales TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.raw_odoo_channel_sales TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.raw_odoo_channel_sales TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- продажи с НДС по всем каналам (карточка «Обзора», знаменатель TACOS): + Wallapop и сайт, тем же отбором, что
-- у витрины Power BI — заказы sale, строки товаров без скидки и доставки
CREATE OR REPLACE VIEW kabinet_data.v_sales_vat_incl_daily AS
 SELECT v_sales_traffic_daily_eur.snapshot_date AS date,
    v_sales_traffic_daily_eur.marketplace,
    sum(v_sales_traffic_daily_eur.ordered_sales) AS sales_vat_incl
   FROM kabinet_data.v_sales_traffic_daily_eur
  GROUP BY v_sales_traffic_daily_eur.snapshot_date, v_sales_traffic_daily_eur.marketplace
UNION ALL
 SELECT (o.created_date)::date AS date,
    'LM'::text AS marketplace,
    (sum(l.price))::double precision AS sales_vat_incl
   FROM (kabinet_data.raw_lm_order_lines l
     JOIN kabinet_data.raw_lm_orders o USING (order_id))
  WHERE (l.order_line_state <> ALL (ARRAY['REFUNDED'::text, 'CANCELED'::text, 'REFUSED'::text]))
  GROUP BY ((o.created_date)::date)
UNION ALL
 SELECT raw_mm_order_lines.order_date AS date,
    kabinet_data.mm_market_code(raw_mm_order_lines.country) AS marketplace,
    sum(raw_mm_order_lines.total_price) AS sales_vat_incl
   FROM kabinet_data.raw_mm_order_lines
  WHERE (upper(COALESCE(raw_mm_order_lines.order_status, ''::text)) <> ALL (ARRAY['CANCELED'::text, 'REFUSED'::text]))
  GROUP BY raw_mm_order_lines.order_date, (kabinet_data.mm_market_code(raw_mm_order_lines.country))
UNION ALL
 SELECT raw_cf_order_lines.order_date AS date,
    ('CF_'::text || upper(raw_cf_order_lines.country)) AS marketplace,
    sum(raw_cf_order_lines.total_price) AS sales_vat_incl
   FROM kabinet_data.raw_cf_order_lines
  WHERE (upper(COALESCE(raw_cf_order_lines.order_status, ''::text)) <> ALL (ARRAY['CANCELED'::text, 'REFUSED'::text]))
  GROUP BY raw_cf_order_lines.order_date, ('CF_'::text || upper(raw_cf_order_lines.country))
UNION ALL
 SELECT raw_odoo_channel_sales.order_date AS date,
    raw_odoo_channel_sales.marketplace,
    sum(raw_odoo_channel_sales.price_total) AS sales_vat_incl
   FROM kabinet_data.raw_odoo_channel_sales
  WHERE raw_odoo_channel_sales.order_state = 'sale'::text AND raw_odoo_channel_sales.sku IS NOT NULL
    AND raw_odoo_channel_sales.sku <> 'woo_discount'::text
  GROUP BY raw_odoo_channel_sales.order_date, raw_odoo_channel_sales.marketplace;

-- статус загрузки маркетплейса: + источник «заказы» Wallapop (WP) и сайта (WEB) по времени загрузки реплики
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
                    WHEN (ads_market_daily.marketplace ~ '^[A-Z]{2}$'::text) THEN 'AMZ'::text
                    ELSE split_part(ads_market_daily.marketplace, '_'::text, 1)
                END AS split_part,
                CASE
                    WHEN (ads_market_daily.marketplace ~ '^[A-Z]{2}$'::text) THEN ads_market_daily.marketplace
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
                    WHEN (raw_mm_order_lines.country = 'ES_B2B'::text) THEN 'MMB'::text
                    ELSE 'MM'::text
                END AS platform,
                CASE
                    WHEN (raw_mm_order_lines.country = 'ES_B2B'::text) THEN 'ES'::text
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
            NULLIF((s.warehouse_country)::text, ''::text) AS "nullif",
            'stock'::text AS text,
            max(s.created_at) AS max
           FROM (kabinet_data.stock_local s
             JOIN kabinet_data.platforms p_1 ON ((p_1.full_name = s.channel)))
          WHERE (s.source <> 'ledger-summary'::text)
          GROUP BY p_1.short_name, NULLIF((s.warehouse_country)::text, ''::text)
        UNION ALL
         SELECT CASE raw_odoo_channel_sales.marketplace WHEN 'WP_ES'::text THEN 'WP'::text WHEN 'WEB_ES'::text THEN 'WEB'::text ELSE NULL::text END AS platform,
            'ES'::text AS country,
            'orders'::text AS source,
            max(raw_odoo_channel_sales.loaded_at) AS max
           FROM kabinet_data.raw_odoo_channel_sales
          GROUP BY raw_odoo_channel_sales.marketplace
        ), per_mp AS (
         SELECT m_1.id,
            max(s.last_at) AS last_data_at,
            (array_agg(s.source ORDER BY s.last_at DESC NULLS LAST))[1] AS last_source,
            jsonb_object_agg(s.source, s.last_at) FILTER (WHERE (s.source IS NOT NULL)) AS by_source
           FROM (kabinet_data.marketplaces_new m_1
             LEFT JOIN src s ON (((s.platform = (m_1.platform_short)::text) AND ((s.country = (m_1.country_alpha2)::text) OR (s.country IS NULL)))))
          GROUP BY m_1.id
        ), win AS (
         SELECT COALESCE(( SELECT (reorder_params.value)::integer AS value
                   FROM kabinet_data.reorder_params
                  WHERE (reorder_params.key = 'mp_no_data_days'::text)), 14) AS days
        )
 SELECT m.id AS marketplace_id,
    m.code,
    m.is_active,
    array_remove(ARRAY[
        CASE
            WHEN ((m.legacy_code IS NULL) OR ((m.legacy_code)::text = ''::text)) THEN 'legacy_code'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (((m.platform_short)::text = 'AMZ'::text) AND ((m.amazon_id IS NULL) OR (m.amazon_id = ''::text))) THEN 'amazon_id'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (((m.platform_short)::text = 'AMZ'::text) AND (NOT m.sync_economics)) THEN 'sync_economics'::text
            ELSE NULL::text
        END], NULL::text) AS config_missing,
    p.last_data_at,
    p.last_source,
    p.by_source,
    w.days AS window_days,
        CASE
            WHEN (NOT m.is_active) THEN 'inactive'::text
            WHEN ((m.legacy_code IS NULL) OR ((m.legacy_code)::text = ''::text) OR (((m.platform_short)::text = 'AMZ'::text) AND ((m.amazon_id IS NULL) OR (m.amazon_id = ''::text) OR (NOT m.sync_economics)))) THEN 'no_config'::text
            WHEN ((a.trial_until >= CURRENT_DATE) AND (NOT COALESCE((p.by_source ? 'orders'::text), false))) THEN 'trial'::text
            WHEN ((p.last_data_at IS NULL) OR (p.last_data_at < (now() - make_interval(days => w.days)))) THEN 'no_data'::text
            ELSE 'ok'::text
        END AS status,
    a.trial_until
   FROM (((kabinet_data.marketplaces_new m
     JOIN per_mp p ON ((p.id = m.id)))
     CROSS JOIN win w)
     LEFT JOIN kabinet_data.marketplace_attributes a ON ((a.marketplace_id = m.id)));

-- граница полных дней: Odoo отдаёт вчерашний день целиком к утреннему прогону — как Mirakl, через сутки.
-- Без этих строк площадки взяли бы общее значение 2 и сдвинули бы период всего «Обзора» на день назад
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('kpi_day_settle_days_wp', 1, 'Wallapop (Odoo): день полон через сутки — выгрузка Odoo 10:11, загрузчик 10:30'),
  ('kpi_day_settle_days_web', 1, 'Сайт (Odoo): день полон через сутки — выгрузка Odoo 10:11, загрузчик 10:30')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;

-- свежесть реплики: синк по loaded_at; содержимое (дата заказа) не проверяем — у сайта бывают недели без заказов
INSERT INTO kabinet_data.data_freshness_rules (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment)
VALUES ('kabinet_data.raw_odoo_channel_sales', 'loaded_at', 26, 'lakebase-replica', 'data', true,
        'Wallapop и сайт из Odoo: Kabinet - Odoo Channels Loader 10:30 Kyiv. Синк — loaded_at; у сайта бывают недели без заказов, поэтому дату заказа не проверяем.')
ON CONFLICT (table_name) DO UPDATE SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
    source_type = EXCLUDED.source_type, comment = EXCLUDED.comment, is_active = true;
COMMIT;
