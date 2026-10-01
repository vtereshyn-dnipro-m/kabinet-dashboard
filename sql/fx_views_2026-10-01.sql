-- Витрины с деньгами в евро. Читатели меняют ИМЯ таблицы, а не свои запросы.
--
-- Правка «по месту» означала бы два десятка запросов в пяти файлах, и один из них
-- забыли бы — а забытый выглядел бы правильным: число есть, просто не то. Вью меняет
-- одно слово в каждом запросе и не оставляет места ошибке.
--
-- ЧТО ПЕРЕСЧИТЫВАЕТСЯ, А ЧТО НЕТ. Выручка, комиссии и поступления лежат в валюте
-- рынка — их пересчитываем. А `cogs` — себестоимость компании, и она в евро ВЕЗДЕ:
-- проверено на одном и том же SKU 41324000, где она равна 11,62 и на DE (EUR), и на GB
-- (GBP). Пересчитать её значило бы занизить себестоимость британских строк на 15 % и
-- завысить маржу — ошибка того же рода, только наоборот.

CREATE OR REPLACE VIEW kabinet_data.v_economics_summary_eur AS
SELECT e.sales_date, e.marketplace, e.norm_sku, e.product_name,
       e.units_ordered, e.units_refunded, e.net_units_sold,
       kabinet_data.to_eur(e.ordered_product_sales, e.currency_code, e.sales_date) AS ordered_product_sales,
       kabinet_data.to_eur(e.net_product_sales,     e.currency_code, e.sales_date) AS net_product_sales,
       kabinet_data.to_eur(e.total_fees,            e.currency_code, e.sales_date) AS total_fees,
       kabinet_data.to_eur(e.net_proceeds_total,    e.currency_code, e.sales_date) AS net_proceeds_total,
       kabinet_data.to_eur(e.net_proceeds_per_unit, e.currency_code, e.sales_date) AS net_proceeds_per_unit,
       kabinet_data.to_eur(e.commission_fee,        e.currency_code, e.sales_date) AS commission_fee,
       -- себестоимость НЕ трогаем: она уже в евро на всех рынках
       e.cogs, e.cogs_source,
       'EUR'::text AS currency_code,
       e.currency_code AS source_currency,
       e.updated_at
  FROM kabinet_data.economics_summary e;

COMMENT ON VIEW kabinet_data.v_economics_summary_eur IS
    'economics_summary с деньгами в евро по курсу ЕЦБ на дату продажи. cogs не пересчитывается: она в евро на всех рынках.';

CREATE OR REPLACE VIEW kabinet_data.v_sales_traffic_daily_eur AS
SELECT s.snapshot_date, s.marketplace,
       kabinet_data.to_eur(s.ordered_sales, s.currency, s.snapshot_date) AS ordered_sales,
       s.units_ordered, s.order_items, s.sessions, s.page_views, s.buy_box_pct,
       'EUR'::text AS currency, s.currency AS source_currency, s.loaded_at
  FROM kabinet_data.sales_traffic_daily s;

COMMENT ON VIEW kabinet_data.v_sales_traffic_daily_eur IS
    'sales_traffic_daily с продажами в евро по курсу ЕЦБ на дату снимка.';

CREATE OR REPLACE VIEW kabinet_data.v_orders_history_eur AS
SELECT o.order_id, o.purchase_date, o.marketplace, o.sales_channel,
       o.fulfillment_channel, o.order_status, o.sku, o.asin, o.quantity,
       kabinet_data.to_eur(o.item_price, o.currency, o.purchase_date::date) AS item_price,
       'EUR'::text AS currency, o.currency AS source_currency,
       o.first_seen, o.last_updated, o.marketplace_code
  FROM kabinet_data.orders_history o;

COMMENT ON VIEW kabinet_data.v_orders_history_eur IS
    'orders_history с ценой строки в евро по курсу ЕЦБ на дату заказа.';

GRANT SELECT ON kabinet_data.v_economics_summary_eur,
                kabinet_data.v_sales_traffic_daily_eur,
                kabinet_data.v_orders_history_eur
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- Проверка: сколько было и сколько стало по трём рынкам.
SELECT e.marketplace AS mp, e.currency_code AS cur,
       round(sum(e.net_product_sales)::numeric, 2)   AS bylo_kak_evro,
       round(sum(v.net_product_sales)::numeric, 2)   AS stalo_evro,
       round((sum(v.net_product_sales) - sum(e.net_product_sales))::numeric, 2) AS raznica
  FROM kabinet_data.economics_summary e
  JOIN kabinet_data.v_economics_summary_eur v
    ON v.sales_date = e.sales_date AND v.marketplace = e.marketplace AND v.norm_sku = e.norm_sku
 WHERE e.currency_code <> 'EUR'
 GROUP BY 1, 2 ORDER BY 1;
