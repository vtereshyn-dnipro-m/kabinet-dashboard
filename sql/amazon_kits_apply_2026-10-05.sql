-- Наборы S…_ у Amazon — применение (решение владельца 05.10.2026). Ключ economics_summary / ads_spend /
-- economics_logistics теперь сохраняет префикс набора (Economics Loader, ячейки 2, 3, 11); копии «до» —
-- *_before_kits_20261005. Вью возвратов приводится к тому же ключу: возврат набора ложится на строку
-- набора, а не одиночного товара. sku_cogs_key даёт ровно ключ экономики: полный код, если он есть в
-- цепочке (набор, вариант), иначе приведённый.
CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
SELECT r.return_date::date                    AS return_date,
       r.marketplace,
       kabinet_data.sku_cogs_key(r.sku)       AS norm_sku,
       sum(r.quantity)::int                   AS sellable_units,
       max(c.cogs)                            AS unit_cogs,
       sum(r.quantity * c.cogs)               AS cogs_credit
FROM kabinet_data.raw_amazon_returns r
JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.sku_cogs_key(r.sku)
WHERE r.fulfillment_type = 'FBA' AND upper(r.disposition) = 'SELLABLE'
GROUP BY 1, 2, 3;
