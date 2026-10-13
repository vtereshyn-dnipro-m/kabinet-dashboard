-- Напоминание о сроке client secret SP-API (13.10.2026). Применять после мержа, до выкладки патча сторожа.

INSERT INTO kabinet_data.incident_types (incident_type, mode, risk, title, description, telegram_digest)
VALUES ('secret_expiry', 'task', 'High', 'Истекает ключ Amazon',
        'Client secret приложения SP-API живёт около 180 дней. За 14 дней до конца срока (считается от даты обновления '
        'amazon-sp-api/lwa-client-secret в Databricks) сторож заводит тревогу; висит в дневной сводке, пока ключ не заменят. '
        'Заменить в трёх местах: Databricks amazon-sp-api, Streamlit Secrets Listing Suite и Кабинета.', 'daily')
ON CONFLICT (incident_type) DO NOTHING;

INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('spapi_secret_lifetime_days', 180, 'Срок жизни client secret SP-API, дней (от даты обновления секрета в Databricks)'),
       ('spapi_secret_warn_days', 14, 'За сколько дней до истечения client secret SP-API сторож заводит тревогу secret_expiry')
ON CONFLICT (key) DO NOTHING;
