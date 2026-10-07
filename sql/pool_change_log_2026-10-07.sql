-- Журнал справочника «Пулы» (07.10.2026): кто, когда и что поменял в пуле и в его связях.
-- Своя таблица: `pools` и `pool_members` принадлежат владельцу базы, колонок туда роль Кабинета не добавит,
-- а без журнала правка дат участия (ТЗ 004 §4, §6) неотличима от исходной записи.
CREATE TABLE IF NOT EXISTS kabinet_data.pool_change_log (
    id           bigserial   PRIMARY KEY,
    pool_id      integer     NOT NULL,
    link_id      integer,                 -- связь «пул → маркетплейс», если правка про неё
    action       text        NOT NULL,    -- create / rename / comment / link_add / link_dates / link_close / pool_close / delete
    before_state jsonb,
    after_state  jsonb,
    actor        text        NOT NULL,
    ts           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pool_change_log_pool_idx ON kabinet_data.pool_change_log (pool_id, ts DESC);

-- приложение пишет журнал, принципал джоб читает
GRANT SELECT, INSERT ON kabinet_data.pool_change_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.pool_change_log_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.pool_change_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
