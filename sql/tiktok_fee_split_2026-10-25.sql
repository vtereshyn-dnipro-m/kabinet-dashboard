-- Раскладка комиссий TikTok по колонкам (решение владельца 25.10.2026): три колонки в реплике операций выписок.
-- Пишет Kabinet - TikTok Shop Loader (nb/tiktok_loader.py, FEE_SPLIT) из fee_tax_breakdown в raw_json сырья
-- dnipro_m.tiktok.raw_finance_statement_transactions; в сумме три колонки = fee_tax_amount. Колонки добавляются пустыми —
-- до первого прогона загрузчика после выкладки вкладка показывает комиссии одной колонкой, как раньше.
-- Порядок: этот SQL (применяет владелец) → мерж PR → выкладка ноутбука → ручной прогон загрузчика.
-- Права — на таблицу целиком, новые колонки их наследуют; отдельных GRANT не нужно.
ALTER TABLE kabinet_data.raw_tiktok_finance_tx
  ADD COLUMN IF NOT EXISTS commission_tiktok numeric(18,2),
  ADD COLUMN IF NOT EXISTS commission_affiliate numeric(18,2),
  ADD COLUMN IF NOT EXISTS fee_other numeric(18,2);
COMMENT ON COLUMN kabinet_data.raw_tiktok_finance_tx.commission_tiktok IS 'Комиссия TikTok: fee_tax_breakdown.fee.platform_commission_amount (с минусом — удержание, с плюсом — возврат).';
COMMENT ON COLUMN kabinet_data.raw_tiktok_finance_tx.commission_affiliate IS 'Комиссия аффилиатов: affiliate_commission_amount + affiliate_ads_commission_amount + affiliate_partner_commission_amount.';
COMMENT ON COLUMN kabinet_data.raw_tiktok_finance_tx.fee_other IS 'Прочие сборы: fee_tax_amount минус комиссии TikTok и аффилиатов (на 25.10.2026 — Smart Promotion и EPR).';

-- Проверка после прогона загрузчика (только чтение): расхождений с fee_tax_amount — 0, пустых — 0
-- SELECT count(*) FILTER (WHERE commission_tiktok + commission_affiliate + fee_other <> fee_tax_amount) AS mismatch,
--        count(*) FILTER (WHERE commission_tiktok IS NULL) AS empty, count(*) AS total
-- FROM kabinet_data.raw_tiktok_finance_tx;
