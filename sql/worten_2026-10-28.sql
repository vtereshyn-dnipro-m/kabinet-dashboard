-- Worten Marketplace (Mirakl): сырьё, реплики для страниц, настройки, правила (28.10.2026, решение владельца: «подключи
-- Worten по API тем же путём, что TikTok»; docs/worten.md). Применяет владелец или агент по прямому «применяй», только
-- под учёткой владельца. Только добавляет: ничего не удаляет и ни у кого не отнимает.
-- Это Lakebase Кабинета; сырьё в Unity Catalog — sql/worten_uc_2026-10-28.sql (применяется первым). Часть B — до первого
-- прогона джобы, одной транзакцией: psql "<строка владельца>" -v sp=<Application ID> -v ON_ERROR_STOP=1 -1 -f …;
-- часть C — после создания джобы и её первого прогона, отдельно (нужен job_id; правило свежести до первого прогона дало бы
-- ложную тревогу): раскомментировать и выполнить psql "<строка владельца>" -v worten_job_id=<id> -v ON_ERROR_STOP=1 -1 -f …
-- (части B тогда закомментировать — она идемпотентна, но :"sp" без -v sp не подставится).
-- Application ID принципала в репозиторий не кладём (как у TikTok). claude-uc-ro для Worten не используется — как у
-- TikTok (решение владельца 22.10.2026): отступление от правила «гранты обоим принципалам» названо здесь.
--
-- Справочники (платформа Worten, маркетплейс WRT-PT) здесь НЕ заводятся: строка маркетплейса без данных сразу дала бы
-- «Worten — нет продаж» в блоке каналов «Обзора» и тревогу сторожа «маркетплейс без данных», а на «Обзор» Worten идёт
-- только после сверки с кабинетом Worten (решение владельца 28.10.2026). Справочники — в PR показа на «Площадках».
-- Принципал джобы — kabinet-jobs-sp; READ на скоуп worten выдан владельцем 28.10.2026.

-- ── Часть B. Lakebase (под владельцем, одной транзакцией) ──

CREATE TABLE IF NOT EXISTS kabinet_data.raw_worten_offers (
  shop_id text NOT NULL, offer_id text NOT NULL, shop_sku text, product_title text, category_code text, active boolean,
  quantity integer, channel_code text, price numeric(18,2), origin_price numeric(18,2), discount_price numeric(18,2),
  discount_start timestamptz, discount_end timestamptz, promo_active boolean, currency text,
  in_last_load boolean, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, offer_id));
COMMENT ON TABLE kabinet_data.raw_worten_offers IS 'Реплика dnipro_m.worten.raw_offers для страниц (пишет Kabinet - Worten Loader). in_last_load = false — оффера нет в последнем ответе API.';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_worten_orders (
  shop_id text NOT NULL, order_id text NOT NULL, order_state text, channel_code text,
  created_at timestamptz, updated_at timestamptz, created_at_utc timestamptz, updated_at_utc timestamptz, currency text, price numeric(18,2), shipping_price numeric(18,2), total_price numeric(18,2),
  total_commission numeric(18,2), country text, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, order_id));
COMMENT ON TABLE kabinet_data.raw_worten_orders IS 'Реплика dnipro_m.worten.raw_orders для страниц, без данных покупателя. created_at, updated_at — часы Мадрида как UTC (правило сырья Mirakl), *_utc — исходный момент.';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_worten_order_lines (
  shop_id text NOT NULL, order_line_id text NOT NULL, order_id text NOT NULL, order_line_state text, shop_sku text,
  product_title text, quantity integer, price_unit numeric(18,2), price numeric(18,2), total_price numeric(18,2),
  commission_fee numeric(18,2), tax_amount numeric(18,2), shipped_at timestamptz, shipped_at_utc timestamptz,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, order_line_id));
COMMENT ON TABLE kabinet_data.raw_worten_order_lines IS 'Реплика dnipro_m.worten.raw_order_lines для страниц.';

GRANT SELECT ON kabinet_data.raw_worten_offers, kabinet_data.raw_worten_orders, kabinet_data.raw_worten_order_lines
  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;
-- загрузчик пишет только INSERT … ON CONFLICT DO UPDATE: SELECT, INSERT, UPDATE; DELETE не нужен
GRANT SELECT, INSERT, UPDATE ON kabinet_data.raw_worten_offers, kabinet_data.raw_worten_orders,
  kabinet_data.raw_worten_order_lines TO :"sp";

INSERT INTO kabinet_data.reorder_params (key, value, note, updated_at) VALUES
 ('worten_shop_id', 18499, 'Worten: магазин Mirakl (shop_id) — DNIPRO-M, канал WRT_PT_ONLINE', now()),
 ('worten_history_days', 200, 'Worten: глубина первой загрузки заказов (сутки), как у TikTok (решение владельца 28.10.2026)', now()),
 ('worten_order_overlap_days', 3, 'Worten: перечитываем заказы по дате изменения с перекрытием (сутки) — статусы меняются задним числом', now()),
 ('worten_window_days', 30, 'Worten: длина куска запроса заказов (сутки)', now())
ON CONFLICT (key) DO NOTHING;


-- ── Часть C. Правило сторожа и правило свежести — ПОСЛЕ создания джобы и первого прогона ──
-- Свежесть — по loaded_at реплики офферов: он переносится из сырья (время снимка), а не ставится now() при записи
-- реплики, поэтому упавший OF21 виден как старение.
-- INSERT INTO kabinet_data.data_freshness_rules
--        (table_name, date_column, max_age_hours, content_date_column, max_content_age_hours,
--         source_type, owner_role, is_active, comment, updated_at) VALUES
--  ('kabinet_data.raw_worten_offers', 'loaded_at', 26, NULL, NULL, 'lakebase', NULL, true,
--   'Worten: офферы (реплика). По содержимому не проверяем — снимок целиком', now())
-- ON CONFLICT (table_name) DO NOTHING;
-- Имя = метка пульса = имя джобы (AGENTS.md, «Одно имя джоба в трёх местах»). Два прогона в сутки (07:20 и 15:20),
-- самый длинный промежуток 16 ч — порог 18 ч: тревога после первого же пропущенного прогона.
-- INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
-- VALUES (:worten_job_id, 'Kabinet - Worten Loader', 18, 'ежедневно 07:20, 15:20 Kyiv', true,
--         'Worten (Mirakl): офферы и заказы, реплика для страниц; run_as kabinet-jobs-sp')
-- ON CONFLICT (job_id) DO NOTHING;

-- Проверка чтением (после B):
-- SELECT has_table_privilege(:'sp', 'kabinet_data.raw_worten_offers', 'INSERT'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_worten_orders', 'UPDATE'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_worten_order_lines', 'DELETE');          -- t, t, f
-- SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'worten_%' ORDER BY key;   -- 4 строки
