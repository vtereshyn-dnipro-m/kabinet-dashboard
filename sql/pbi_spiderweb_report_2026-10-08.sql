-- Реплика витрины Power BI (08.10.2026, решение владельца: Кабинет показывает ТЕ ЖЕ цифры, что Power BI).
-- Источник — dnipro_m.dnipro_m.v_all_marketplaces_spiderweb_report (отчёт «Marketplaces Report», режим Import, DAX
-- почти нет — карточки это прямые суммы колонок витрины). Страницы Кабинета ходят только в Lakebase, поэтому витрина
-- копируется сюда джобой Kabinet - Power BI Replica. Первоисточник остаётся в dnipro_m: при расхождении прав он.
--
-- Строка — день × рынок × SKU: у витрины одна строка на день × площадку × страну × SKU × ASIN (у SKU бывает два
-- ASIN), суммы при схлопывании не меняются. Строки, где все числа нулевые (витрина плотная: 200 тыс. строк, из них
-- с числами 28 тыс.), не копируются — на суммы это не влияет.
-- Колонки — как в витрине, один в один, кроме двух переименованных (paidUnits, paidSales: в Postgres регистр
-- имени без кавычек теряется). Тип — double precision, как в витрине: суммы сходятся до цента.
BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.pbi_spiderweb_report (
    date                         date             NOT NULL,
    marketplace                  text             NOT NULL,   -- код рынка Кабинета: ES, IT, GB, LM, MM_ES, CF_ES, WP_ES…
    sku                          text             NOT NULL,   -- SKU, как в витрине
    pbi_marketplace              text             NOT NULL,   -- площадка, как в витрине: Amazon, Leroy Merlin, …
    pbi_country                  text             NOT NULL,   -- страна, как в витрине: Spain, Italy, United Kingdom…
    units_sold                   double precision NOT NULL DEFAULT 0,
    sales_vat_incl               double precision NOT NULL DEFAULT 0,
    sales_vat_excl               double precision NOT NULL DEFAULT 0,
    tax_amount                   double precision NOT NULL DEFAULT 0,
    commission_fee_vat_excl      double precision NOT NULL DEFAULT 0,
    cancel_commission_vat_excl   double precision NOT NULL DEFAULT 0,
    cogs_total                   double precision NOT NULL DEFAULT 0,
    shipping_cost_total          double precision NOT NULL DEFAULT 0,
    packing_cost_total           double precision NOT NULL DEFAULT 0,
    expenses                     double precision NOT NULL DEFAULT 0,
    quantity_refund              double precision NOT NULL DEFAULT 0,
    refund_total_vat_incl        double precision NOT NULL DEFAULT 0,
    refund_total_vat_excl        double precision NOT NULL DEFAULT 0,
    refunds_commissions_vat_excl double precision NOT NULL DEFAULT 0,
    expenses_refund              double precision NOT NULL DEFAULT 0,
    cogs_refund                  double precision NOT NULL DEFAULT 0,
    shipping_cost_refund         double precision NOT NULL DEFAULT 0,
    reimbursment                 double precision NOT NULL DEFAULT 0,
    impressions                  double precision NOT NULL DEFAULT 0,
    clicks                       double precision NOT NULL DEFAULT 0,
    spend                        double precision NOT NULL DEFAULT 0,
    paid_units                   double precision NOT NULL DEFAULT 0,
    paid_sales                   double precision NOT NULL DEFAULT 0,
    profit                       double precision NOT NULL DEFAULT 0,
    contribution_profit          double precision NOT NULL DEFAULT 0,
    loaded_at                    timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (date, marketplace, sku)
);
CREATE INDEX IF NOT EXISTS pbi_spiderweb_report_mk_date ON kabinet_data.pbi_spiderweb_report (marketplace, date);

COMMENT ON TABLE kabinet_data.pbi_spiderweb_report IS
  'Реплика витрины Power BI v_all_marketplaces_spiderweb_report (Kabinet - Power BI Replica). Из неё Кабинет берёт '
  'продажи с НДС и без, штуки, Contribution Profit, расходы, рекламу, ACOS и TACOS — те же цифры, что в Power BI.';

-- пишет джоба под владельцем; читают приложение и принципал джоб
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.pbi_spiderweb_report TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.pbi_spiderweb_report TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.pbi_spiderweb_report TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- свежесть — по СОДЕРЖИМОМУ (дата продаж; у Amazon в витрине по вчера), 72 ч как у Sales & Traffic: этот же порог
-- читает паспорт данных у цифр. Живость самой джобы — правило job_health_rules (sql/pbi_replica_job_rule_2026-10-08.sql)
INSERT INTO kabinet_data.data_freshness_rules (table_name, date_column, max_age_hours, source_type, owner_role, is_active, comment)
VALUES ('kabinet_data.pbi_spiderweb_report', 'date', 72, 'lakebase-replica', 'data', true,
        'Реплика витрины Power BI: Kabinet - Power BI Replica 12:45 и 16:45 Kyiv. Из неё Кабинет показывает продажи, штуки, '
        'Contribution Profit и рекламу — те же цифры, что в Power BI. Возраст — по дате продаж.')
ON CONFLICT (table_name) DO UPDATE SET date_column = EXCLUDED.date_column, max_age_hours = EXCLUDED.max_age_hours,
    source_type = EXCLUDED.source_type, comment = EXCLUDED.comment, is_active = true;

-- паспорт данных: откуда цифры на «Обзоре», в «Деньгах», на «Рекламе» и «Площадках»
INSERT INTO kabinet_data.data_source_origins (table_name, platform_source, platform_refresh, our_refresh, verdict, note)
VALUES ('kabinet_data.pbi_spiderweb_report',
        'Power BI «Marketplaces Report»: витрина v_all_marketplaces_spiderweb_report (Amazon — Sales & Traffic и модель комиссий, Mirakl — заказы, Odoo — Wallapop и сайт)',
        'витрина пересчитывается из сырья каждый день; отчёт Power BI обновляется по своему расписанию',
        'дважды в день: 12:45 и 16:45 Kyiv',
        'ok',
        'Цифры как в Power BI: продажи без НДС у Amazon — продажи с НДС, делённые на ставку страны; Contribution Profit — прибыль витрины минус реклама.')
ON CONFLICT (table_name) DO UPDATE SET platform_source = EXCLUDED.platform_source, platform_refresh = EXCLUDED.platform_refresh,
    our_refresh = EXCLUDED.our_refresh, verdict = EXCLUDED.verdict, note = EXCLUDED.note;
COMMIT;
