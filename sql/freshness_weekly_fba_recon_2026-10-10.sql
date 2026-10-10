-- Пороги свежести (10.10.2026): два ложных «устарело» в сводке сторожа.
-- 1) Возмещения FBA: загрузчик Kabinet - FBA Charges Loader с 27.09.2026 ходит раз в неделю (понедельник 07:30 Kyiv),
--    а порог синка остался суточным — 30 ч. Как у хранения: 192 ч (неделя + сутки запаса).
-- 2) Результаты сверки: date_column = calc_date — ДАТА без времени, то есть возраст считается от полуночи UTC. Сверка
--    идёт в 13:00 Kyiv, ровно когда и сторож, а с 09.10.2026 сначала ждёт реплику Power BI и пишет расчёт на несколько
--    минут позже проверки — в момент проверки свежей строки ещё нет, возраст вчерашней 34 ч > 30. Порог 48 ч: сутки
--    от полуночи плюс время расчёта, а пропущенный день всё равно даёт 58 ч и тревогу.
BEGIN;
UPDATE kabinet_data.data_freshness_rules
   SET max_age_hours = 192,
       comment = 'Возмещения FBA. Загрузчик Kabinet - FBA Charges Loader раз в неделю (пн 07:30 Kyiv) — синк 192 ч; '
                 'приходят нерегулярно — 47 за полгода; порог содержимого 30 дней ловит только полную тишину.',
       updated_at = now()
 WHERE table_name = 'kabinet_data.raw_amazon_fba_reimbursements';
UPDATE kabinet_data.data_freshness_rules
   SET max_age_hours = 48,
       comment = 'Результаты сверки (Kabinet - Reconciliation, 13:00 Kyiv). Питают колонку «Сверка» в паспорте данных. '
                 'calc_date — дата без времени: возраст от полуночи, поэтому 48 ч, а не 30.',
       updated_at = now()
 WHERE table_name = 'kabinet_data.reconciliation_results';
COMMIT;
