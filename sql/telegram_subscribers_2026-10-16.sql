-- Подписка на тревоги через бота @kabinet_dm_alerts_bot (решение владельца 16.10.2026) вместо отдельного секрета на
-- каждого получателя. Выполнять ПОСЛЕ мержа, ДО выкладки ноутбуков-отправителей: без таблицы они шлют только владельцу
-- и пишут «подписчики не прочитались». Правило сторожа — после `databricks jobs create`
-- (nb/jobs/alerts_bot_2026-10-16/create_alerts_bot.json): вместо <JOB_ID> — его id.

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.telegram_subscribers (
    chat_id      bigint      PRIMARY KEY,           -- личный чат с ботом
    name         text,                              -- имя и @username из Telegram на момент заявки
    username     text,
    status       text        NOT NULL CHECK (status IN ('pending', 'active', 'rejected', 'stopped')),
    requested_at timestamptz NOT NULL DEFAULT now(),
    approved_by  text,                              -- кто нажал «Разрешить» / «Отклонить» (имя из Telegram)
    approved_at  timestamptz,                       -- когда
    stopped_at   timestamptz,                       -- /stop
    updated_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE kabinet_data.telegram_subscribers IS
    'Подписчики тревог Кабинета: /start в @kabinet_dm_alerts_bot → кнопка владельца. active получают копию всех тревог, '
    'что идут владельцу (основной чат kabinet-alerts/telegram-chat-id — подписан всегда, в таблице его нет). '
    'Пишет Kabinet - Alerts Bot, читают все джобы-отправители.';

CREATE TABLE IF NOT EXISTS kabinet_data.telegram_bot_state (
    key        text PRIMARY KEY,                    -- update_offset — следующий update_id для getUpdates
    value      text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE ON kabinet_data.telegram_subscribers, kabinet_data.telegram_bot_state TO "v.tereshyn@dniprom.com";
-- джобы, идущие под принципалом (Watchdog, реплика и др.), читают подписчиков
GRANT SELECT ON kabinet_data.telegram_subscribers TO "b1698364-6ec5-4240-8cd6-e06dd6e60856", "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.telegram_subscribers, kabinet_data.telegram_bot_state TO claude_code_ro;

INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, note)
VALUES (<JOB_ID>, 'Kabinet - Alerts Bot', 1, 'каждые 10 мин',
        'Подписка на тревоги через бота: заявки /start, кнопки владельца, /stop; источник nb/alerts_bot.py')
ON CONFLICT DO NOTHING;

COMMIT;

SELECT count(*) AS subscribers FROM kabinet_data.telegram_subscribers;
SELECT job_name, expected_interval_hours FROM kabinet_data.job_health_rules WHERE job_name = 'Kabinet - Alerts Bot';
