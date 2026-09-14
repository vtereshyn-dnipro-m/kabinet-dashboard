-- Единый состав: SKU → компонент × количество. Lakebase, kabinet_data.
--
-- Два источника, приоритет у Odoo: там BOM ведётся, а амазоновский каталог
-- его переписывает под SKU витрины. Odoo-набор берётся целиком; амазоновский
-- SKU добавляется только если такого родителя в Odoo нет. Моно-товар — это
-- состав из самого себя ×1: так зависимая потребность считается одной
-- формулой и для наборов, и для простых позиций.
--
-- source говорит, откуда строка: odoo_kit, odoo_mono, amazon_catalog.
-- Родитель без единого компонента ни в одном источнике сюда не попадает —
-- его ищет проверка покрытия ниже.

CREATE OR REPLACE VIEW kabinet_data.v_sku_composition AS
WITH odoo AS (
    SELECT parent_sku, child_sku, quantity,
           CASE WHEN custom_type = 'website_kit' THEN 'odoo_kit' ELSE 'odoo_mono' END AS source
    FROM kabinet_data.raw_odoo_sku_mapping
    WHERE type IN ('product', 'consu') AND quantity > 0
),
amazon AS (
    SELECT c.parent_sku, c.child_sku, c.units AS quantity, 'amazon_catalog' AS source
    FROM kabinet_data.raw_amazon_sku_catalog c
    WHERE c.units > 0
      AND NOT EXISTS (SELECT 1 FROM odoo o WHERE o.parent_sku = c.parent_sku)
)
SELECT parent_sku, child_sku, quantity, source FROM odoo
UNION ALL
SELECT parent_sku, child_sku, quantity, source FROM amazon;

COMMENT ON VIEW kabinet_data.v_sku_composition IS
    'SKU → компонент × количество из Odoo (приоритет) и амазоновского каталога. Моно — сам в себя ×1.';
GRANT SELECT ON kabinet_data.v_sku_composition TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb";
GRANT SELECT ON kabinet_data.v_sku_composition TO claude_code_ro;

SELECT source, count(*) AS strok, count(DISTINCT parent_sku) AS roditeley FROM kabinet_data.v_sku_composition GROUP BY 1 ORDER BY 1;
