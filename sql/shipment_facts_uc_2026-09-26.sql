-- Выполняется в Unity Catalog (Databricks SQL), не в Lakebase: сырьё живёт в `dnipro_m.raw_*`,
-- а в `kabinet_data` лежит только его реплика (AGENTS.md, «Слои данных»).
--
-- Таблицу создаём заранее, пустой, а не первым прогоном загрузчика: `Kabinet - Shipment Facts`
-- читает её обязательным источником и падает, если источника нет. Если бы её создавал сам
-- загрузчик, то день без отгрузок ни по одному рынку оставил бы сборку факта падающей на
-- «таблицы нет» — то есть на пустоте, а не на поломке.
--
-- Колонок покупателя здесь нет намеренно: в отчёте есть имя, почта, телефон и адрес, и ни одно из
-- этих полей мы не храним. Сырой строки отчёта (колонки `raw`, как у других отчётных загрузчиков)
-- тоже нет — она вернула бы персональные данные обратно.
CREATE TABLE IF NOT EXISTS dnipro_m.dnipro_m.raw_amazon_fulfilled_shipments (
  marketplace       STRING,
  amazon_order_id   STRING,
  shipment_id       STRING,
  shipment_item_id  STRING,      -- ключ строки: одна позиция одной отгрузки
  sku               STRING,
  asin              STRING,
  quantity_shipped  INT,
  shipment_date     DATE,        -- то, ради чего всё это: фактическая дата отгрузки
  purchase_date     DATE,
  reporting_date    DATE,
  fulfillment_center STRING,
  fulfillment_channel STRING,
  item_price        DOUBLE,
  currency          STRING,
  report_id         STRING,
  loaded_at         TIMESTAMP)
COMMENT 'GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL. Данные покупателя (имя, почта, телефон, адрес) намеренно не храним, сырой строки отчёта тоже нет.';
