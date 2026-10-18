-- Реплики рекламы Amazon в Lakebase для раздела «Реклама» (решение владельца 18.10.2026, первый PR из трёх).
-- Страницы Кабинета читают только Lakebase, а отчёты рекламы, счета и сборы лежат в Unity Catalog — без реплик экран
-- их не видит. Таблицы заводит роль Кабинета этим файлом (тогда default privileges дают SELECT обоим принципалам),
-- пишет джоба Kabinet - Ads Replica (nb/ads_replica.py) под владельцем — ему INSERT/DELETE явно.
-- Выполнять ПОСЛЕ мержа и создания джобы (nb/jobs/ads_replica_2026-10-18/create_ads_replica.json): вместо
-- <JOB_ID_ADS_REPLICA> — id из `databricks jobs create`. Суммы — в валюте профиля (GB — GBP, SE — SEK, PL — PLN);
-- в евро переводит страница через kabinet_data.to_eur(сумма, валюта, дата). Рынок — код страны, Британия — GB.
BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.ads_campaign_daily (
    date date NOT NULL, country text NOT NULL, ad_product text NOT NULL, campaign_id text NOT NULL,
    campaign_name text, campaign_status text, currency text,
    impressions numeric, clicks numeric, cost numeric, orders numeric, sales numeric, units numeric,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (date, country, ad_product, campaign_id));
COMMENT ON TABLE kabinet_data.ads_campaign_daily IS
    'Реклама Amazon: кампания × день. SP — из raw_amazon_ads_sp_placement (сумма по плейсментам, продажи 14 дней), SB и SD — '
    'из таблиц кампаний аналитика raw_amazon_ads_{sb,sd}_campaign_<рынок>, включая SB без товара (их нет в Spend Power BI). '
    'Пишет Kabinet - Ads Replica, окно ads_replica_days перечитывается целиком.';

CREATE TABLE IF NOT EXISTS kabinet_data.ads_search_term_daily (
    date date NOT NULL, country text NOT NULL, ad_product text NOT NULL, campaign_id text NOT NULL, campaign_name text,
    ad_group_id text, ad_group_name text, keyword_id text, keyword text, match_type text, search_term text NOT NULL,
    currency text, impressions numeric, clicks numeric, cost numeric, orders numeric, sales numeric, units numeric,
    loaded_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ads_search_term_daily_date_country ON kabinet_data.ads_search_term_daily (date, country);
COMMENT ON TABLE kabinet_data.ads_search_term_daily IS
    'Реклама Amazon: поисковый запрос покупателя × таргет × день, SP и SB, последние ads_replica_search_term_days. '
    'Источник raw_amazon_ads_{sp,sb}_search_term. Пишет Kabinet - Ads Replica, окно перечитывается целиком.';

CREATE TABLE IF NOT EXISTS kabinet_data.ads_placement_daily (
    date date NOT NULL, country text NOT NULL, campaign_id text NOT NULL, placement text NOT NULL, campaign_name text,
    currency text, impressions numeric, clicks numeric, cost numeric, orders numeric, sales numeric, units numeric,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (date, country, campaign_id, placement));
COMMENT ON TABLE kabinet_data.ads_placement_daily IS
    'Реклама Amazon SP: кампания × плейсмент (верх поиска, страница товара, остальное) × день. Источник raw_amazon_ads_sp_placement.';

CREATE TABLE IF NOT EXISTS kabinet_data.ads_invalid_traffic_daily (
    date date NOT NULL, country text NOT NULL, ad_product text NOT NULL, campaign_id text NOT NULL, campaign_name text,
    impressions numeric, clicks numeric, gross_impressions numeric, gross_clicks numeric,
    invalid_impressions numeric, invalid_clicks numeric,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (date, country, ad_product, campaign_id));
COMMENT ON TABLE kabinet_data.ads_invalid_traffic_daily IS
    'Реклама Amazon SP и SB: всего и недействительных показов и кликов × кампания × день (Amazon недействительные не '
    'списывает). Источник raw_amazon_ads_gross_invalid.';

CREATE TABLE IF NOT EXISTS kabinet_data.ads_fees_daily (
    date date NOT NULL, profile_country text NOT NULL, fee_country text, fee_type text, currency text,
    fee_amount numeric, invoice_key text, invoice_status text, allocation text,
    loaded_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ads_fees_daily_date ON kabinet_data.ads_fees_daily (date, profile_country);
COMMENT ON TABLE kabinet_data.ads_fees_daily IS
    'Регуляторный сбор Amazon Ads по дням: реплика dnipro_m.v_amazon_ads_fees_daily (сбор счёта разнесён по дням '
    'периода пропорционально расходу). profile_country — профиль рекламы, fee_country — страна показа.';

CREATE TABLE IF NOT EXISTS kabinet_data.ads_invoices (
    invoice_key text NOT NULL, profile_country text NOT NULL, invoice_id text, status text, invoice_date date,
    from_date date, to_date date, amount_due numeric, tax_amount_due numeric, currency text,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_country, invoice_key));      -- набирающийся счёт — ACCUMULATING:<дата> у каждого профиля
COMMENT ON TABLE kabinet_data.ads_invoices IS
    'Счета Amazon Ads по профилям (реплика raw_amazon_ads_invoices без сырого ответа). amount_due — без НДС и уже со '
    'сбором, tax_amount_due — НДС (ES 21 %, IT/FR/DE 0 — обратное начисление).';

GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.ads_campaign_daily, kabinet_data.ads_search_term_daily,
    kabinet_data.ads_placement_daily, kabinet_data.ads_invalid_traffic_daily, kabinet_data.ads_fees_daily,
    kabinet_data.ads_invoices TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.ads_campaign_daily, kabinet_data.ads_search_term_daily, kabinet_data.ads_placement_daily,
    kabinet_data.ads_invalid_traffic_daily, kabinet_data.ads_fees_daily, kabinet_data.ads_invoices
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('ads_replica_days', 120, 'Реплики рекламы: сколько последних дней кампаний, плейсментов, недействительного трафика и сборов перечитывать', now()),
 ('ads_replica_search_term_days', 35, 'Реплики рекламы: сколько последних дней поисковых запросов держать в Lakebase (экран показывает 30)', now())
ON CONFLICT (key) DO NOTHING;

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID_ADS_REPLICA>, 'Kabinet - Ads Replica', 26, '10:20 Kyiv daily',
        'Реплики рекламы Amazon в Lakebase для раздела «Реклама»; источник nb/ads_replica.py')
ON CONFLICT DO NOTHING;

INSERT INTO kabinet_data.data_freshness_rules
       (table_name, date_column, max_age_hours, content_date_column, max_content_age_hours,
        source_type, owner_role, is_active, comment, updated_at) VALUES
 ('kabinet_data.ads_campaign_daily', 'loaded_at', 30, 'date', 72, 'lakebase', 'ads', true,
  'Реклама Amazon по кампаниям (реплика). Содержимое: последний день с расходом — реклама крутится каждый день', now()),
 ('kabinet_data.ads_search_term_daily', 'loaded_at', 30, NULL, NULL, 'lakebase', 'ads', true,
  'Поисковые запросы рекламы (реплика). По содержимому не проверяем: Amazon отдаёт запросы с задержкой', now())
ON CONFLICT (table_name) DO NOTHING;
COMMIT;

SELECT table_name, has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.' || table_name, 'SELECT') app_select
FROM information_schema.tables WHERE table_schema = 'kabinet_data' AND table_name LIKE 'ads\_%' AND table_name IN
 ('ads_campaign_daily','ads_search_term_daily','ads_placement_daily','ads_invalid_traffic_daily','ads_fees_daily','ads_invoices');
