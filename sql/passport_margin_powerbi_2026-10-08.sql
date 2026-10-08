-- Паспорт данных, колонка «В Power BI» у экономики: итог сверки маржи за август и сентябрь 2026 (08.10.2026).
-- Вердикт остаётся «уточняется»: открыты правило 90 % себестоимости возвратов, строки REFUNDED у Leroy Merlin,
-- реклама Leroy Merlin и около 50 € в месяц внутри Power BI. Отчёт: https://claude.ai/artifact/EjzHH5AqxHQ6vQ5QhLVxt6
UPDATE kabinet_data.data_source_origins
   SET darina_verdict = 'pending',
       darina_reason =
 'сверка маржи 08.10: август −1 899 € у нас против −1 746 € в Power BI, сентябрь 2 541 € против 3 455 €; разница разложена полностью. '
 || 'Разная методика: себестоимость возвратов (у нас только годные, в Power BI 90 % всех) −1 178 / −658 €, промо и удержания Amazon (в Power BI их нет) −277 / −947 €, '
 || 'комиссии (у нас фактические, в Power BI модель) +264 / +337 €. Реклама Leroy Merlin за август +724 € — у нас не загружается. Wallapop и сайт −90 / −109 € — подключаем. '
 || 'Совпадают продажи вместе с промо, себестоимость продаж, доставка и упаковка, реклама Amazon и ManoMano. '
 || 'Уточняется: правило 90 %, REFUNDED у Leroy Merlin, реклама Leroy Merlin, около 50 € в месяц внутри Power BI. Отчёт: https://claude.ai/artifact/EjzHH5AqxHQ6vQ5QhLVxt6'
 WHERE table_name = 'kabinet_data.economics_summary';
