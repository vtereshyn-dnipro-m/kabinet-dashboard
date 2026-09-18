-- 18.09.2026: внешние ключи между справочниками. Часть 1 — таблицы, которыми владеет роль Кабинета
-- (выполнено от rw). Часть 2 — то, что может выдать только владелец схемы (см. комментарий внизу).
BEGIN;
ALTER TABLE kabinet_data.product_entity_listings
    ADD CONSTRAINT product_entity_listings_entity_fk FOREIGN KEY (marketplace_id, peid)
    REFERENCES kabinet_data.product_entities (marketplace_id, peid);
ALTER TABLE kabinet_data.product_entity_checks
    ADD CONSTRAINT product_entity_checks_entity_fk FOREIGN KEY (marketplace_id, peid)
    REFERENCES kabinet_data.product_entities (marketplace_id, peid) ON DELETE CASCADE;
ALTER TABLE kabinet_data.variation_group_checks
    ADD CONSTRAINT variation_group_checks_group_fk FOREIGN KEY (group_id)
    REFERENCES kabinet_data.variation_groups (id) ON DELETE CASCADE;
ALTER TABLE kabinet_data.sku_checks
    ADD CONSTRAINT sku_checks_sku_fk FOREIGN KEY (sku) REFERENCES kabinet_data.sku_master (sku) ON DELETE CASCADE;
ALTER TABLE kabinet_data.assortment_representations
    ADD CONSTRAINT assortment_repr_entity_fk FOREIGN KEY (marketplace_id, peid)
    REFERENCES kabinet_data.product_entities (marketplace_id, peid);
ALTER TABLE kabinet_data.sku_target_status
    ADD CONSTRAINT sku_target_status_sku_fk FOREIGN KEY (sku) REFERENCES kabinet_data.sku_master (sku);
COMMIT;

-- ЧАСТЬ 2 — от владельца (v.tereshyn@dniprom.com). Проверено 18.09.2026: сирот нет, ключи встанут без ошибок.
-- 2a. Разрешить роли Кабинета ссылаться на справочники владельца (после этого rw сам поставит FK
--     product_entities / product_entity_listings / variation_groups / assortment_* → marketplaces_new):
--   GRANT REFERENCES ON kabinet_data.marketplaces_new, kabinet_data.warehouses, kabinet_data.pools TO claude_code_ro, claude_code_rw;
-- 2b. Ключи на таблицах владельца:
--   ALTER TABLE kabinet_data.warehouses ADD CONSTRAINT warehouses_canonical_fk
--       FOREIGN KEY (canonical_id) REFERENCES kabinet_data.warehouses (id);
--   ALTER TABLE kabinet_data.coverage_norms ADD CONSTRAINT coverage_norms_sku_fk
--       FOREIGN KEY (sku) REFERENCES kabinet_data.sku_master (sku);
-- 2c. Связи склад ↔ площадки (таблица наша, ссылки — на владельца; после 2a выполним сами):
--   ALTER TABLE kabinet_data.warehouse_marketplaces ADD FOREIGN KEY (warehouse_id) REFERENCES kabinet_data.warehouses (id);
--   ALTER TABLE kabinet_data.warehouse_marketplaces ADD FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
-- НЕ ставим намеренно: sku_lifecycle.sku (51 SKU вне периметра справочника — факт продаж шире),
-- reorder_recommendations.sku (6 базовых кодов сегодня вне справочника, загрузчик пишет раньше проверки),
-- forecast_register.sku (82 SKU листа планов нигде не выставлены — это вопрос к плану, не к ключу),
-- forecast_* и forecast_alert_rules по (object_type, object_id) — полиморфная ссылка, FK не выражается.
