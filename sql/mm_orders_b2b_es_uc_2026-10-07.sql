-- Unity Catalog, для Дарины (07.10.2026): B2B ManoMano Испания одним видом — строки заказов с данными заказа.
-- В сырых таблицах B2B лежит с country = 'ES_B2B', поэтому её ES-витрины (WHERE country = 'ES') его не видят.
-- Фильтр по стране, а не по договору: колонку contract_id загрузчик заводит сам на первом прогоне.
CREATE OR REPLACE VIEW dnipro_m.kabinet_data.mm_orders_b2b_es
COMMENT 'ManoMano Pro (B2B Испания, договор 70159079): строки заказов с данными заказа. В сырых таблицах B2B лежит с country = ES_B2B, поэтому ES-витрины B2C его не видят.'
AS SELECT l.order_ref, l.sku, l.country, l.title, l.quantity, l.unit_price, l.total_price, l.unit_price_ex_vat,
          l.vat_rate, l.shipping_price, l.carrier, l.order_date, l.order_status, l.loaded_at,
          o.created_at, o.status AS order_header_status, o.is_mmf, o.manomano_discount, o.seller_discount,
          o.shipping_discount, o.total_discount, o.is_b2b, o.vat_liability, o.intraco_vat_number, o.invoice_fiscal_number
   FROM dnipro_m.kabinet_data.raw_mm_order_lines l
   LEFT JOIN dnipro_m.kabinet_data.raw_mm_orders o ON o.order_ref = l.order_ref
   WHERE l.country = 'ES_B2B';
