-- Реплика dnipro_m.raw_amazon_settlements для страниц Кабинета. Lakebase.
-- Первоисточник — таблица в Unity Catalog и файлы в томе kabinet_raw;
-- при расхождении прав UC. Наполняет Kabinet - Settlements Loader.

CREATE TABLE IF NOT EXISTS kabinet_data.raw_amazon_settlements (
    settlement_id               text        NOT NULL,
    row_no                      integer     NOT NULL,
    report_id                   text,
    marketplace                 text,
    settlement_start_date       date,
    settlement_end_date         date,
    deposit_date                date,
    total_amount                numeric(14,2),
    currency                    text,
    transaction_type            text,
    order_id                    text,
    merchant_order_id           text,
    adjustment_id               text,
    shipment_id                 text,
    marketplace_name            text,
    amount_type                 text,
    amount_description          text,
    amount                      numeric(14,2),
    fulfillment_id              text,
    posted_date                 date,
    posted_date_time            timestamptz,
    order_item_code             text,
    merchant_order_item_id      text,
    merchant_adjustment_item_id text,
    sku                         text,
    quantity_purchased          integer,
    promotion_id                text,
    loaded_at                   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (settlement_id, row_no)
);

COMMENT ON TABLE kabinet_data.raw_amazon_settlements IS
    'Реплика dnipro_m.raw_amazon_settlements: Settlement V2 по всем рынкам. '
    'Раскладывать по posted_date; период — для проверки полноты.';

CREATE INDEX IF NOT EXISTS raw_amazon_settlements_posted_idx
    ON kabinet_data.raw_amazon_settlements (marketplace, posted_date);
CREATE INDEX IF NOT EXISTS raw_amazon_settlements_kind_idx
    ON kabinet_data.raw_amazon_settlements (amount_type, amount_description);

GRANT SELECT ON kabinet_data.raw_amazon_settlements TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.raw_amazon_settlements TO claude_code_ro;

-- Дневная витрина: что ляжет в «Деньги» рядом с economics_summary
CREATE OR REPLACE VIEW kabinet_data.v_settlement_daily AS
SELECT marketplace, posted_date, currency, amount_type, amount_description,
       sum(amount)::numeric(14,2) AS amount, count(*) AS provodok
  FROM kabinet_data.raw_amazon_settlements
 WHERE row_no > 0
 GROUP BY 1, 2, 3, 4, 5;

GRANT SELECT ON kabinet_data.v_settlement_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_settlement_daily TO claude_code_ro;
