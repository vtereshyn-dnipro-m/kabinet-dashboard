-- 21.09.2026. ТЗ 006 §11: у группы вариаций своя история — название, URL, признак семьи, активность, создание.
-- До этого журнал был только у связи «PeID → группа» (product_entity_change_log); правки самой группы терялись.
CREATE TABLE IF NOT EXISTS kabinet_data.variation_group_change_log (
    id          BIGSERIAL PRIMARY KEY,
    group_id    INT NOT NULL REFERENCES kabinet_data.variation_groups(id),
    field       TEXT NOT NULL,            -- created | name | url | is_family | is_active | comment | group_peid
    old_value   TEXT,
    new_value   TEXT,
    source      TEXT NOT NULL DEFAULT 'manual',
    actor       TEXT NOT NULL DEFAULT 'kabinet',
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS variation_group_change_log_group_idx ON kabinet_data.variation_group_change_log (group_id, changed_at DESC);
COMMENT ON TABLE kabinet_data.variation_group_change_log IS 'ТЗ 006 §11: история изменений группы вариаций; деактивация закрывает связи вариантов и роли — это тоже здесь.';
GRANT SELECT ON kabinet_data.variation_group_change_log TO claude_code_ro;
GRANT SELECT, INSERT ON kabinet_data.variation_group_change_log TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT USAGE ON SEQUENCE kabinet_data.variation_group_change_log_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
-- создание групп с экрана — приложению нужен INSERT в сам справочник и правка сущностей/представлений при деактивации
GRANT INSERT ON kabinet_data.variation_groups TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT USAGE ON SEQUENCE kabinet_data.variation_groups_id_seq TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
SELECT has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.variation_groups', 'INSERT') ins_vg,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.product_entities', 'UPDATE') upd_pe,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.assortment_representations', 'UPDATE') upd_ar,
       has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.assortment_change_log', 'INSERT') ins_acl;
