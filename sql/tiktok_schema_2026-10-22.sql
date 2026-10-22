-- TikTok Shop: сырьё в Unity Catalog и настройки загрузчика (22.10.2026, решение владельца: «TikTok Shop — подключаем,
-- только чтение»; docs/tiktok-shop.md). Применяет ВЛАДЕЛЕЦ после мержа. Ничего не удаляет и ни у кого не отнимает.
--
-- Часть A — SQL-склад (Spark SQL), под владельцем: схема и таблицы. Владелец схемы — тот, кто её создал (владелец
--   Кабинета); `account users` получает доступ к ней через права на каталог, как к остальным схемам dnipro_m.
-- Часть B — SQL-склад, гранты kabinet-jobs-sp. `<sp>` — Application ID, подставить руками (в Spark SQL нет переменных).
--   Пока #364 не смержен и принципала нет — часть B пропустить: загрузчик без расписания, прогоны владелец запускает
--   руками под своей учёткой.
-- Часть C — Lakebase Кабинета, под владельцем: настройки загрузчика в reorder_params (пороги живут в БД).
--
-- Персональные данные покупателя (имя, адрес, телефон, email, ник, налоговый номер, переписка, user_id) в эти таблицы
-- не пишутся — загрузчик срезает их до записи (nb/tiktok_rows.py). Из адреса остаются индекс и код региона; вместо
-- user_id — buyer_hash = sha256(соль + user_id), соль — секрет tiktok-shop/buyer-salt (задаёт владелец, не меняется).
-- Деньги — DECIMAL(18,2) в валюте магазина (`currency`), время — TIMESTAMP по UTC.

-- ── Часть A. Схема и таблицы (SQL-склад) ──
CREATE SCHEMA IF NOT EXISTS dnipro_m.tiktok
  COMMENT 'TikTok Shop — сырьё API (только чтение, Kabinet - TikTok Shop Loader). Без персональных данных покупателей.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_orders (
  shop_id STRING NOT NULL, region STRING, order_id STRING NOT NULL, status STRING,
  create_time TIMESTAMP, update_time TIMESTAMP, paid_time TIMESTAMP, cancel_time TIMESTAMP, delivery_time TIMESTAMP,
  currency STRING, total_amount DECIMAL(18,2), sub_total DECIMAL(18,2), original_total_product_price DECIMAL(18,2),
  shipping_fee DECIMAL(18,2), seller_discount DECIMAL(18,2), platform_discount DECIMAL(18,2), tax DECIMAL(18,2),
  fulfillment_type STRING, delivery_type STRING, payment_method_name STRING, cancel_reason STRING,
  cancellation_initiator STRING, is_sample_order BOOLEAN, postal_code STRING,
  buyer_hash STRING COMMENT 'sha256(соль + user_id) — покупатель для повторных покупок без user_id в открытом виде',
  line_items_count INT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: заказы (POST /order/202309/orders/search). Ключ shop_id + order_id; без персональных данных.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_order_lines (
  shop_id STRING NOT NULL, region STRING, order_id STRING NOT NULL, line_item_id STRING NOT NULL,
  sku_id STRING, seller_sku STRING, product_id STRING, product_name STRING, sku_name STRING, currency STRING,
  original_price DECIMAL(18,2), sale_price DECIMAL(18,2), seller_discount DECIMAL(18,2), platform_discount DECIMAL(18,2),
  item_tax STRING, display_status STRING, cancel_reason STRING, is_gift BOOLEAN, package_id STRING,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: строки заказов (line_items; у TikTok строка — одна штука). Ключ shop_id + line_item_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_products (
  shop_id STRING NOT NULL, region STRING, product_id STRING NOT NULL, title STRING, status STRING,
  create_time TIMESTAMP, update_time TIMESTAMP, listing_quality_tier STRING, skus_count INT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: товары (POST /product/202502/products/search), снимок раз в сутки. Ключ shop_id + product_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_product_skus (
  shop_id STRING NOT NULL, region STRING, product_id STRING NOT NULL, sku_id STRING NOT NULL, seller_sku STRING,
  currency STRING, sale_price DECIMAL(18,2), tax_exclusive_price DECIMAL(18,2), inventory_quantity INT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: SKU товаров — seller_sku, цена, остаток по складам суммой. Ключ shop_id + sku_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_finance_statements (
  shop_id STRING NOT NULL, region STRING, statement_id STRING NOT NULL, statement_time TIMESTAMP,
  payment_status STRING, payment_id STRING, payment_time TIMESTAMP, currency STRING,
  revenue_amount DECIMAL(18,2), fee_amount DECIMAL(18,2), adjustment_amount DECIMAL(18,2),
  shipping_cost_amount DECIMAL(18,2), net_sales_amount DECIMAL(18,2), settlement_amount DECIMAL(18,2),
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: выписки (GET /finance/202309/statements). Ключ shop_id + statement_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_finance_statement_transactions (
  shop_id STRING NOT NULL, region STRING, statement_id STRING NOT NULL, transaction_id STRING NOT NULL,
  type STRING, order_id STRING, order_create_time TIMESTAMP, adjustment_id STRING, currency STRING,
  revenue_amount DECIMAL(18,2), shipping_cost_amount DECIMAL(18,2), fee_tax_amount DECIMAL(18,2),
  adjustment_amount DECIMAL(18,2), settlement_amount DECIMAL(18,2), raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: операции выписок (GET /finance/202501/statements/{id}/statement_transactions). Ключ shop_id + statement_id + transaction_id.';

-- ── Часть B. Гранты kabinet-jobs-sp (SQL-склад; только когда принципал создан, #364) ──
-- Решение владельца 22.10.2026: USE SCHEMA, CREATE TABLE, MODIFY, SELECT — только на dnipro_m.tiktok. USE CATALOG на
-- dnipro_m у принципала — из sql/kabinet_jobs_sp_2026-10-22.sql, часть B. claude-uc-ro для TikTok не используется.
-- GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT ON SCHEMA dnipro_m.tiktok TO `<sp>`;

-- ── Часть C. Настройки загрузчика (Lakebase Кабинета) ──
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('tiktok_history_days', 90, 'TikTok Shop: глубина первого запуска (сутки) — заказы и выписки; дальше инкремент', now()),
 ('tiktok_order_overlap_days', 3, 'TikTok Shop: инкремент заказов — перечитываем по update_time с перекрытием (сутки): статусы и отмены меняются задним числом', now()),
 ('tiktok_finance_overlap_days', 14, 'TikTok Shop: инкремент выписок — перечитываем по statement_time с перекрытием (сутки): payment_status меняется после выписки', now()),
 ('tiktok_window_days', 7, 'TikTok Shop: длина куска запроса заказов и выписок (сутки) — длинный период режется на куски', now())
ON CONFLICT (key) DO NOTHING;
