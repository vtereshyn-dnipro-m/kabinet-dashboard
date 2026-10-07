-- Журнал справочника «Подпитка» (07.10.2026): кто, когда и что поменял в связи «склад-источник → склад-получатель».
-- Своя таблица: `supply_chains` принадлежит владельцу базы, колонок туда роль Кабинета не добавит. Плановый срок
-- поставки (`median_days`) правит только человек (ТЗ 001 §5) и читают автозаказ и переброска, поэтому без журнала
-- нельзя было ответить, кто и когда поменял срок, по которому считается заказ.
-- Пишут две точки правки: раздел «Подпитка» и карточка склада-получателя.
CREATE TABLE IF NOT EXISTS kabinet_data.supply_chain_change_log (
    id        bigserial   PRIMARY KEY,
    chain_id  integer     NOT NULL,
    field     text        NOT NULL,   -- created / median_days / route_type / note / is_active / deleted
    old_value text,
    new_value text,
    actor     text        NOT NULL,
    ts        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS supply_chain_change_log_chain_idx ON kabinet_data.supply_chain_change_log (chain_id, ts DESC);

-- приложение пишет журнал, принципал джоб читает
GRANT SELECT, INSERT ON kabinet_data.supply_chain_change_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE, SELECT ON SEQUENCE kabinet_data.supply_chain_change_log_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.supply_chain_change_log TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
