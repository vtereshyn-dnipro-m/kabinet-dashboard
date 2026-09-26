-- Факт по дате ОТГРУЗКИ (ТЗ 010 §13): одно место, где живёт отгруженное количество по SKU и дате.
-- Раньше факт считался по дате заказа, и ТЗ это прямо запрещает: «дата заказа не подменяет дату
-- отгрузки ни явно по умолчанию, ни скрытым резервным правилом». Поэтому источник у каждого канала
-- свой, и в таблице всегда видно, какой именно: где данных нет, строки нет — и это честнее нуля.
CREATE TABLE IF NOT EXISTS kabinet_data.shipment_facts (
    channel        text NOT NULL,           -- AMZ-FBA, AMZ-MFN, LM, CF, MM
    marketplace    text,                    -- код маркетплейса, как в economics_summary (ES, DE, LM, CF_ES…)
    order_ref      text,                    -- номер заказа в канале: нужен для дедупликации и разбора
    shipment_ref   text,                    -- отдельная отгрузка: частичные отгрузки одного заказа различаются
    sku            text NOT NULL,
    norm_sku       text,                    -- ключ склейки с экономикой
    qty            int  NOT NULL,
    shipped_date   date NOT NULL,
    order_date     date,                    -- для анализа лага «заказ → отгрузка», в расчёт факта не идёт
    source         text NOT NULL,           -- какой загрузчик принёс строку
    loaded_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (channel, shipment_ref, sku)
);
COMMENT ON TABLE kabinet_data.shipment_facts IS
    'ТЗ 010 §13: отгруженное количество по дате отгрузки. Канал без данных строк не имеет — неполнота показывается отдельно, дата заказа подстановкой не служит.';
CREATE INDEX IF NOT EXISTS shipment_facts_date_idx ON kabinet_data.shipment_facts (shipped_date, channel);
CREATE INDEX IF NOT EXISTS shipment_facts_sku_idx  ON kabinet_data.shipment_facts (norm_sku, shipped_date);

-- Реплика сырья отчёта FBA в Lakebase. ВАЖНО: из отчёта берём только то, что нужно для факта —
-- без данных покупателя. В `GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL` есть имя, почта и адрес;
-- складывать их в наши таблицы незачем, поэтому и сырой JSON строкой мы тоже НЕ храним.
CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_fulfilled_shipments (
    marketplace          text NOT NULL,
    amazon_order_id      text NOT NULL,
    shipment_id          text,
    shipment_item_id     text NOT NULL,
    sku                  text,
    asin                 text,
    quantity_shipped     int,
    shipment_date        date,
    purchase_date        date,
    reporting_date       date,
    fulfillment_center   text,
    fulfillment_channel  text,
    item_price           numeric(12,2),
    currency             text,
    report_id            text,
    loaded_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (shipment_item_id)
);
COMMENT ON TABLE kabinet_data.raw_amazon_fulfilled_shipments IS
    'Отчёт GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL без персональных данных покупателя: дата отгрузки по заказу, SKU и количеству.';

GRANT SELECT ON kabinet_data.shipment_facts, kabinet_data.raw_amazon_fulfilled_shipments
   TO claude_code_ro, "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT INSERT, UPDATE, DELETE ON kabinet_data.shipment_facts, kabinet_data.raw_amazon_fulfilled_shipments
   TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
