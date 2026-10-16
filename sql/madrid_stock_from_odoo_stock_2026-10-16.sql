-- Мадрид из raw_odoo_stock вместо raw_odoo_madrid_stock (16.10.2026, решение владельца).
-- Аналитик убрал из ноутбука «Odoo Stock for Tableau» ячейку, писавшую raw_odoo_madrid_stock (последняя запись 12.10.2026);
-- тот же склад «RS Spain Madrid (Stock)» есть в raw_odoo_stock, которую та же джоба пишет ежедневно (12.10 построчно равны).
-- Coverage Projection и Stock Loader переведены патчами nb/patches/2026-10-16_madrid_from_odoo_stock_*.diff.
-- Правило свежести старой таблицы выключаем: сторож закроет её инцидент stale_data сам (правило выключено, токен — имя таблицы),
-- а из списка RULES сторожа оно убрано тем же патчем, чтобы seed его не вернул (seed is_active не трогает).
-- Выполнять после мержа PR, после выкладки ноутбуков.
UPDATE kabinet_data.data_freshness_rules
   SET is_active = false, updated_at = now(),
       comment = 'Выключено 16.10.2026: таблицу перестали писать после 12.10; Мадрид читаем из raw_odoo_stock (склад RS Spain Madrid (Stock))'
 WHERE table_name = 'dnipro_m.dnipro_m.raw_odoo_madrid_stock';
SELECT table_name, is_active, comment FROM kabinet_data.data_freshness_rules WHERE table_name LIKE '%odoo%stock%';
