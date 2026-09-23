-- Журнал действий по рекламе из Кабинета (кнопки «Пауза» и «Снизить ставку» на странице «Реклама»).
-- Пишется только по нажатию человека: расписаний и фоновых прогонов у этих действий нет.
-- before_state хранит прежнее состояние целиком (состояние кампании и ставки всех её групп) —
-- это и есть материал отката: без него «вернуть как было» возможно лишь по памяти человека.
CREATE TABLE IF NOT EXISTS kabinet_data.ads_actions (
    id            bigserial PRIMARY KEY,
    created_at    timestamptz NOT NULL DEFAULT now(),
    actor         text NOT NULL,                 -- st.user.email, если Streamlit его отдаёт, иначе kabinet-app
    profile_id    text NOT NULL,                 -- рекламный профиль Amazon (ES)
    ad_product    text NOT NULL CHECK (ad_product IN ('sponsored_products', 'sponsored_brands', 'sponsored_display')),
    campaign_id   text NOT NULL,
    campaign_name text,
    action        text NOT NULL CHECK (action IN ('pause', 'resume', 'bid_down', 'rollback')),
    params        jsonb,                         -- {"pct": 20} у снижения ставки
    before_state  jsonb NOT NULL,                -- {"campaign_state": "...", "ad_groups": [{"adGroupId": "...", "defaultBid": 0.30}]}
    after_state   jsonb,
    api_status    text NOT NULL,                 -- ok | partial | error
    api_response  jsonb,
    rollback_of   bigint REFERENCES kabinet_data.ads_actions(id),
    rolled_back_at timestamptz,
    note          text
);
CREATE INDEX IF NOT EXISTS ads_actions_campaign_idx ON kabinet_data.ads_actions (campaign_id, created_at DESC);
COMMENT ON TABLE kabinet_data.ads_actions IS 'Действия по рекламе из Кабинета: кто, когда, что было, что стало; источник отката. Только по нажатию.';

GRANT SELECT ON kabinet_data.ads_actions TO claude_code_ro, "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.ads_actions TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.ads_actions_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";

-- Шаг снижения ставки — настройка, не константа в коде
INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('ads_bid_down_pct', '20', 'Шаг кнопки «Снизить ставку» на странице «Реклама», % от текущей defaultBid группы'),
       ('ads_bid_min', '0.02', 'Минимальная ставка Amazon Ads, € — ниже неё кнопка не опускает')
ON CONFLICT (key) DO NOTHING;

SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'ads_%' ORDER BY 1;
