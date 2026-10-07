-- Паспорт данных, колонка «У Дарины»: описание методики по её Power BI (разбор 07.10.2026) и пятый вердикт
-- «уточняется». Срок сравнения — 09.10.2026 (решение владельца); что Дарина не подтвердит к сроку, стоит с этим словом.
--
-- Что изменилось против описания от 05.10 (passport_darina_2026-10-05.sql):
--  * Power BI читает v_all_marketplaces_spiderweb_report в режиме Import через кластер, DAX нам не виден;
--  * Amazon в её витрине — таблица raw_amazon_spiderweb_report, её пересобирает джоба «Test spiderweb Amazon» в 10:50;
--  * прибыль Amazon у неё теперь ПОСЛЕ возвратов: profit − refunds + other_net_result + cogs_refund − доставка возврата;
--  * себестоимость возврата возвращается × 0,9 («1 из 10 — брак») со всех возвращённых штук, срез на месяц возврата;
--  * у Leroy Merlin, ManoMano, Carrefour строка REFUNDED исключена из продаж, но её цена вычтена как возврат —
--    похоже на двойной вычет (сентябрь LM около −50 €), ждёт подтверждения.
-- «Уточняется» — не пятый результат сравнения, а его отсутствие: ответ зависит от вопроса, который задан Дарине.
ALTER TABLE kabinet_data.data_source_origins DROP CONSTRAINT IF EXISTS data_source_origins_darina_verdict_check;
ALTER TABLE kabinet_data.data_source_origins ADD CONSTRAINT data_source_origins_darina_verdict_check
    CHECK (darina_verdict IS NULL OR darina_verdict IN ('same', 'ours_better', 'hers_better', 'different', 'pending'));

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'Power BI (режим Import, раз в день около 11:10) читает витрину v_all_marketplaces_spiderweb_report; '
               || 'Amazon в ней — таблица raw_amazon_spiderweb_report, которую пересобирает джоба «Test spiderweb Amazon» '
               || 'в 10:50. Amazon: заказанные продажи Sales & Traffic по дате заказа без НДС; комиссия — модель '
               || '(реферальный % × цена, плюс 3 % от него и FBA-сбор из оценки); себестоимость — срез на месяц продажи, '
               || 'у набора по составу; прибыль ПОСЛЕ возвратов: profit − refunds + other_net_result + cogs_refund − '
               || 'доставка возврата, возвраты и компенсации — по дате settlement. Mirakl: строки заказов по дате заказа, '
               || 'отменённые и REFUNDED исключены из продаж, цена REFUNDED вычтена как возврат. UK, SE, PL — в евро по '
               || 'нашей таблице курсов raw_ecb_fx_rates.',
  darina_verdict = 'pending',
  darina_reason = 'методика разная (у неё модельные комиссии и себестоимость на месяц продажи, у нас фактическая '
               || 'выплата Amazon), но итог сравнения уточняется у Дарины: не вычитает ли DAX возвраты второй раз '
               || 'поверх profit и задумано ли у Mirakl вычитать возврат по строке, исключённой из продаж '
               || '(сентябрь LM около −50 €)',
  updated_at = now()
WHERE table_name = 'kabinet_data.economics_summary';

UPDATE kabinet_data.data_source_origins SET
  darina_method = 'возвращает 90 % себестоимости КАЖДОЙ возвращённой штуки («1 из 10 — брак»), по срезу себестоимости '
               || 'на месяц возврата, у всех каналов (cogs_refund), без учёта состояния товара',
  darina_verdict = 'different',
  darina_reason = 'у неё 90 % себестоимости любого возврата, у нас — себестоимость только годного по факту (Amazon '
               || 'или Odoo, включая проверку на складе брака); коэффициент 0,9 — правило или временная заглушка, '
               || 'уточняется у Дарины',
  updated_at = now()
WHERE table_name = 'kabinet_data.v_returns_cogs_credit';
