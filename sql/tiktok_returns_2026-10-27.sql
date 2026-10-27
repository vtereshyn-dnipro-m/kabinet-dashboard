-- TikTok Shop, возвраты и отмены (шаг 2, 27.10.2026, решение владельца: POST-поиск возвратов и отмен, только чтение):
-- две таблицы сырья для шага `Kabinet - TikTok Shop Loader` (docs/tiktok-shop.md). Применяет владелец — сам или агентом
-- по прямому «применяй», только под учёткой владельца. Только добавляет: ничего не удаляет и ни у кого не отнимает.
--
-- Права: kabinet-jobs-sp уже имеет на схему dnipro_m.tiktok USE SCHEMA, CREATE TABLE, MODIFY, SELECT (26.10.2026) —
-- новые таблицы схемы их наследуют, отдельных GRANT не нужно. В Lakebase ничего нового: реплики для страниц пока нет,
-- пульс — тот же `Kabinet - TikTok Shop Loader`, правило сторожа у него уже есть.
-- Строка — позиция возврата или отмены; поля самого возврата повторяются в каждой позиции. Позиция без id — заглушка
-- '#номер', возврат без позиций — одна строка '#0' (строки '#…' возврата берутся, только если настоящих позиций нет). Адреса склада возврата, трек-номера, перевозчика, доли покупателя за обратную
-- доставку и ссылок на картинки нет ни в колонках, ни в raw_json (nb/tiktok_rows.py). Данных покупателей в ответах нет.

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_returns (
  shop_id STRING NOT NULL, region STRING, return_id STRING NOT NULL, return_line_item_id STRING NOT NULL,
  order_id STRING, order_line_item_id STRING, sku_id STRING, seller_sku STRING, product_name STRING, sku_name STRING,
  return_type STRING, return_status STRING, return_reason STRING, return_reason_text STRING, return_method STRING,
  role STRING, create_time TIMESTAMP, update_time TIMESTAMP, currency STRING,
  refund_total DECIMAL(18,2) COMMENT 'возмещение по позиции',
  refund_subtotal DECIMAL(18,2) COMMENT 'возмещение по позиции без доставки и налога',
  return_refund_total DECIMAL(18,2) COMMENT 'возмещение по возврату целиком (повторяется в каждой позиции)',
  return_refund_shipping_fee DECIMAL(18,2) COMMENT 'возмещённая доставка по возврату целиком',
  product_seller_discount DECIMAL(18,2), product_platform_discount DECIMAL(18,2),
  seller_paid_return_shipping_fee DECIMAL(18,2) COMMENT 'обратная доставка за счёт продавца',
  platform_paid_return_shipping_fee DECIMAL(18,2) COMMENT 'обратная доставка за счёт платформы',
  lines_count INT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: возвраты по позициям (POST /return_refund/202309/returns/search). Ключ shop_id + return_id + return_line_item_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_cancellations (
  shop_id STRING NOT NULL, region STRING, cancel_id STRING NOT NULL, cancel_line_item_id STRING NOT NULL,
  order_id STRING, order_line_item_id STRING, sku_id STRING, seller_sku STRING, product_name STRING, sku_name STRING,
  cancel_type STRING, cancel_status STRING, cancel_reason STRING, cancel_reason_text STRING, role STRING,
  should_replenish_stock BOOLEAN, create_time TIMESTAMP, update_time TIMESTAMP, currency STRING,
  refund_total DECIMAL(18,2) COMMENT 'возмещение по позиции',
  cancel_refund_total DECIMAL(18,2) COMMENT 'возмещение по отмене целиком (повторяется в каждой позиции)',
  lines_count INT, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: отмены по позициям (POST /return_refund/202309/cancellations/search). Ключ shop_id + cancel_id + cancel_line_item_id.';
