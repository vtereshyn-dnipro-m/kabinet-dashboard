-- Паспорт, колонка «У Дарины»: вопрос №1 закрыт её экраном Power BI (созвон 07.10.2026).
-- Отчёт «Marketplaces Report → Overall Report» за август 2026 сошёлся с прямой суммой её витрины
-- v_all_marketplaces_spiderweb_report до евро: Contribution Profit −1 746 € = sum(contribution_profit),
-- Revenue VAT Excl 69 504, VAT Incl 84 070, штуки 1 484, Expenses 57 524, Paid Sales 31 856, Spend 11 817,
-- % CM −2,08 % (к выручке с НДС) и −2,51 % (без НДС), ACOS 37 % = Spend / Paid Sales, TACOS 14 % = Spend / Revenue VAT Incl.
-- Значит DAX маржу не пересчитывает — второго вычета возвратов нет. Модель: 4 таблицы (витрина, заказы
-- v_all_marketplaces_orders_enriched, v_sku_names_categories, календарь d_Calendar_Marketplace), режим Import.
-- Открытым остаётся вопрос №2 (REFUNDED у Mirakl) — вердикт по продажам и марже по-прежнему «уточняется».
UPDATE kabinet_data.data_source_origins SET
  darina_reason = 'методика разная (у неё модельные комиссии и себестоимость на месяц продажи, у нас фактическая '
               || 'выплата Amazon). Подтверждено её экраном 07.10: маржа в Power BI — прямая сумма contribution_profit '
               || 'витрины, DAX её не пересчитывает (август −1 746 € сошёлся до евро). Уточняется одно: задумано ли у '
               || 'Mirakl вычитать возврат по строке REFUNDED, исключённой из продаж (сентябрь LM около −50 €)',
  updated_at = now()
WHERE table_name = 'kabinet_data.economics_summary';
