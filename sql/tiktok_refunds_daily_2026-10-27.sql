-- TikTok Shop: возвраты по дням для «Обзора» (27.10.2026, решение владельца): «Продажи + возвраты + после возвратов» по
-- всем каналам; у TikTok возврат — только фактически возвращённые деньги, по дате выписки возврата (Мадрид), как на
-- вкладке TikTok с 23.10.2026; та же конвенция, что у Power BI для Amazon (по дате расчёта). Заявки на возврат
-- (dnipro_m.tiktok.raw_returns) из выручки не вычитаются. Возврат без даты выписки — по дате заказа (как на вкладке).
-- Применяет владелец или агент по прямому «применяй», под учёткой владельца. Только добавляет: новое вью и SELECT на него.
-- revenue_amount возврата — минус выручка продавца с НДС по заказу (проверено 27.10.2026: −74,99 и −59,95 при выручке
-- 74,99 и 59,95); без НДС — делением на ставку из marketplaces_new, как у v_tiktok_sales_daily. Знак — плюс (сумма
-- возвратов), минус ставит страница.
BEGIN;

CREATE OR REPLACE VIEW kabinet_data.v_tiktok_refunds_daily AS
SELECT coalesce((x.statement_time AT TIME ZONE 'Europe/Madrid')::date,
                (o.create_time AT TIME ZONE 'Europe/Madrid')::date) AS date,
       m.code AS marketplace, p.full_name AS channel, c.name AS country,
       count(DISTINCT x.order_id) AS refunds,
       (-sum(x.revenue_amount))::double precision AS refund_vat_incl,
       (-sum(x.revenue_amount) / (1 + m.vat_rate))::double precision AS refund_vat_excl
FROM kabinet_data.raw_tiktok_finance_tx x
JOIN kabinet_data.raw_tiktok_orders o ON o.order_id = x.order_id AND o.shop_id = x.shop_id
JOIN kabinet_data.marketplaces_new m ON m.code = 'TTS-' || o.region
JOIN kabinet_data.platforms p ON p.short_name = m.platform_short
JOIN kabinet_data.countries c ON c.alpha2 = m.country_alpha2
WHERE x.revenue_amount < 0 AND coalesce(o.status, '') <> 'CANCELLED' AND NOT coalesce(o.is_sample_order, false)
GROUP BY 1, 2, 3, 4, m.vat_rate;
COMMENT ON VIEW kabinet_data.v_tiktok_refunds_daily IS 'TikTok Shop: возвраты (деньги по выпискам) по дням выписки возврата (Мадрид), с НДС и без, со знаком плюс — для «Обзора». Источник — TikTok Shop API, не Power BI.';

GRANT SELECT ON kabinet_data.v_tiktok_refunds_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;

COMMIT;
