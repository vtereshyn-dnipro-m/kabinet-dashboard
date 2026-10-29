-- Worten в Кабинете: справочники, отметка статуса данных, вью продаж для «Обзора», флаг строки (29.10.2026, PR3
-- из трёх; решение владельца: Worten — новый источник по API, как TikTok Shop, а не реплика Power BI; Power BI Кабинет
-- не ждёт; docs/worten.md). Применяет владелец или агент по прямому «применяй», ПОД УЧЁТКОЙ ВЛАДЕЛЬЦА (не через
-- claude_code_ro — правило AGENTS.md), в Lakebase Кабинета, одной транзакцией:
--   psql "<строка владельца>" -v ON_ERROR_STOP=1 -f sql/worten_page_2026-10-29.sql   (BEGIN/COMMIT — в самом файле)
-- Таблицы platforms и marketplaces_new — владельца; в platform_attributes и marketplace_attributes (принадлежат
-- claude_code_ro) у владельца есть INSERT. Вью статуса не меняется (раздел 2). Только добавляет: ничего не удаляет, ни у
-- кого не отнимает. Маркетплейс и его отметка — в одной транзакции: WRT-PT без отметки сторож увидел бы как no_data.
--
-- Порядок: SQL — ПЕРЕД выкладкой (мержем) кода. Код без SQL безопасен: вью нет — строки Worten на «Обзоре» нет, вкладка
-- «Площадок» читает реплики, которые уже есть. SQL без кода тоже безопасен: флаг 0, страниц, читающих вью, ещё нет.
-- Plan Matrix в эти справочники не смотрит: вкладки таблицы — список TABS в nb/plan_matrix_prices.py, Worten там нет,
-- и в табы аналитика витрины ничего не пишется.

BEGIN;

-- ── 1. Справочники ──
-- Площадка: короткое имя WRT (как у Mirakl-кодов LM, CF), полное — Worten. Маркетплейс WRT-PT: Португалия, евро, НДС 23 %
-- (стандартная ставка; пониженные на наших категориях не проверены — docs/worten.md, «Деньги»). legacy_code wrt_pt — как
-- tts_es у TikTok; sync_* и monitor_listings — false (это флаги загрузчиков Amazon).
INSERT INTO kabinet_data.platforms (short_name, full_name) VALUES ('WRT', 'Worten')
ON CONFLICT (short_name) DO NOTHING;

INSERT INTO kabinet_data.platform_attributes (platform_id, is_active, comment, updated_by)
SELECT id, true, 'Worten (Mirakl), Португалия: данные — Worten API, не Power BI', 'migration:worten_page'
  FROM kabinet_data.platforms WHERE short_name = 'WRT'
ON CONFLICT (platform_id) DO NOTHING;

INSERT INTO kabinet_data.marketplaces_new (code, platform_short, country_alpha2, name, currency, vat_rate, is_active,
                                           legacy_code)
VALUES ('WRT-PT', 'WRT', 'PT', 'Worten Portugal', 'EUR', 0.23, true, 'wrt_pt')
ON CONFLICT (code) DO NOTHING;

-- ── 2. Статус данных маркетплейса: отметка «загрузчика во вью статуса нет» — как у TTS-ES ──
-- v_marketplace_data_status смотрит данные только по своему списку источников, Worten в нём нет: без отметки WRT-PT сразу
-- стал бы no_data, и сторож завёл бы marketplace_no_data ([MPDATA:WRT-PT]) в 13:00. Добавить источники Worten в вью
-- владелец не может: вью принадлежит claude_code_ro, а учётка владельца состоит в этой роли без INHERIT и SET (то же, что
-- в sql/kabinet_jobs_sp_2026-10-22_ro.sql), писать через claude_code_ro нельзя (решение владельца 26.10.2026). Поэтому —
-- как у TTS-ES (sql/watchdog_weekly_digest_2026-10-11.sql): no_loader_since, статус no_loader, сторож не тревожит. Живость
-- загрузчика Worten и свежесть его данных проверяют правило сторожа «Kabinet - Worten Loader» (18 ч) и правило свежести
-- raw_worten_offers (26 ч) — sql/worten_rules_2026-10-28.sql. INSERT в marketplace_attributes у владельца есть.
INSERT INTO kabinet_data.marketplace_attributes (marketplace_id, no_loader_since, no_loader_note, updated_at, updated_by)
SELECT id, DATE '2026-10-29',
       'Данные Worten — Worten API (Kabinet - Worten Loader); во вью статуса источников Worten нет, живость загрузчика и '
       'свежесть данных проверяют его правило сторожа и правило свежести.', now(), 'migration:worten_page'
  FROM kabinet_data.marketplaces_new WHERE code = 'WRT-PT'
ON CONFLICT (marketplace_id) DO NOTHING;

-- ── 3. Продажи Worten по дням для «Обзора» ──
-- Как у Leroy Merlin в v_sales_vat_incl_daily: сумма строк заказа (цена без доставки), без строк REFUNDED, CANCELED,
-- REFUSED. День заказа — по Лиссабону: created_at в реплике — часы Лиссабона, записанные как UTC (решение владельца
-- 28.10.2026), поэтому дата берётся явно AT TIME ZONE 'UTC', а не от пояса сессии. Без НДС — делением на ставку
-- маркетплейса, как у TikTok.
CREATE OR REPLACE VIEW kabinet_data.v_worten_sales_daily AS
SELECT (o.created_at AT TIME ZONE 'UTC')::date AS date,
       m.code AS marketplace,
       p.full_name AS channel,
       c.name AS country,
       count(DISTINCT o.order_id) AS orders,
       sum(l.price)::double precision AS sales_vat_incl,
       (sum(l.price) / (1 + m.vat_rate))::double precision AS sales_vat_excl
  FROM kabinet_data.raw_worten_order_lines l
  JOIN kabinet_data.raw_worten_orders o ON o.shop_id = l.shop_id AND o.order_id = l.order_id
  JOIN kabinet_data.marketplaces_new m ON m.code = 'WRT-PT'
  JOIN kabinet_data.platforms p ON p.short_name = m.platform_short
  JOIN kabinet_data.countries c ON c.alpha2 = m.country_alpha2
 WHERE l.order_line_state <> ALL (ARRAY['REFUNDED', 'CANCELED', 'REFUSED'])   -- строка без статуса — не продажа, как у LM
 GROUP BY 1, m.code, p.full_name, c.name, m.vat_rate;
COMMENT ON VIEW kabinet_data.v_worten_sales_daily IS
  'Worten по дням для «Обзора»: Worten API (Mirakl), не Power BI. Строки заказов без отмен, отказов, возвратов; день — по Лиссабону.';

-- Гранты: приложению — SELECT; claude_code_ro — SELECT (проверки страниц). Джобам не выдаём — ни одна джоба вью не
-- читает, а claude-uc-ro для Worten не используется (как у TikTok, решение владельца 22.10.2026): отступление от правила
-- «гранты обоим принципалам» названо здесь.
GRANT SELECT ON kabinet_data.v_worten_sales_daily TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;

-- ── 4. Флаг строки Worten на «Обзоре» ──
-- 0 до сверки заказов с кабинетом Worten (как tiktok_overview_enabled); включает владелец. Администратор видит строку и
-- при 0. Вкладка «Площадок» — без флага (ответ владельца на аудит 28.10.2026).
INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('worten_overview_enabled', 0, 'Worten в «Обзоре» (каналы и страны): 1 — показывать всем, 0 — только администратору. Включает владелец после сверки заказов с кабинетом Worten', now())
ON CONFLICT (key) DO NOTHING;

COMMIT;

-- Проверка чтением (после применения):
-- SELECT code, status, no_loader_note FROM kabinet_data.v_marketplace_data_status WHERE code IN ('WRT-PT', 'TTS-ES');
--   оба no_loader; у остальных маркетплейсов статус как до применения
-- SELECT * FROM kabinet_data.v_worten_sales_daily ORDER BY date DESC LIMIT 5;   -- 21.10.2026 · WRT-PT · 65,99 с НДС
-- SELECT key, value FROM kabinet_data.reorder_params WHERE key = 'worten_overview_enabled';   -- 0
