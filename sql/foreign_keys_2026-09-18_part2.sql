-- 18.09.2026, часть 2: владелец выдал GRANT REFERENCES на marketplaces_new / warehouses / pools —
-- ставим ключи наших таблиц на справочники владельца. Сироты проверены перед выполнением: 0.
BEGIN;
ALTER TABLE kabinet_data.product_entities        ADD CONSTRAINT product_entities_mp_fk        FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
ALTER TABLE kabinet_data.product_entity_listings ADD CONSTRAINT product_entity_listings_mp_fk FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
ALTER TABLE kabinet_data.variation_groups        ADD CONSTRAINT variation_groups_mp_fk        FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
ALTER TABLE kabinet_data.assortment_admissions   ADD CONSTRAINT assortment_admissions_mp_fk   FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
ALTER TABLE kabinet_data.assortment_representations ADD CONSTRAINT assortment_repr_mp_fk      FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
ALTER TABLE kabinet_data.warehouse_marketplaces  ADD CONSTRAINT warehouse_marketplaces_wh_fk  FOREIGN KEY (warehouse_id)   REFERENCES kabinet_data.warehouses (id);
ALTER TABLE kabinet_data.warehouse_marketplaces  ADD CONSTRAINT warehouse_marketplaces_mp_fk  FOREIGN KEY (marketplace_id) REFERENCES kabinet_data.marketplaces_new (id);
COMMIT;
SELECT c.conrelid::regclass AS child, c.conname, c.confrelid::regclass AS parent
FROM pg_constraint c WHERE c.contype = 'f' AND c.connamespace = 'kabinet_data'::regnamespace
  AND c.conname IN ('product_entities_mp_fk','product_entity_listings_mp_fk','variation_groups_mp_fk','assortment_admissions_mp_fk',
                    'assortment_repr_mp_fk','warehouse_marketplaces_wh_fk','warehouse_marketplaces_mp_fk','warehouses_canonical_fk','coverage_norms_sku_fk')
ORDER BY 1, 2;
