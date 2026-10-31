-- TikTok Shop: реплики заявок на возврат и отмен в Lakebase для вкладки «TikTok Shop» (27.10.2026, решение владельца:
-- «заявки остаются видны на вкладке TikTok как операционная картина»; в выручку «Обзора» они не входят — там возвраты по
-- выпискам). Реплику пишет `Kabinet - TikTok Shop Loader` из dnipro_m.tiktok.raw_returns / raw_cancellations (#393),
-- upsert по ключу, только колонки страницы, без raw_json. Адреса склада возврата, трек-номера, перевозчика, доли
-- покупателя за доставку и картинок нет и в сырье. Применяет владелец или агент по прямому «применяй», под учёткой
-- владельца, одной транзакцией:
--   psql "<строка владельца>" -v sp=<Application ID kabinet-jobs-sp> -v ON_ERROR_STOP=1 -f <этот файл>   (транзакция — BEGIN/COMMIT внутри)
-- Только добавляет. Гранты: приложению и claude_code_ro — SELECT; kabinet-jobs-sp — SELECT, INSERT, UPDATE (INSERT …
-- ON CONFLICT DO UPDATE; DELETE не нужен), как у трёх реплик TikTok (sql/kabinet_jobs_sp_2026-10-22.sql).

BEGIN;

CREATE TABLE IF NOT EXISTS kabinet_data.raw_tiktok_returns (
  shop_id text NOT NULL, return_id text NOT NULL, return_line_item_id text NOT NULL, order_id text, seller_sku text,
  product_name text, return_type text, return_status text, return_reason_text text, role text,
  create_time timestamptz, update_time timestamptz, currency text, refund_total numeric(18,2),
  return_refund_total numeric(18,2), seller_paid_return_shipping_fee numeric(18,2),
  loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, return_id, return_line_item_id));
COMMENT ON TABLE kabinet_data.raw_tiktok_returns IS 'Реплика dnipro_m.tiktok.raw_returns для вкладки TikTok (пишет Kabinet - TikTok Shop Loader): заявки на возврат по позициям, без raw_json.';

CREATE TABLE IF NOT EXISTS kabinet_data.raw_tiktok_cancellations (
  shop_id text NOT NULL, cancel_id text NOT NULL, cancel_line_item_id text NOT NULL, order_id text, seller_sku text,
  product_name text, cancel_type text, cancel_status text, cancel_reason_text text, role text,
  create_time timestamptz, update_time timestamptz, currency text, refund_total numeric(18,2),
  loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (shop_id, cancel_id, cancel_line_item_id));
COMMENT ON TABLE kabinet_data.raw_tiktok_cancellations IS 'Реплика dnipro_m.tiktok.raw_cancellations для вкладки TikTok: отмены по позициям, без raw_json.';

GRANT SELECT ON kabinet_data.raw_tiktok_returns, kabinet_data.raw_tiktok_cancellations
  TO "583bf6d1-6cd0-4a89-9c44-b387ec5c21cb", claude_code_ro;
GRANT SELECT, INSERT, UPDATE ON kabinet_data.raw_tiktok_returns, kabinet_data.raw_tiktok_cancellations TO :"sp";

COMMIT;

-- Проверка чтением (после применения):
-- SELECT has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_returns', 'INSERT'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_cancellations', 'UPDATE'),
--        has_table_privilege(:'sp', 'kabinet_data.raw_tiktok_returns', 'DELETE'),
--        has_table_privilege('583bf6d1-6cd0-4a89-9c44-b387ec5c21cb', 'kabinet_data.raw_tiktok_returns', 'INSERT');  -- t, t, f, f
