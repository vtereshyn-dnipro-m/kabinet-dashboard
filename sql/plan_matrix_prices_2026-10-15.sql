-- Plan Matrix, шаг 1: средняя цена SKU × маркетплейс × месяц (ноутбук nb/plan_matrix_prices.py,
-- джоба «Kabinet - Plan Matrix Prices»). Выполнять ПОСЛЕ мержа PR и ДО первого прогона джобы.
--
-- Две таблицы, потому что вопросов два:
--   plan_price_daily — что было известно на дату: расчёт «на сегодня» по каждой паре, строка на день. Это история,
--                      из неё же берётся цена замораживаемого месяца («на 15-е»), и по ней видно, откуда цена;
--   plan_price_month — цена месяца, которую видит таблица: frozen = зафиксирована, такую строку прогон не меняет
--                      (условие WHERE NOT frozen стоит в самом UPSERT ноутбука).
-- Пары, по которым цены нет, тоже лежат строкой (source = kit_only / listed_no_price / none): «пусто» должно быть
-- видно с причиной, иначе его не отличить от «не считали».

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.plan_price_daily (
    calc_date   date        NOT NULL,                 -- расчёт «на дату»: данные по эту дату включительно
    marketplace text        NOT NULL,                 -- код справочника: AMZ-ES, LM-ES, MM-FR, TTS-ES …
    sku         text        NOT NULL,                 -- SKU как во вкладке таблицы
    price       numeric(12,2),                        -- с НДС; пусто — цены нет (причина в source)
    source      text        NOT NULL CHECK (source IN ('sales', 'sp_api', 'scrape', 'buybox', 'offer',
                                                     'listed_no_price', 'kit_only', 'none')),
    units       integer,                              -- штук за окно продаж
    revenue     numeric(14,2),                        -- выручка за окно продаж, с НДС, после скидок продавца
    n_obs       integer,                              -- сколько листингов / снимков / проверок Buy Box / офферов усреднено
    note        text,                                 -- окно или дата отчёта, купон; у пустых — почему пусто
    computed_at timestamptz NOT NULL DEFAULT now(),   -- когда посчитано (для дозаполненных задним числом — позже calc_date)
    PRIMARY KEY (calc_date, marketplace, sku)
);
COMMENT ON TABLE kabinet_data.plan_price_daily IS
    'Plan Matrix: средняя цена «на дату» по SKU × маркетплейс. sales — средневзвешенная цена продаж за '
    'plan_price_sales_window_days (от plan_price_min_units штук); sp_api — наша цена листинга Amazon из отчёта листингов; '
    'scrape — средняя цена витрины Amazon (ScrapingDog); buybox — средняя цена Buy Box (SP-API) за '
    'plan_price_listing_window_days; у sp_api и scrape вычтен купон из ScrapingDog; offer — цена активного оффера Mirakl; '
    'listed_no_price / kit_only / none — цены нет. Пишет Kabinet - Plan Matrix Prices.';

CREATE TABLE IF NOT EXISTS kabinet_data.plan_price_month (
    marketplace text        NOT NULL,
    sku         text        NOT NULL,
    month       date        NOT NULL,                 -- первое число месяца плана
    price       numeric(12,2),
    source      text        NOT NULL,
    calc_date   date        NOT NULL,                 -- расчёт какого дня взят: сегодня или «на 15-е» у замороженных
    frozen      boolean     NOT NULL DEFAULT false,
    frozen_at   timestamptz,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (marketplace, sku, month),
    FOREIGN KEY (calc_date, marketplace, sku) REFERENCES kabinet_data.plan_price_daily (calc_date, marketplace, sku)
);
COMMENT ON TABLE kabinet_data.plan_price_month IS
    'Plan Matrix: цена месяца. Месяц M обновляется ежедневно до plan_price_freeze_day-го числа месяца M−1 и с '
    'следующего дня зафиксирован ценой расчёта на это число (frozen). Замороженную строку прогон не меняет.';

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('plan_price_sales_window_days', 90,
  'Plan Matrix: окно продаж для средней цены, дней по дату расчёта включительно («последние 3 месяца»)', now()),
 ('plan_price_listing_window_days', 30,
  'Plan Matrix: окно усреднения цены витрины Amazon (ScrapingDog) и Buy Box и поиска купона, дней', now()),
 ('plan_price_min_units', 3,
  'Plan Matrix: минимум проданных штук за окно, чтобы цена считалась по продажам; меньше — цена листинга '
  '(решение владельца 14.10.2026); нет и её — цена продаж', now()),
 ('plan_price_freeze_day', 15,
  'Plan Matrix: число месяца M−1, ценой на которое фиксируется месяц M; со следующего дня цена месяца не меняется', now()),
 ('plan_price_sheet_write', 0,
  'Plan Matrix: 1 — писать цены во вкладку avg_price таблицы Plan Matrix; 0 — не писать (до решения владельца)', now())
ON CONFLICT (key) DO NOTHING;

-- Джоба идёт под владельцем; принципал джоб — на случай переноса; приложение и read-only роль — только чтение
GRANT SELECT, INSERT, UPDATE ON kabinet_data.plan_price_daily, kabinet_data.plan_price_month TO "v.tereshyn@dniprom.com";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.plan_price_daily, kabinet_data.plan_price_month
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT ON kabinet_data.plan_price_daily, kabinet_data.plan_price_month TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.plan_price_daily, kabinet_data.plan_price_month TO claude_code_ro;

COMMIT;

SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'plan_price_%' ORDER BY key;
