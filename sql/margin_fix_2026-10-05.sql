-- Маржа: четыре правки по сверке сентября с витриной Дарины (решение владельца 05.10.2026).
--
-- 1. Sponsored Products вычитаем ОДИН раз. Data Kiosk уже удерживает SP внутри net_proceeds_total:
--    на уровне SKU × день удержание сверх комиссий равно sp_spend до цента (медиана остатка 0,00 за
--    сентябрь, 1 144 строки с рекламой), а мы вычитали рекламу второй раз из ads_spend — 5 973 € за
--    сентябрь. В маржу из ads_spend теперь идут только SB и SD: их Amazon в выплате не удерживает.
-- 2. Возврат, годный к продаже, возвращает себестоимость в маржу; негодный остаётся расходом.
-- 3. LM и Carrefour получают себестоимость по той же цепочке, что Amazon.
-- 4. Wallapop и сайт в Кабинет не загружаются — сказано в паспорте.

-- ── приведение SKU по правилу Amazon (то же, что NORM_SQL/CLEAN_SQL в Economics Loader, ячейка 2) ──
-- Нужна в базе, чтобы искать себестоимость у строк, где SKU записан как есть (LM — shop_sku, возвраты —
-- seller SKU). Второе написание правила в Python разошлось бы с первым молча, поэтому оно одно.
CREATE OR REPLACE FUNCTION kabinet_data.amz_norm_sku(p text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH c AS (
        SELECT regexp_replace(regexp_replace(upper(btrim(coalesce(p, ''))),
                   '^(AMZN\.GR\.)?(S[0-9]*_)?', ''), '[-_ ]*(FBA|FBM)([-_].*)?$', '') AS x)
    SELECT CASE WHEN x ~ '^[0-9]{5,}'
                THEN lpad(substring(x from '^([0-9]{5,})'), 8, '0')
                     || coalesce(substring(x from '^[0-9]{5,}(-[A-Z0-9]{1,2})'), '')
                ELSE '' END
    FROM c
$$;
COMMENT ON FUNCTION kabinet_data.amz_norm_sku(text) IS
    'norm_sku по правилу Amazon (Economics Loader): префиксы S_/S2_/amzn.gr. и хвосты -FBA/-FBM срезаются, ядро до 8 знаков, вариант-суффикс до двух знаков сохраняется';
GRANT EXECUTE ON FUNCTION kabinet_data.amz_norm_sku(text) TO PUBLIC;

-- ── себестоимость за единицу по цепочке Amazon: одна таблица на все каналы ──
-- Пишет Economics Loader (ячейка 2) тем же расчётом, которым заполняет economics_summary.cogs у Amazon:
-- помесячная raw_amazon_cogs → cost Odoo там, где SKU нет; у набора — сумма по составу (BOM Odoo, иначе
-- каталог Amazon), NULL, если хоть у одного компонента цены нет. Читают загрузчики LM и Carrefour и вью
-- возвратов — иначе цепочка жила бы в четырёх копиях.
CREATE TABLE IF NOT EXISTS kabinet_data.sku_cogs_current (
    norm_sku    text PRIMARY KEY,
    cogs        numeric(12,4) NOT NULL,
    cogs_source text NOT NULL,
    calc_at     timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON kabinet_data.sku_cogs_current TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856";
GRANT SELECT, INSERT, UPDATE, DELETE ON kabinet_data.sku_cogs_current TO "v.tereshyn@dniprom.com";

-- ── реклама для маржи ──
CREATE OR REPLACE VIEW kabinet_data.v_ads_spend_margin AS
SELECT date, marketplace, norm_sku,
       sum(total_spend)                                       AS total_spend,
       sum(coalesce(sp_spend, 0))                             AS sp_in_proceeds,
       sum(coalesce(sb_spend, 0) + coalesce(sd_spend, 0))     AS margin_ads
FROM kabinet_data.ads_spend
GROUP BY 1, 2, 3;
COMMENT ON VIEW kabinet_data.v_ads_spend_margin IS
    'margin_ads — реклама, которую вычитаем из маржи (SB + SD); SP Amazon уже удержал внутри net_proceeds_total';
GRANT SELECT ON kabinet_data.v_ads_spend_margin TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- ── себестоимость, вернувшаяся с возвратом ──
-- Только FBA-возврат с диспозицией SELLABLE: товар вернулся на склад Amazon годным и будет продан снова.
-- CUSTOMER_DAMAGED, DEFECTIVE, CARRIER_DAMAGED и прочие — расход остаётся. У возвратов в Мадрид (MFN) и у
-- Mirakl состояния товара в данных нет вовсе (у MFN в disposition лежит тип возврата денег —
-- StandardRefund, AutomatedRefund), поэтому по ним себестоимость не возвращается: «годен» не доказано.
-- Дата — дата возврата: Data Kiosk относит возврат денег на неё же, а не на дату заказа.
CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
SELECT r.return_date::date                    AS return_date,
       r.marketplace,
       kabinet_data.amz_norm_sku(r.sku)       AS norm_sku,
       sum(r.quantity)::int                   AS sellable_units,
       max(c.cogs)                            AS unit_cogs,
       sum(r.quantity * c.cogs)               AS cogs_credit
FROM kabinet_data.raw_amazon_returns r
JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.amz_norm_sku(r.sku)
WHERE r.fulfillment_type = 'FBA' AND upper(r.disposition) = 'SELLABLE'
GROUP BY 1, 2, 3;
COMMENT ON VIEW kabinet_data.v_returns_cogs_credit IS
    'Себестоимость FBA-возвратов, годных к продаже (SELLABLE), — возвращается в маржу на дату возврата';
GRANT SELECT ON kabinet_data.v_returns_cogs_credit TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", "b1698364-6ec5-4240-8cd6-e06dd6e60856", "v.tereshyn@dniprom.com";

-- ── паспорт: каких каналов нет ──
UPDATE kabinet_data.data_source_origins
   SET note = concat_ws(' ', nullif(note, ''),
       'Каналы Wallapop и сайт в Кабинет не загружаются: в выручке и марже их нет (сентябрь 2026 — 369 € без НДС у Дарины).'),
       updated_at = now()
 WHERE table_name IN ('economics_summary', 'kabinet_data.economics_summary')
   AND coalesce(note, '') NOT LIKE '%Wallapop%';

-- ── ключ поиска себестоимости: сначала ПОЛНЫЙ код, потом приведённый ──
-- Найдено сверкой с Дариной в тот же день: правило Amazon срезает префикс набора S_/S2_/S3_…, и набор
-- «S2_99966000» искался как «99966000» — цена ОДНОГО инструмента (42,64 €) вместо двух (81,41 €). В цепочке
-- наборы лежат под своим полным кодом (ключи BOM чистятся только с хвоста, как _CL в Economics Loader),
-- поэтому сперва ищем полный код, очищенный тем же _CL, и только если его нет — приведённый.
CREATE OR REPLACE FUNCTION kabinet_data.sku_cogs_key(p text) RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    WITH c AS (
        SELECT regexp_replace(regexp_replace(regexp_replace(btrim(coalesce(p, '')), '[_-]+$', ''),
                   '(FBA|FBM)$', '', 'i'), '[_-]+$', '') AS x),
    k AS (SELECT CASE WHEN length(x) < 8 THEN lpad(x, 8, '0') ELSE x END AS exact FROM c)
    SELECT CASE WHEN EXISTS (SELECT 1 FROM kabinet_data.sku_cogs_current s WHERE s.norm_sku = k.exact)
                THEN k.exact ELSE kabinet_data.amz_norm_sku(p) END
    FROM k
$$;
COMMENT ON FUNCTION kabinet_data.sku_cogs_key(text) IS
    'Ключ в sku_cogs_current: полный код (набор S2_… — свой состав), если он есть в цепочке, иначе приведённый по правилу Amazon';
GRANT EXECUTE ON FUNCTION kabinet_data.sku_cogs_key(text) TO PUBLIC;

CREATE OR REPLACE VIEW kabinet_data.v_returns_cogs_credit AS
SELECT r.return_date::date                    AS return_date,
       r.marketplace,
       kabinet_data.amz_norm_sku(r.sku)       AS norm_sku,
       sum(r.quantity)::int                   AS sellable_units,
       max(c.cogs)                            AS unit_cogs,
       sum(r.quantity * c.cogs)               AS cogs_credit
FROM kabinet_data.raw_amazon_returns r
JOIN kabinet_data.sku_cogs_current c ON c.norm_sku = kabinet_data.sku_cogs_key(r.sku)
WHERE r.fulfillment_type = 'FBA' AND upper(r.disposition) = 'SELLABLE'
GROUP BY 1, 2, 3;
