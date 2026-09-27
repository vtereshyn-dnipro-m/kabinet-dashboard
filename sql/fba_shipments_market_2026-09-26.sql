-- Разбор первого прогона `Kabinet - FBA Shipments Loader` (26.09.2026) и правка по его итогам.
--
-- Отчёт GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL отдаётся ПО ВСЕМУ АККАУНТУ, а не по рынку:
-- десять запросов вернули один и тот же набор из 246 позиций — 246 строк в таблице при десяти
-- отчётах, то есть `shipment-item-id` у всех рынков совпали до единого. Колонка `marketplace`
-- при этом хранила тот рынок, у которого спросили последним (SE), хотя по `orders_history` это
-- отгрузки IT 115 шт, ES 75, FR 32, DE 27, BE 7, GB 6.
--
-- Поэтому рынок берём из самого отчёта (колонка `sales-channel`), а не из того, кого спросили, и
-- запрос делаем один вместо десяти. Девять лишних createReport в день — это чужая квота аккаунта.
ALTER TABLE kabinet_data.raw_amazon_fulfilled_shipments ADD COLUMN IF NOT EXISTS sales_channel text;

COMMENT ON COLUMN kabinet_data.raw_amazon_fulfilled_shipments.sales_channel IS
    'Витрина заказа из отчёта, например «Amazon.it». Из неё выводится marketplace: рынок, у которого спросили отчёт, рынком отгрузки не является.';

COMMENT ON COLUMN kabinet_data.raw_amazon_fulfilled_shipments.marketplace IS
    'Код страны рынка из sales_channel. Пусто в отчёте — берём из orders_history по номеру заказа, не нашлось и там — NULL, а не догадка.';

-- `asin` отчёт не отдаёт вовсе: в 246 строках он пуст у всех. Колонка, всегда пустая, читается как
-- «данных нет по этим товарам», а не «поля нет в источнике» — убираем, чтобы не обманывала.
ALTER TABLE kabinet_data.raw_amazon_fulfilled_shipments DROP COLUMN IF EXISTS asin;

SELECT count(*) AS строк, count(DISTINCT report_id) AS отчётов, count(sales_channel) AS с_витриной,
       min(shipment_date) AS с, max(shipment_date) AS по
FROM kabinet_data.raw_amazon_fulfilled_shipments;
