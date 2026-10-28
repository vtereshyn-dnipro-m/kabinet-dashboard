-- Worten Marketplace (Mirakl): схема и таблицы сырья в Unity Catalog (28.10.2026; docs/worten.md). Применяет
-- владелец или агент по прямому «применяй», под учёткой владельца, на SQL-складе, подставив Application ID
-- kabinet-jobs-sp вместо `<sp>` (в репозиторий его не кладём, как у TikTok). Только добавляет. Lakebase — в
-- sql/worten_2026-10-28.sql; этот файл — первым.

CREATE SCHEMA IF NOT EXISTS dnipro_m.worten
COMMENT 'Worten Marketplace (Mirakl): ответ API как есть, без данных покупателей. Пишет Kabinet - Worten Loader.';

CREATE TABLE IF NOT EXISTS dnipro_m.worten.raw_offers (
  shop_id STRING NOT NULL, offer_id STRING NOT NULL, shop_sku STRING, product_sku STRING, product_title STRING,
  category_code STRING, active BOOLEAN, state_code STRING, quantity INT, channel_code STRING,
  price DECIMAL(18,2) COMMENT 'цена для покупателя на момент снимка: цена канала WRT_PT_ONLINE, скидка — только действующая',
  origin_price DECIMAL(18,2), discount_price DECIMAL(18,2), discount_start TIMESTAMP, discount_end TIMESTAMP,
  promo_active BOOLEAN, base_price DECIMAL(18,2) COMMENT 'верхнее поле price — цена без канала, покупатель её не видит',
  currency STRING, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'Worten: офферы магазина (GET /api/offers, OF21). Ключ shop_id + offer_id; пропавшие из ответа — со старым loaded_at.';

CREATE TABLE IF NOT EXISTS dnipro_m.worten.raw_orders (
  shop_id STRING NOT NULL, order_id STRING NOT NULL, commercial_id STRING, order_state STRING, channel_code STRING,
  created_at TIMESTAMP, updated_at TIMESTAMP, currency STRING, price DECIMAL(18,2), shipping_price DECIMAL(18,2),
  total_price DECIMAL(18,2), total_commission DECIMAL(18,2), order_tax_mode STRING, fully_refunded BOOLEAN,
  has_incident BOOLEAN, postal_code STRING, country STRING, lines_count INT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'Worten: заказы (GET /api/orders, OR11), без данных покупателя — из адреса индекс и страна. Ключ shop_id + order_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.worten.raw_order_lines (
  shop_id STRING NOT NULL, order_id STRING NOT NULL, order_line_id STRING NOT NULL, order_line_state STRING,
  offer_id STRING, shop_sku STRING, product_title STRING, quantity INT, price_unit DECIMAL(18,2), price DECIMAL(18,2),
  shipping_price DECIMAL(18,2), total_price DECIMAL(18,2), commission_fee DECIMAL(18,2), commission_vat DECIMAL(18,2),
  tax_amount DECIMAL(18,2), shipped_at TIMESTAMP, received_at TIMESTAMP, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'Worten: строки заказов. Ключ shop_id + order_line_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.worten.sync_state (
  shop_id STRING NOT NULL, stream STRING NOT NULL, done_until TIMESTAMP, updated_at TIMESTAMP)
COMMENT 'Worten: отметка продолжения — конец последнего целиком записанного куска. Ключ shop_id + stream.';

-- USE CATALOG на dnipro_m у принципала — из sql/kabinet_jobs_sp_2026-10-22.sql. Таблицы заводит владелец здесь же,
-- поэтому CREATE TABLE принципалу не нужен (у TikTok он был — таблицы заводил загрузчик).
GRANT USE SCHEMA, MODIFY, SELECT ON SCHEMA dnipro_m.worten TO `<sp>`;
