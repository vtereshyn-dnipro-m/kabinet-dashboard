-- Мгновенная тревога об авторизации Amazon (13.10.2026). Применять после мержа и после `databricks jobs create`
-- (job_id вписать вместо :guard_job_id).

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('amazon_auth', 'task', 'Critical', 'Авторизация Amazon не проходит',
        'Ключ SP-API или Amazon Ads больше не обменивается на токен, либо загрузчик упал на ошибке авторизации Amazon '
        '(401/403, истёкший client secret, отозванный refresh token). Следующий прогон это не исправит: загрузчики Amazon '
        'стоят, пока ключ не заменят — в Databricks amazon-sp-api, Streamlit Secrets Listing Suite и Кабинета.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
VALUES (:guard_job_id, 'Kabinet - Amazon Auth Guard', 2, 'каждые 15 минут', true,
        'Мгновенная тревога об авторизации Amazon: обмен LWA и упавшие прогоны с 401/403')
ON CONFLICT (job_id) DO UPDATE SET job_name = EXCLUDED.job_name, expected_interval_hours = EXCLUDED.expected_interval_hours,
    schedule_description = EXCLUDED.schedule_description, is_active = true, note = EXCLUDED.note;
