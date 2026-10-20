-- Утренняя сводка, вторая версия (20.10.2026, решение владельца). Применять ПОСЛЕ мержа и ДО выкладки ноутбука:
-- новый nb/morning_report.py пишет в kabinet_data.morning_reports и читает incident_types.area.

-- 1. Журнал отправок: текст каждой сводки и итог отправки. Пишет только Kabinet - Morning Report (под владельцем);
--    dry_run не пишет. Удаление строк — никогда сам (AGENTS.md); журнал маленький — одна строка в день.
CREATE TABLE IF NOT EXISTS kabinet_data.morning_reports (
    id          bigserial PRIMARY KEY,
    report_date date NOT NULL,
    sent_at     timestamptz NOT NULL DEFAULT now(),
    text        text NOT NULL,
    sent        boolean NOT NULL,
    error       text
);
CREATE INDEX IF NOT EXISTS morning_reports_date_idx ON kabinet_data.morning_reports (report_date DESC);
COMMENT ON TABLE kabinet_data.morning_reports IS
  'Утренняя сводка ночи (Kabinet - Morning Report): текст каждой отправки, ушла ли, текст сбоя.';
GRANT SELECT, INSERT ON kabinet_data.morning_reports TO claude_code_rw;
GRANT SELECT, INSERT ON kabinet_data.morning_reports TO "v.tereshyn@dniprom.com";
GRANT SELECT ON kabinet_data.morning_reports TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT, INSERT ON kabinet_data.morning_reports TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE ON SEQUENCE kabinet_data.morning_reports_id_seq TO claude_code_rw, "v.tereshyn@dniprom.com",
    "b1698364-6ec5-4240-8cd6-e06dd6e60856";

-- 2. Блок сводки — в incident_types.area (колонка была пустой у всех 39 типов и нигде не читалась). «Бизнес» —
--    то, что решают продажи и снабжение: остатки, дефицит, заказы и приёмка площадок, листинги, Buy Box, прогноз.
--    Остальное — «Техника». Тип без area сводка кладёт в технику, чтобы новый тип заметили.
UPDATE kabinet_data.incident_types SET area = 'business', updated_at = now(), updated_by = 'claude_code'
WHERE incident_type IN ('low_stock', 'out_of_stock', 'coverage_reaction', 'lm_offer_out_of_stock',
                        'lm_order_not_accepted', 'leroy_merlin_order_not_accepted', 'carrefour_order_not_accepted',
                        'manomano_order_not_accepted', 'leroy_merlin_health_degraded', 'carrefour_health_degraded',
                        'manomano_health_degraded', 'listing_pair_blocked', 'listing_suppressed', 'listing_pair_missing',
                        'buybox_lost', 'buybox_no_offers', 'account_health', 'missing_forecast', 'partial_forecast',
                        'forecast_pace', 'lead_time_deviation');
UPDATE kabinet_data.incident_types SET area = 'tech', updated_at = now(), updated_by = 'claude_code'
WHERE area IS NULL;

-- 3. Подписи LM были перепутаны: «(старое имя)» стояло на живом типе. Mirakl Health с 05.09.2026 пишет
--    leroy_merlin_order_not_accepted; lm_order_not_accepted — прежнее имя, последний раз 29.08.2026.
UPDATE kabinet_data.incident_types SET title = 'LM: заказ ждёт подтверждения',
       note = 'группа «Площадки»: заказ ждёт подтверждения; пишет Kabinet - Mirakl Health (с 05.09.2026)',
       updated_at = now(), updated_by = 'claude_code'
WHERE incident_type = 'leroy_merlin_order_not_accepted';
UPDATE kabinet_data.incident_types SET title = 'LM: заказ ждёт подтверждения (старое имя)',
       note = 'старое имя типа (до 05.09.2026), встречается в журнале',
       updated_at = now(), updated_by = 'claude_code'
WHERE incident_type = 'lm_order_not_accepted';

-- 4. Подпись правила промо отстала от расписания: с #342 (19.10.2026) промо в 03:05, не в 08:50.
UPDATE kabinet_data.job_health_rules SET schedule_description = '03:05 Kyiv daily'
WHERE job_id = 907284097553767 AND job_name = 'Kabinet - Amazon Promotions Loader';
