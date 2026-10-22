-- TikTok Shop, аналитика (группа 1, 22.10.2026): таблицы сырья и настройка загрузчика `Kabinet - TikTok Shop Analytics
-- Loader` (docs/tiktok-shop.md). Применяет владелец под своей учёткой после мержа: часть A — SQL-склад (Spark SQL),
-- часть B — Lakebase Кабинета. Только добавляет: ничего не удаляет и ни у кого не отнимает.
--
-- Дата `date` — день в часовом поясе магазина (так API считает аналитику). Деньги — DECIMAL(18,2) в валюте `currency`.
-- Креаторы — creator_id и публичный ник (`creator_user_name`); отображаемое имя и open_id не пишутся.
-- Доступ к схеме dnipro_m.tiktok — как решено 22.10.2026: вариант а) (наследуется от каталога), в) — по плану #364.

-- ── Часть A. Таблицы (SQL-склад) ──
CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_shop_daily (
  shop_id STRING NOT NULL, region STRING, date DATE NOT NULL, currency STRING,
  gmv DECIMAL(18,2), gmv_with_tax DECIMAL(18,2), gmv_with_tiktok_co_funding DECIMAL(18,2), tax DECIMAL(18,2),
  shipping_fees DECIMAL(18,2), refunds DECIMAL(18,2), orders_count INT, sku_orders_count INT, items_sold INT,
  customers_count INT, cancellations_and_returns INT, video_gmv DECIMAL(18,2), live_gmv DECIMAL(18,2),
  creator_video_gmv DECIMAL(18,2), seller_video_gmv DECIMAL(18,2), product_card_attributed_gmv DECIMAL(18,2),
  avg_page_views DECIMAL(18,4), avg_visitors DECIMAL(18,4), product_impressions BIGINT, product_clicks BIGINT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: аналитика магазина по дням (GET /analytics/202609/shop/performance, 1D). Ключ shop_id + date.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_product_daily (
  shop_id STRING NOT NULL, region STRING, date DATE NOT NULL, product_id STRING NOT NULL, currency STRING,
  gmv DECIMAL(18,2), gmv_incl_tax DECIMAL(18,2), orders INT, sku_orders INT, items_sold INT,
  product_impressions BIGINT, product_clicks BIGINT, add_cart_count INT, refunds DECIMAL(18,2), refunded_items INT,
  affiliate_gmv DECIMAL(18,2), seller_card_gmv DECIMAL(18,2), shop_tab_gmv DECIMAL(18,2), raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: аналитика товаров по дням (GET /analytics/202605/shop_products/performance). Ключ shop_id + date + product_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_sku_daily (
  shop_id STRING NOT NULL, region STRING, date DATE NOT NULL, sku_id STRING NOT NULL, product_id STRING, currency STRING,
  gmv DECIMAL(18,2), sku_orders INT, units_sold INT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: аналитика SKU по дням (GET /analytics/202509/shop_skus/performance). Ключ shop_id + date + sku_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_video_daily (
  shop_id STRING NOT NULL, region STRING, date DATE NOT NULL, video_id STRING NOT NULL, creator_id STRING,
  creator_user_name STRING, author_type STRING, title STRING, video_post_time_local STRING, duration_s INT, currency STRING,
  gmv DECIMAL(18,2), attributed_gmv DECIMAL(18,2), indirect_gmv DECIMAL(18,2), items_sold INT, sku_orders INT,
  views BIGINT, likes BIGINT, comments BIGINT, shares BIGINT, new_followers BIGINT, product_impressions BIGINT,
  product_clicks BIGINT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: видео по дням (GET /analytics/202605/shop_videos/performance). Ключ shop_id + date + video_id; креатор — id и публичный ник.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_video_product_daily (
  shop_id STRING NOT NULL, region STRING, date DATE NOT NULL, video_id STRING NOT NULL, product_id STRING NOT NULL,
  currency STRING, gmv DECIMAL(18,2), units_sold INT, customers INT, product_impressions BIGINT, product_clicks BIGINT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: товары видео по дням, только дни с продажами видео (GET /analytics/202509/shop_videos/{id}/products/performance).';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_lives (
  shop_id STRING NOT NULL, region STRING, live_id STRING NOT NULL, account_type STRING, creator_id STRING,
  creator_user_name STRING, author_type STRING, title STRING, start_time_local STRING, end_time_local STRING,
  currency STRING, live_gmv DECIMAL(18,2), live_attributed_gmv DECIMAL(18,2), live_attributed_items_sold INT,
  products_sold INT, viewers BIGINT, views BIGINT, avg_viewing_duration_s INT, product_impressions BIGINT,
  product_clicks BIGINT, likes BIGINT, comments BIGINT, shares BIGINT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: эфиры — итоги сессии (GET /analytics/202609/shop_lives/performance, три типа аккаунтов). Ключ shop_id + live_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_analytics_live_products (
  shop_id STRING NOT NULL, region STRING, live_id STRING NOT NULL, product_id STRING NOT NULL, currency STRING,
  gmv DECIMAL(18,2), units_sold INT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: товары эфиров с продажами (GET /analytics/202512/shop/{live_id}/products_performance). Ключ shop_id + live_id + product_id.';

-- ── Часть B. Настройка (Lakebase Кабинета) ──
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('tiktok_analytics_overlap_days', 7, 'TikTok Shop аналитика: перечитываем последние дни (сутки) — атрибуция GMV видео и эфиров дописывается задним числом', now())
ON CONFLICT (key) DO NOTHING;
