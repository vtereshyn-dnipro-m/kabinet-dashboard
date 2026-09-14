-- 14.09.2026. Восемь джобов с расписанием, но без правила в job_health_rules —
-- сторож их не проверял, и Suppressed Listings Checker падал десять дней подряд
-- (SSL drop на финальной записи, с 05.09) незамеченным.
-- job_name — имя джоба в Databricks символ в символ (CLAUDE.md, «одно имя в трёх местах»).
-- Проверка идёт по job_id через Jobs API, пульс тут не нужен, поэтому парсеры
-- без system_pulse тоже покрываются.
INSERT INTO kabinet_data.job_health_rules
    (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES
    (85948015331467,   'Kabinet - CF Transactions Loader',                 26,  '10:00 Kyiv daily', NULL),
    (174154625041145,  'Kabinet - FBA Ledger Detail + Listing Cards Sync', 26,  '09:30 Kyiv daily', 'два пульса: FBA Ledger Detail Loader и Listing Cards Sync'),
    (772811628056364,  'Kabinet - MM Competitiveness Loader',              26,  '09:40 Kyiv daily', NULL),
    (565517931588672,  'Kabinet - MYI Report Collector',                   26,  '08:00 Kyiv daily', NULL),
    (474477518393306,  'Kabinet - Suppressed Listings Checker',            26,  '05:30 Kyiv daily', NULL),
    (983944537894147,  'parse_dnipro_m_pl',                                768, '1-го числа 07:00 Kyiv, ежемесячно', 'парсер сайта dnipro-m.pl → Google Sheets; порог 32 дня'),
    (1057040435613658, 'parse_dnipro_m_ua',                                768, '1-го числа 05:00 Kyiv, ежемесячно', 'парсер сайта dnipro-m.ua → Google Sheets; порог 32 дня')
ON CONFLICT DO NOTHING;

-- Review Requests (ES Evening): правило было выключено, когда проверка шла по
-- пульсу и оба расписания писали одну метку. Проверка идёт по job_id — включаем.
UPDATE kabinet_data.job_health_rules
   SET is_active = TRUE, schedule_description = '19:00 Madrid daily'
 WHERE job_id = 760565204236769;
