-- Сверка: объяснённое расхождение отдельно от необъяснённого. 03.10.2026.
--
-- До этого строка сверки знала один вердикт — ok / off / no_data. Красными были 25 строк в
-- день, и почти все — разные ОПРЕДЕЛЕНИЯ, а не ошибки данных: у Дарины комиссия модельная и на
-- все заказанные штуки, у нас фактическая и только на отгруженные; у неё себестоимость на месяц
-- продажи, у нас последний срез. Отдать такое сторожу как есть — получить ежедневный поток
-- ложных тревог, после которого канал перестают читать.
--
-- Поэтому расхождение раскладывается по слагаемым (`components`), объяснимая часть подписывается
-- словами (`explanation`), и сторожу уходит только то, где `verdict = 'off' AND NOT explained`.
ALTER TABLE kabinet_data.reconciliation_results ADD COLUMN IF NOT EXISTS explained boolean;
ALTER TABLE kabinet_data.reconciliation_results ADD COLUMN IF NOT EXISTS explanation text;
ALTER TABLE kabinet_data.reconciliation_results ADD COLUMN IF NOT EXISTS components jsonb;

COMMENT ON COLUMN kabinet_data.reconciliation_results.explained IS
  'true — расхождение разложено и объяснено (разная база, известная причина); false — не объяснено, уходит сторожу; NULL — расхождения нет';
COMMENT ON COLUMN kabinet_data.reconciliation_results.components IS
  'разложение по слагаемым: для комиссий — реферальный/digital/FBA/прочее с базой штук и ставкой за штуку; для себестоимости — эффект штук и эффект цены за единицу';

-- допуски разложения — в настройках, а не в коде
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
  ('recon_rate_tolerance_pct', 5,
   'Сверка комиссий по слагаемым: ставка за штуку у нас и у Дарины должна совпадать в пределах этого процента — тогда разница в сумме объясняется базой штук, а не ошибкой'),
  ('recon_unit_cost_tolerance_pct', 6,
   'Сверка себестоимости: расхождение цены за единицу в пределах этого процента объясняется датой цены (у Дарины на месяц продажи, у нас последний срез)')
ON CONFLICT (key) DO NOTHING;

-- тип инцидента для сторожа: название заполнено сразу, иначе он покажется кодом
INSERT INTO kabinet_data.incident_types (incident_type, title, description)
VALUES ('reconciliation', 'Сверка: необъяснённое расхождение',
        'Наши цифры расходятся с витриной Дарины или с settlement Amazon сверх допуска, и разложение по слагаемым причину не нашло. Объяснимые расхождения (разная база штук, дата себестоимости, сдвиг по дням) сюда не попадают — они подписаны в «Сверке» паспорта.')
ON CONFLICT (incident_type) DO NOTHING;
