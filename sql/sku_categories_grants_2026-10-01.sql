-- Гранты принципалу ДЖОБ: загрузчик справочника SKU идёт под ним и пишет дерево и связи.
-- Та же ошибка, что уже записана в AGENTS.md про buybox_status: таблицу создала роль
-- Кабинета, выдал я только приложению, а пишет джоба — «permission denied» на первом
-- же прогоне. Гранты новой таблице нужны СРАЗУ и обоим, если пишут оба.
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_category_tree
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_category_links
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE ON kabinet_data.category_names
    TO "b1698364-6ec5-4240-8cd6-e06dd6e60856";
