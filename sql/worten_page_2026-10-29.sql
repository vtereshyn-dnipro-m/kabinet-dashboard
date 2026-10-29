-- Worten в Кабинете: справочники, вью продаж для «Обзора», флаг строки, статус данных маркетплейса (29.10.2026, PR3
-- из трёх; решение владельца: Worten — новый источник по API, как TikTok Shop, а не реплика Power BI; Power BI Кабинет
-- не ждёт; docs/worten.md). Применяет владелец или агент по прямому «применяй», ПОД УЧЁТКОЙ ВЛАДЕЛЬЦА (не через
-- claude_code_ro — правило AGENTS.md), в Lakebase Кабинета, одной транзакцией:
--   psql "<строка владельца>" -v ON_ERROR_STOP=1 -1 -f sql/worten_page_2026-10-29.sql
-- Таблицы platforms и marketplaces_new — владельца; v_marketplace_data_status принадлежит роли claude_code_ro, учётка
-- владельца в неё входит, поэтому заменить вью может. Только добавляет: ничего не удаляет, ни у кого не отнимает;
-- права на вью при CREATE OR REPLACE сохраняются.
--
-- Порядок: SQL — ПЕРЕД выкладкой (мержем) кода. Код без SQL безопасен: вью нет — строки Worten на «Обзоре» нет, вкладка
-- «Площадок» читает реплики, которые уже есть. SQL без кода тоже безопасен: флаг 0, страниц, читающих вью, ещё нет.
-- Plan Matrix в эти справочники не смотрит: вкладки таблицы — список TABS в nb/plan_matrix_prices.py, Worten там нет,
-- и в табы аналитика витрины ничего не пишется.

-- ── 1. Справочники ──
-- Площадка: короткое имя WRT (как у Mirakl-кодов LM, CF), полное — Worten. Маркетплейс WRT-PT: Португалия, евро, НДС 23 %
-- (стандартная ставка; пониженные на наших категориях не проверены — docs/worten.md, «Деньги»). legacy_code wrt_pt — как
-- tts_es у TikTok; sync_* и monitor_listings — false (это флаги загрузчиков Amazon).
INSERT INTO kabinet_data.platforms (short_name, full_name) VALUES ('WRT', 'Worten')
ON CONFLICT (short_name) DO NOTHING;

INSERT INTO kabinet_data.platform_attributes (platform_id, is_active, comment, updated_by)
SELECT id, true, 'Worten (Mirakl), Португалия: данные — Worten API, не Power BI', 'migration:worten_page'
  FROM kabinet_data.platforms WHERE short_name = 'WRT'
ON CONFLICT (platform_id) DO NOTHING;

INSERT INTO kabinet_data.marketplaces_new (code, platform_short, country_alpha2, name, currency, vat_rate, is_active,
                                           legacy_code)
VALUES ('WRT-PT', 'WRT', 'PT', 'Worten Portugal', 'EUR', 0.23, true, 'wrt_pt')
ON CONFLICT (code) DO NOTHING;

-- ── 2. Статус данных маркетплейса — с источниками Worten ──
-- Без них WRT-PT сразу получил бы статус no_data (источников по платформе WRT в вью нет), и сторож завёл бы тревогу
-- marketplace_no_data. Определение — живое на 29.10.2026 (pg_get_viewdef) плюс две ветки: офферы (свежесть — каждый
-- прогон загрузчика) и заказы по стране. Колонки и их порядок прежние.
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

-- ── 3. Продажи Worten по дням для «Обзора» ──
-- Как у Leroy Merlin в v_sales_vat_incl_daily: сумма строк заказа (цена без доставки), без строк REFUNDED, CANCELED,
-- REFUSED. День заказа — по Лиссабону: created_at в реплике — часы Лиссабона, записанные как UTC (решение владельца
-- 28.10.2026), поэтому дата берётся явно AT TIME ZONE 'UTC', а не от пояса сессии. Без НДС — делением на ставку
-- маркетплейса, как у TikTok.
CREATE OR REPLACE VIEW kabinet_data.v_worten_sales_daily AS
SELECT (o.created_at AT TIME ZONE 'UTC')::date AS date,
       m.code AS marketplace,
       p.full_name AS channel,
       c.name AS country,
       count(DISTINCT o.order_id) AS orders,
       sum(l.price)::double precision AS sales_vat_incl,
       (sum(l.price) / (1 + m.vat_rate))::double precision AS sales_vat_excl
  FROM kabinet_data.raw_worten_order_lines l
  JOIN kabinet_data.raw_worten_orders o ON o.shop_id = l.shop_id AND o.order_id = l.order_id
  JOIN kabinet_data.marketplaces_new m ON m.code = 'WRT-PT'
  JOIN kabinet_data.platforms p ON p.short_name = m.platform_short
  JOIN kabinet_data.countries c ON c.alpha2 = m.country_alpha2
 WHERE upper(coalesce(l.order_line_state, '')) <> ALL (ARRAY['REFUNDED', 'CANCELED', 'REFUSED'])
 GROUP BY 1, m.code, p.full_name, c.name, m.vat_rate;
COMMENT ON VIEW kabinet_data.v_worten_sales_daily IS
  'Worten по дням для «Обзора»: Worten API (Mirakl), не Power BI. Строки заказов без отмен, отказов, возвратов; день — по Лиссабону.';

GRANT SELECT ON kabinet_data.v_worten_sales_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;

-- ── 4. Флаг строки Worten на «Обзоре» ──
-- 0 до сверки заказов с кабинетом Worten (как tiktok_overview_enabled); включает владелец. Администратор видит строку и
-- при 0. Вкладка «Площадок» — без флага (ответ владельца на аудит 28.10.2026).
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('worten_overview_enabled', 0, 'Worten в «Обзоре» (каналы и страны): 1 — показывать всем, 0 — только администратору. Включает владелец после сверки заказов с кабинетом Worten', now())
ON CONFLICT (key) DO NOTHING;

-- Проверка чтением (после применения):
-- SELECT code, status, last_source FROM kabinet_data.v_marketplace_data_status WHERE code IN ('WRT-PT', 'TTS-ES', 'LM-ES');
--   WRT-PT — ok; у остальных — как до применения
-- SELECT * FROM kabinet_data.v_worten_sales_daily ORDER BY date DESC LIMIT 5;   -- 21.10.2026 · WRT-PT · 65,99 с НДС
-- SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'worten_overview_enabled';   -- 0
