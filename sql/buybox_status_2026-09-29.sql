-- Состояние витрины по ASIN × рынок из SP-API Product Pricing (с 29.09.2026).
--
-- Почему не из снимков Scrapingdog: на малых рынках блока покупки в снимке нет, и вчера я
-- счёл это дефектом сборщика. Проверка через API показала обратное — блока нет, потому что
-- ПОКУПАТЬ НЕЧЕГО: по IE 137 наших ASIN из 138 отвечают `NoBuyableOffers`, по GB 24 из 28.
-- Сборщик показывал правду. Но API отвечает и там, где снимок пуст, и отвечает определённее:
-- владелец Buy Box, его цена, есть ли покупаемый оффер вообще.
--
-- `status` — три РАЗНЫХ состояния, и путать их нельзя:
--   ours        — Buy Box наш;
--   competitor  — Buy Box у другого продавца (на GB это Amazon EU, на DE Amazon);
--   no_offers   — покупаемых офферов нет вовсе. Это не «потеря Buy Box», а «товар не купить».
--
-- Наш продавец — один id на весь европейский аккаунт: `A4JU8NB3VJG0K`. Флаг `MyOffer` в ответе
-- Amazon не выставляет даже там, где оффер наш, поэтому сравниваем по `SellerId`.

CREATE TABLE IF NOT EXISTS kabinet_data.buybox_status (
    asin              text        NOT NULL,
    marketplace       text        NOT NULL,          -- код страны, как в economics_summary (GB, не co.uk)
    checked_at        timestamptz NOT NULL DEFAULT now(),
    status            text        NOT NULL CHECK (status IN ('ours', 'competitor', 'no_offers')),
    buybox_seller_id  text,
    buybox_seller     text,                          -- человекочитаемое имя, когда знаем
    buybox_price      numeric(12,2),
    buybox_shipping   numeric(12,2),
    buybox_is_fba     boolean,
    currency          text,
    our_price         numeric(12,2),                 -- наш оффер, если он в ответе есть
    offers_total      int,
    PRIMARY KEY (asin, marketplace, checked_at)
);

CREATE INDEX IF NOT EXISTS buybox_status_last
    ON kabinet_data.buybox_status (marketplace, asin, checked_at DESC);

-- Последнее состояние по каждой паре — то, что читают сторож и страница.
CREATE OR REPLACE VIEW kabinet_data.v_buybox_current AS
SELECT DISTINCT ON (asin, marketplace) *
  FROM kabinet_data.buybox_status
 ORDER BY asin, marketplace, checked_at DESC;

INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('buybox_max_age_hours', '30',
   'По состоянию витрины старше этого срока алерт не заводим: загрузчик ходит раз в сутки, и вчерашнее «продаёт Amazon» может быть уже неправдой.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;

INSERT INTO kabinet_data.incident_types (incident_type, title, description, risk) VALUES
  ('buybox_no_offers', 'Товар нельзя купить',
   'На витрине нет ни одного покупаемого оффера: кнопки покупки нет вовсе. Это не потеря Buy Box конкуренту, а листинг, по которому продаж быть не может.',
   'High')
ON CONFLICT (incident_type) DO UPDATE
  SET title = COALESCE(kabinet_data.incident_types.title, EXCLUDED.title),
      description = COALESCE(kabinet_data.incident_types.description, EXCLUDED.description),
      risk = COALESCE(kabinet_data.incident_types.risk, EXCLUDED.risk);

SELECT count(*) AS строк_состояния FROM kabinet_data.buybox_status;

-- Пауза между батчами. Частота Product Pricing — 0.1 запроса в секунду с запасом 1,
-- то есть ОДИН запрос в десять секунд. Проба с тремя секундами прошла лишь потому,
-- что делала по одному батчу на рынок; полный прогон сразу получил 429 QuotaExceeded.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('buybox_batch_pause_sec', '11',
   'Секунд между батчами getItemOffersBatch. Лимит Amazon — 0.1 запроса в секунду; 11 с даёт запас.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, note = EXCLUDED.note;
