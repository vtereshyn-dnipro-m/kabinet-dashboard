-- Колонка «Сверка» в паспорте данных: с чем сверяется цифра, когда сверялась, чем кончилось.
--
-- Пока ни один источник не сверяется ни с чем, и в паспорте так и будет написано словом
-- «не сверяется» — это честнее пустой ячейки, которая читается как «сверка была, результата нет».
-- С понедельника подключается сверка с витриной Дарины, и результат ляжет сюда же: паспорту
-- не нужно знать, кто и как сверял, ему нужно показать три вещи — с чем, когда и чем кончилось.
ALTER TABLE kabinet_data.data_source_origins
    ADD COLUMN IF NOT EXISTS reconcile_with   TEXT,
    ADD COLUMN IF NOT EXISTS reconciled_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reconcile_result TEXT;

COMMENT ON COLUMN kabinet_data.data_source_origins.reconcile_with IS
    'С чем сверяется источник: витрина Дарины, Seller Central, отчёт площадки. Пусто = не сверяется.';
COMMENT ON COLUMN kabinet_data.data_source_origins.reconciled_at IS
    'Когда сверка проходила последний раз. Пусто при заполненном reconcile_with = сверка заведена, но ещё не шла.';
COMMENT ON COLUMN kabinet_data.data_source_origins.reconcile_result IS
    'Чем кончилась: «сошлось до евро», «расхождение 2,4 %», текст ошибки. Короткой фразой — её читают в таблице.';
