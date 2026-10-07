-- ManoMano Pro (B2B Испания, договор 70159079) — 07.10.2026, решение владельца, согласовано с Дариной.
-- B2B-заказы лежат в тех же сырых таблицах ManoMano с country = 'ES_B2B' (её ES-витрины их не видят), код рынка
-- экономики — MMB_ES. Код рынка из страны ManoMano раньше собирался в трёх вьюхах как 'MM_' || страна, и для
-- 'ES_B2B' дал бы 'MM_ES_B2B'. Теперь это одна функция: правило в одном месте.
CREATE OR REPLACE FUNCTION kabinet_data.mm_market_code(country text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE upper(country) WHEN 'ES_B2B' THEN 'MMB_ES' ELSE 'MM_' || upper(country) END
$$;
GRANT EXECUTE ON FUNCTION kabinet_data.mm_market_code(text) TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb",
    "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- «Пробный период» маркетплейса: пока он идёт и заказов ещё не было, статус данных — 'trial', и сторож
-- (тревожит только на no_config / no_data) молчит. Первый заказ или конец периода возвращают обычные правила.
ALTER TABLE kabinet_data.marketplace_attributes
    ADD COLUMN IF NOT EXISTS trial_until date,
    ADD COLUMN IF NOT EXISTS trial_note  text;

-- v_sales_vat_incl_daily: код рынка ManoMano — через mm_market_code (2 мест)
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
  GROUP BY raw_mm_order_lines.order_date, kabinet_data.mm_market_code(raw_mm_order_lines.country)
UNION ALL
 SELECT raw_cf_order_lines.order_date AS date,
    ('CF_'::text || upper(raw_cf_order_lines.country)) AS marketplace,
    sum(raw_cf_order_lines.total_price) AS sales_vat_incl
   FROM kabinet_data.raw_cf_order_lines
  WHERE (upper(COALESCE(raw_cf_order_lines.order_status, ''::text)) <> ALL (ARRAY['CANCELED'::text, 'REFUSED'::text]))
  GROUP BY raw_cf_order_lines.order_date, ('CF_'::text || upper(raw_cf_order_lines.country));

-- v_returns_cogs_credit: код рынка ManoMano — через mm_market_code (1 мест)
CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
 WITH fba AS (
         SELECT r.return_date,
            r.marketplace,
            kabinet_data.sku_cogs_key(r.sku) AS norm_sku,
            (r.quantity)::numeric AS qty,
            'fba'::text AS source
           FROM kabinet_data.raw_amazon_returns r
          WHERE ((r.fulfillment_type = 'FBA'::text) AND (upper(r.disposition) = 'SELLABLE'::text))
        ), odoo AS (
         SELECT (o.move_date)::date AS return_date,
            o.product_code,
                CASE
                    WHEN (o.dest_location ~~ 'WH-1/%'::text) THEN o.quantity
                    ELSE (COALESCE(d.qty_to_good, (0)::numeric) + COALESCE(d.qty_sold_intercompany, (0)::numeric))
                END AS qty,
                CASE
                    WHEN (o.dest_location ~~ 'WH-1/%'::text) THEN 'odoo_madrid'::text
                    ELSE 'odoo_def'::text
                END AS source,
            btrim(COALESCE(o.client_order_ref, o.sale_origin)) AS ref
           FROM (kabinet_data.raw_odoo_customer_returns o
             LEFT JOIN kabinet_data.odoo_return_def_outcomes d ON ((d.return_move_id = o.move_id)))
          WHERE (((o.dest_location ~~ 'WH-1/%'::text) OR (o.dest_location ~~ 'DEF/WH-1%'::text)) AND (o.product_code IS NOT NULL) AND (o.quantity > (0)::numeric))
        ), amz_mk AS (
         SELECT DISTINCT ON (orders_history.order_id) orders_history.order_id,
            orders_history.marketplace_code
           FROM kabinet_data.orders_history
          WHERE (orders_history.order_id IN ( SELECT regexp_replace(odoo.ref, '^FBM'::text, ''::text) AS regexp_replace
                   FROM odoo))
          ORDER BY orders_history.order_id, orders_history.last_updated DESC
        ), mm_mk AS (
         SELECT DISTINCT ON (raw_mm_order_lines.order_ref) raw_mm_order_lines.order_ref,
            kabinet_data.mm_market_code(raw_mm_order_lines.country) AS marketplace
           FROM kabinet_data.raw_mm_order_lines
          ORDER BY raw_mm_order_lines.order_ref, raw_mm_order_lines.loaded_at DESC
        ), madrid AS (
         SELECT o.return_date,
                CASE
                    WHEN (o.ref ~ '^(FBM)?\d{3}-\d{7}-\d{7}$'::text) THEN a_1.marketplace_code
                    WHEN (o.ref ~ '^M\d{12}$'::text) THEN m.marketplace
                    WHEN (o.ref ~ '^\d{3}-\d+L\d+-[A-Z]$'::text) THEN 'LM'::text
                    WHEN (o.ref ~ '^\d{8}-[A-Z]$'::text) THEN 'CF_ES'::text
                    ELSE NULL::text
                END AS marketplace,
            kabinet_data.sku_cogs_key(o.product_code) AS norm_sku,
            o.qty,
            o.source
           FROM ((odoo o
             LEFT JOIN amz_mk a_1 ON ((a_1.order_id = regexp_replace(o.ref, '^FBM'::text, ''::text))))
             LEFT JOIN mm_mk m ON ((m.order_ref = o.ref)))
          WHERE (o.qty > (0)::numeric)
        ), allr AS (
         SELECT fba.return_date,
            fba.marketplace,
            fba.norm_sku,
            fba.qty,
            fba.source
           FROM fba
        UNION ALL
         SELECT madrid.return_date,
            madrid.marketplace,
            madrid.norm_sku,
            madrid.qty,
            madrid.source
           FROM madrid
          WHERE (madrid.marketplace IS NOT NULL)
        )
 SELECT a.return_date,
    a.marketplace,
    a.norm_sku,
    (sum(a.qty))::integer AS sellable_units,
    max(c.cogs) AS unit_cogs,
    sum((a.qty * c.cogs)) AS cogs_credit,
    a.source
   FROM (allr a
     JOIN kabinet_data.sku_cogs_current c ON ((c.norm_sku = a.norm_sku)))
  GROUP BY a.return_date, a.marketplace, a.norm_sku, a.source;

-- v_sku_sales_vat_incl_daily: MMB_ES — тоже канал Mirakl
CREATE OR REPLACE VIEW kabinet_data.v_sku_sales_vat_incl_daily AS
 SELECT a.snapshot_date AS date,
    a.marketplace,
    kabinet_data.amz_econ_key(a.sku) AS norm_sku,
    sum(kabinet_data.to_eur((a.ordered_sales)::double precision,
        CASE a.marketplace
            WHEN 'GB'::text THEN 'GBP'::text
            WHEN 'SE'::text THEN 'SEK'::text
            WHEN 'PL'::text THEN 'PLN'::text
            ELSE 'EUR'::text
        END, a.snapshot_date)) AS sales_vat_incl
   FROM kabinet_data.sales_traffic_asin a
  WHERE (kabinet_data.amz_econ_key(a.sku) <> ''::text)
  GROUP BY a.snapshot_date, a.marketplace, (kabinet_data.amz_econ_key(a.sku))
UNION ALL
 SELECT e.sales_date AS date,
    e.marketplace,
    e.norm_sku,
    (sum(e.ordered_product_sales) * max((v.sales_vat_incl / NULLIF(t.ex_vat, (0)::double precision)))) AS sales_vat_incl
   FROM ((kabinet_data.v_economics_summary_eur e
     JOIN ( SELECT v_economics_summary_eur.sales_date,
            v_economics_summary_eur.marketplace,
            sum(v_economics_summary_eur.ordered_product_sales) AS ex_vat
           FROM kabinet_data.v_economics_summary_eur
          WHERE ((v_economics_summary_eur.marketplace)::text = ANY ((ARRAY['LM'::character varying, 'MM_ES'::character varying, 'MM_FR'::character varying, 'MMB_ES'::character varying, 'CF_ES'::character varying])::text[]))
          GROUP BY v_economics_summary_eur.sales_date, v_economics_summary_eur.marketplace) t ON (((t.sales_date = e.sales_date) AND ((t.marketplace)::text = (e.marketplace)::text))))
     JOIN kabinet_data.v_sales_vat_incl_daily v ON (((v.date = e.sales_date) AND (v.marketplace = (e.marketplace)::text))))
  WHERE ((e.marketplace)::text = ANY ((ARRAY['LM'::character varying, 'MM_ES'::character varying, 'MM_FR'::character varying, 'MMB_ES'::character varying, 'CF_ES'::character varying])::text[]))
  GROUP BY e.sales_date, e.marketplace, e.norm_sku;

-- v_marketplace_data_status: заказы ManoMano с country = 'ES_B2B' относятся к MMB-ES; статус 'trial' — пробный
-- период без единого заказа (сторож его не тревожит); колонка trial_until — в конце, чтобы читатели не сломались
CREATE OR REPLACE VIEW kabinet_data.v_marketplace_data_status AS
 WITH src AS (
         SELECT 'AMZ'::text AS platform,
            orders_history.marketplace_code AS country,
            'orders'::text AS source,
            max(orders_history.purchase_date) AS last_at
           FROM kabinet_data.orders_history
          GROUP BY orders_history.marketplace_code
        UNION ALL
         SELECT 'AMZ'::text,
            sales_traffic_daily.marketplace,
            'sales_traffic'::text,
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
            'ads'::text,
            max(ads_market_daily.updated_at) AS max
           FROM kabinet_data.ads_market_daily
          GROUP BY ads_market_daily.marketplace
        UNION ALL
         SELECT split_part(raw_mm_offers.marketplace_code, '-'::text, 1) AS split_part,
            split_part(raw_mm_offers.marketplace_code, '-'::text, 2) AS split_part,
            'offers'::text,
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
            'orders'::text,
            max(raw_mm_order_lines.loaded_at) AS max
           FROM kabinet_data.raw_mm_order_lines
          GROUP BY raw_mm_order_lines.country
        UNION ALL
         SELECT 'CF'::text,
            raw_cf_order_lines.country,
            'orders'::text,
            max(raw_cf_order_lines.loaded_at) AS max
           FROM kabinet_data.raw_cf_order_lines
          GROUP BY raw_cf_order_lines.country
        UNION ALL
         SELECT 'CF'::text,
            NULL::text,
            'offers'::text,
            max(raw_cf_offers.loaded_at) AS max
           FROM kabinet_data.raw_cf_offers
        UNION ALL
         SELECT 'LM'::text,
            raw_lm_orders.customer_country,
            'orders'::text,
            max(raw_lm_orders.loaded_at) AS max
           FROM kabinet_data.raw_lm_orders
          GROUP BY raw_lm_orders.customer_country
        UNION ALL
         SELECT 'LM'::text,
            NULL::text,
            'offers'::text,
            max(raw_lm_offers.loaded_at) AS max
           FROM kabinet_data.raw_lm_offers
        UNION ALL
         SELECT p_1.short_name,
            NULLIF((s.warehouse_country)::text, ''::text) AS "nullif",
            'stock'::text,
            max(s.created_at) AS max
           FROM (kabinet_data.stock_local s
             JOIN kabinet_data.platforms p_1 ON ((p_1.full_name = s.channel)))
          WHERE (s.source <> 'ledger-summary'::text)
          GROUP BY p_1.short_name, NULLIF((s.warehouse_country)::text, ''::text)
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
