-- Паспорт «Обзора»: строка «Возвраты» (05.10.2026, решение владельца). Правило — по факту, а не по допущению:
-- себестоимость возвращается в маржу, только если товар годен — FBA по оценке Amazon (SELLABLE), Мадрид (Amazon MFN
-- и Mirakl) — по приёмке Odoo в годный запас WH-1. Допущение «90 % годных» не внедрено до проверки того, как
-- работает локация брака DEF/WH-1.
INSERT INTO kabinet_data.data_source_origins
    (table_name, platform_source, platform_refresh, our_refresh, verdict, note, darina_method, darina_verdict, darina_reason)
VALUES ('kabinet_data.v_returns_cogs_credit',
        'Amazon: отчёт возвратов FBA (состояние товара SELLABLE / брак); Odoo: приёмка возврата покупателя на склад Мадрид (локация WH-1 — годный запас, DEF/WH-1 — брак, W-SPR — ремонт)',
        'Amazon — суточно; Odoo — в момент приёмки на складе',
        'Kabinet - Returns Loader 06:00 и Kabinet - Odoo Customer Returns 08:15 Kyiv', 'ok',
        'Себестоимость возвращается в маржу только с годных возвратов: FBA — по оценке Amazon, Мадрид — если Odoo принял товар в годный запас. Принятое в брак или в ремонт остаётся расходом. В сентябре 2026 годных 10 шт на 146 € (9 FBA и 1 в Мадриде).',
        'возвращает себестоимость со ВСЕХ возвращённых штук (cogs_refund в v_amazon_spiderweb_report и v_lm_spiderweb_report), без учёта состояния товара',
        'different',
        'у неё в маржу возвращается себестоимость любого возврата, у нас — только годного по факту (Amazon или приёмка Odoo); сентябрь — 1 718 € у неё против 146 € у нас')
ON CONFLICT (table_name) DO UPDATE SET platform_source = EXCLUDED.platform_source, platform_refresh = EXCLUDED.platform_refresh,
    our_refresh = EXCLUDED.our_refresh, verdict = EXCLUDED.verdict, note = EXCLUDED.note,
    darina_method = EXCLUDED.darina_method, darina_verdict = EXCLUDED.darina_verdict,
    darina_reason = EXCLUDED.darina_reason, updated_at = now();
