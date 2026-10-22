-- TikTok Shop в Кабинете: реплики в Lakebase для страницы «TikTok Shop», вью продаж для «Обзора», флаг показа в
-- «Обзоре», право page.tiktok (22.10.2026, решение владельца; docs/tiktok-shop.md). Применяет ВЛАДЕЛЕЦ под своей
-- учёткой (не через claude_code_ro — правило AGENTS.md), в Lakebase Кабинета. Только добавляет: ничего не удаляет.
--
-- Страницы Кабинета читают только Lakebase, сырьё TikTok — в Unity Catalog (dnipro_m.tiktok). Реплику пишет
-- `Kabinet - TikTok Shop Loader` после загрузки сырья (upsert по ключу), только нужные странице колонки, без raw_json
-- и без персональных данных (buyer_hash — псевдоним; по GDPR тоже персональные данные — в реплике он нужен для
-- повторных покупок).
-- Гранты: приложению — SELECT; claude_code_ro — SELECT (проверки страниц, сводка); kabinet-jobs-sp — запись, когда
-- принципал будет (#364), строки ниже закомментированы. claude-uc-ro для TikTok не используется (решение владельца
-- 22.10.2026) — отступление от правила «гранты обоим принципалам» названо здесь.
-- Деньги — как у TikTok: с НДС, в валюте магазина. Исключение «не Power BI» для TikTok подтверждено владельцем.

-- ── Реплики ──
CREATE TABLE IF NOT EXISTS kabinet_data.raw_tiktok_orders (
  shop_id text NOT NULL, order_id text NOT NULL, region text, status text, create_time timestamptz, update_time timestamptz,
  is_sample_order boolean, currency text, original_total_product_price numeric(18,2), seller_discount numeric(18,2),
  platform_discount numeric(18,2), sub_total numeric(18,2), total_amount numeric(18,2), buyer_hash text,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, order_id));
COMMENT ON TABLE kabinet_data.raw_tiktok_orders IS 'Реплика dnipro_m.tiktok.raw_orders для страниц (пишет Kabinet - TikTok Shop Loader). Без персональных данных; buyer_hash — псевдоним.';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_tiktok_order_lines (
  shop_id text NOT NULL, line_item_id text NOT NULL, order_id text NOT NULL, sku_id text, seller_sku text, product_name text,
  currency text, original_price numeric(18,2), sale_price numeric(18,2), seller_discount numeric(18,2),
  platform_discount numeric(18,2), display_status text, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, line_item_id));
COMMENT ON TABLE kabinet_data.raw_tiktok_order_lines IS 'Реплика dnipro_m.tiktok.raw_order_lines для страниц (строка заказа = одна штука).';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_tiktok_finance_tx (
  shop_id text NOT NULL, statement_id text NOT NULL, transaction_id text NOT NULL, order_id text, type text,
  statement_time timestamptz, payment_status text, currency text, revenue_amount numeric(18,2),
  fee_tax_amount numeric(18,2), shipping_cost_amount numeric(18,2), adjustment_amount numeric(18,2),
  settlement_amount numeric(18,2), loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, statement_id, transaction_id));
COMMENT ON TABLE kabinet_data.raw_tiktok_finance_tx IS 'Реплика операций выписок TikTok (dnipro_m.tiktok.raw_finance_statement_transactions + статус выплаты выписки).';

-- ── Продажи TikTok по дням для «Обзора» ──
-- Выручка продавца = sub_total + platform_discount (= цена до скидок минус скидка продавца; скидку платформы платит
-- TikTok), без отмен и образцов, по дате создания заказа по Мадриду, до возвратов. Без НДС — делением на ставку из
-- marketplaces_new (TTS-ES, 0,21), а не константой.
CREATE OR REPLACE VIEW kabinet_data.v_tiktok_sales_daily AS
SELECT (o.create_time AT TIME ZONE 'Europe/Madrid')::date AS date,
       m.code AS marketplace, 'TikTok Shop'::text AS channel, 'Spain'::text AS country,
       count(*) AS orders,
       sum(o.sub_total + coalesce(o.platform_discount, 0))::double precision AS sales_vat_incl,
       (sum(o.sub_total + coalesce(o.platform_discount, 0)) / (1 + m.vat_rate))::double precision AS sales_vat_excl
FROM kabinet_data.raw_tiktok_orders o
JOIN kabinet_data.marketplaces_new m ON m.code = 'TTS-' || o.region
WHERE o.status <> 'CANCELLED' AND NOT coalesce(o.is_sample_order, false)
GROUP BY 1, 2, m.vat_rate;
COMMENT ON VIEW kabinet_data.v_tiktok_sales_daily IS 'TikTok Shop: выручка продавца по дням (Мадрид), с НДС и без — для «Обзора». Источник — TikTok Shop API, не Power BI.';

-- ── Флаг показа в «Обзоре» (до сверки заказов с Seller Center — выключен, решение владельца 22.10.2026) ──
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('tiktok_overview_enabled', 0, 'TikTok Shop в «Обзоре» (каналы и страны): 1 — показывать, 0 — нет. Включает владелец после сверки заказов с Seller Center', now())
ON CONFLICT (key) DO NOTHING;

-- ── Право page.tiktok: до сверки — только администратор (решение владельца 22.10.2026); country_manager — потом,
-- галочкой на экране «Доступ» ──
INSERT INTO kabinet_data.app_permissions (action, role, allowed, updated_by)
SELECT 'page.tiktok', r.role, r.role = 'admin', 'sql:tiktok_page_2026-10-22'
  FROM (VALUES ('viewer'), ('country_manager'), ('demand_planner'), ('admin')) AS r(role)
ON CONFLICT (action, role) DO NOTHING;

-- ── Гранты ──
GRANT SELECT ON kabinet_data.raw_tiktok_orders, kabinet_data.raw_tiktok_order_lines, kabinet_data.raw_tiktok_finance_tx,
  kabinet_data.v_tiktok_sales_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;
-- kabinet-jobs-sp (после #364): GRANT SELECT, INSERT, UPDATE ON kabinet_data.raw_tiktok_orders,
--   kabinet_data.raw_tiktok_order_lines, kabinet_data.raw_tiktok_finance_tx TO "<sp>";

-- Проверка: SELECT * FROM kabinet_data.v_tiktok_sales_daily ORDER BY date DESC LIMIT 5;
