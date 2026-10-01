-- Тестовый вход для QA-агентов по ссылке `?qa=токен` (задание владельца 01.10.2026).
--
-- В задании было «токен в секретах Streamlit» И «кнопка сменить токен». Это
-- противоречие: приложение не может править собственные секреты — такая правка всегда
-- ручная и с перезапуском, то есть «одним нажатием» не получится, а именно это и нужно
-- в тот момент, когда ссылка утекла. Развязка: сам токен живёт ЗДЕСЬ, хешем, и кнопка
-- его меняет; в секретах Streamlit лежит «перец» (`[qa] pepper`) — без него украденный
-- дамп базы в рабочую ссылку не превратить.
--
-- Открытый токен не хранится нигде, даже у нас: он показывается один раз при выдаче.
-- Потерял — выпусти новый, это одно нажатие; восстановить старый нельзя и не нужно.

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.qa_tokens (
    id          bigserial PRIMARY KEY,
    token_hash  text        NOT NULL UNIQUE,
    label       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  text,
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    last_used_at timestamptz,
    uses        integer     NOT NULL DEFAULT 0
);

COMMENT ON TABLE kabinet_data.qa_tokens IS
    'Токены тестового входа QA. Хранится только хеш: открытый токен показывается один раз при выдаче.';

CREATE INDEX IF NOT EXISTS qa_tokens_live_idx
    ON kabinet_data.qa_tokens (expires_at) WHERE revoked_at IS NULL;

-- Отдельный выключатель, по умолчанию ВЫКЛЮЧЕН (требование владельца): пока он ноль,
-- ссылка не работает, даже если токен жив и не просрочен. Включают на время проверки.
INSERT INTO kabinet_data.reorder_params (key, value, note) VALUES
    ('qa_access_enabled', 0,
     'Тестовый вход QA по ссылке ?qa=: 1 включён, 0 выключен. По умолчанию выключен.'),
    ('qa_token_days', 7, 'Сколько дней живёт выданный токен QA')
ON CONFLICT (key) DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON kabinet_data.qa_tokens
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.qa_tokens_id_seq
    TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.qa_tokens
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";

COMMIT;

SELECT key, value, note FROM kabinet_data.reorder_params WHERE key LIKE 'qa_%' ORDER BY key;
