-- Расчётные отчёты Amazon (Settlement V2 flat file). Unity Catalog, слой сырья.
--
-- Один settlement = один рынок и один расчётный период; строка 0 файла —
-- итог отчёта (total_amount), остальные — проводки, каждая со своей датой
-- posted_date. Раскладывать в календарь по posted_date, а не по периоду:
-- иначе не состыкуется с economics_summary. Период держим отдельными
-- колонками ради проверки полноты — периоды одного рынка идут встык.
--
-- 24 колонки повторяют raw_amazon_settlements_es символ в символ, чтобы
-- вью Дарины продолжили работать после переноса. Наши четыре: row_no,
-- report_id, marketplace, loaded_at.
--
-- Сами файлы как пришли — в томе kabinet_raw/amazon_settlements/raw/.

CREATE TABLE IF NOT EXISTS dnipro_m.dnipro_m.raw_amazon_settlements (
  settlement_id               STRING  NOT NULL COMMENT 'ключ, часть 1',
  row_no                      INT     NOT NULL COMMENT 'ключ, часть 2: номер строки в файле, 0 = итоговая строка отчёта',
  report_id                   STRING           COMMENT 'reportId в SP-API; один settlement Amazon иногда выдаёт двумя отчётами байт-в-байт',
  marketplace                 STRING           COMMENT 'наш код рынка по доминирующему marketplace-name в файле; NULL — только сервисные проводки без рынка',
  settlement_start_date       DATE,
  settlement_end_date         DATE,
  deposit_date                DATE,
  total_amount                DECIMAL(14,2)    COMMENT 'итог выплаты, только в row_no = 0',
  currency                    STRING,
  transaction_type            STRING,
  order_id                    STRING,
  merchant_order_id           STRING,
  adjustment_id               STRING,
  shipment_id                 STRING,
  marketplace_name            STRING,
  amount_type                 STRING,
  amount_description          STRING,
  amount                      DECIMAL(14,2),
  fulfillment_id              STRING,
  posted_date                 DATE             COMMENT 'дата проводки — по ней раскладываем в календарь',
  posted_date_time            TIMESTAMP,
  order_item_code             STRING,
  merchant_order_item_id      STRING,
  merchant_adjustment_item_id STRING,
  sku                         STRING,
  quantity_purchased          INT,
  promotion_id                STRING,
  loaded_at                   TIMESTAMP,
  CONSTRAINT raw_amazon_settlements_pk PRIMARY KEY (settlement_id, row_no)
)
USING DELTA
COMMENT 'Settlement V2 flat file по всем рынкам EU-аккаунта. Источник: SP-API getReports (отчёт запросить нельзя, Amazon создаёт сам раз в две недели, через API виден 90 дней с даты создания). Загрузчик: Kabinet - Settlements Loader. Реплика для страниц: kabinet_data.raw_amazon_settlements в Lakebase.';
