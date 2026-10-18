-- Вью «текущих» транзакций Amazon (Finances v2024-06-19), решение владельца 18.10.2026. Unity Catalog, не Lakebase:
-- выполнять ПОСЛЕ мержа ноутбуком (spark.sql), MCP-запрос CREATE не пропускает.
--
-- Зачем. В raw_amazon_finances_transactions одна продажа лежит ДВАЖДЫ: отложенной транзакцией (DEFERRED_RELEASED,
-- со ссылкой release_transaction_id) и выплатой (RELEASED, со ссылкой deferred_transaction_id) с той же разбивкой.
-- Сумма «всего подряд» удваивается: digital-сбор ES за август 2026 выходил 506 € вместо 241 €.
-- Правило: выплаты (RELEASED) + ещё не выплаченные (DEFERRED) + отложенные, на которые выплаты в таблице нет
-- (DEFERRED_RELEASED без RELEASED со ссылкой на неё). Последнее — не страховка «на всякий случай»: 423 продажи
-- ноября 2024 — марта 2025 Amazon отдаёт только отложенной транзакцией, отдельной выплаты по ним нет вовсе.
-- Проверено 18.10.2026: ES август — 811 заказов, 40 334,16 €; сентябрь — 702 заказа, 41 592,68 € (+5 невыплаченных) —
-- с settlement-отчётом заказ в заказ и до цента. Дата — posted_date транзакции: у выплаты это дата выплаты, у
-- невыплаченной — дата заказа.
CREATE OR REPLACE VIEW dnipro_m.dnipro_m.v_amazon_finances_transactions_current
COMMENT 'Транзакции Amazon без задвоения: выплаты + невыплаченные + отложенные без выплаты. Правило — AGENTS.md, «Finances, промо и добор экономики».'
AS
WITH rel AS (
    SELECT DISTINCT deferred_transaction_id AS id
    FROM dnipro_m.dnipro_m.raw_amazon_finances_transactions
    WHERE transaction_status = 'RELEASED' AND deferred_transaction_id IS NOT NULL
)
SELECT t.*
FROM dnipro_m.dnipro_m.raw_amazon_finances_transactions t
LEFT ANTI JOIN rel ON rel.id = t.transaction_id AND t.transaction_status = 'DEFERRED_RELEASED'
WHERE t.transaction_status IN ('RELEASED', 'DEFERRED', 'DEFERRED_RELEASED');

CREATE OR REPLACE VIEW dnipro_m.dnipro_m.v_amazon_finances_breakdowns_current
COMMENT 'Разбивка сумм только по транзакциям из v_amazon_finances_transactions_current. Внутри одной транзакции суммы вложены: путь X и X/Y повторяют одни деньги — складывать один уровень (лист is_leaf = Y или конкретный путь).'
AS
SELECT b.*
FROM dnipro_m.dnipro_m.raw_amazon_finances_breakdowns b
LEFT SEMI JOIN dnipro_m.dnipro_m.v_amazon_finances_transactions_current c ON c.transaction_id = b.transaction_id;
