-- Окно маржи для порога ACOS кампаний (читает v_amc_attribution). Выполняет claude_code_rw.
INSERT INTO kabinet_data.reorder_params (key, value, note)
VALUES ('ads_margin_window_days', '90',
        'Порог ACOS кампании = маржа до рекламы товаров кампании за N дней на рынке инстанса AMC (ES): (net_proceeds − COGS − упаковка/доставка) / продажи с НДС. Читает вью v_amc_attribution')
ON CONFLICT (key) DO NOTHING;
SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'ads_margin_window_days';
