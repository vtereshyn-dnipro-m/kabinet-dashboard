-- TikTok Shop, справочники (шаг 1 из групп 2–5: логистика и категории, 26.10.2026): таблицы сырья и правило сторожа для
-- `Kabinet - TikTok Shop Reference Loader` (docs/tiktok-shop.md). Применяет владелец — сам или агентом по прямому
-- «применяй», только под учёткой владельца. Только добавляет: ничего не удаляет и ни у кого не отнимает.
--
-- Права: kabinet-jobs-sp уже имеет на схему dnipro_m.tiktok USE SCHEMA, CREATE TABLE, MODIFY, SELECT (26.10.2026) —
-- новые таблицы схемы их наследуют, отдельных GRANT не нужно. В Lakebase загрузчик пишет только system_pulse — право
-- у принципала уже есть (sql/kabinet_jobs_sp_2026-10-22.sql).
-- Данных покупателей в этих таблицах нет. У складов из адреса — только регион и страна (nb/tiktok_reference_rows.py).

-- ── Часть A. Таблицы (SQL-склад, под владельцем) ──
CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_warehouses (
  shop_id STRING NOT NULL, region STRING, warehouse_id STRING NOT NULL, name STRING, type STRING, sub_type STRING,
  effect_status STRING, is_default BOOLEAN, region_code STRING, state STRING, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: склады магазина (GET /logistics/202309/warehouses), без адреса и контакта. Ключ shop_id + warehouse_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_delivery_options (
  shop_id STRING NOT NULL, region STRING, warehouse_id STRING NOT NULL, delivery_option_id STRING NOT NULL, name STRING,
  type STRING, platforms STRING, raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: варианты доставки склада (GET /logistics/202309/warehouses/{id}/delivery_options). Ключ shop_id + warehouse_id + delivery_option_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_shipping_providers (
  shop_id STRING NOT NULL, region STRING, delivery_option_id STRING NOT NULL, provider_id STRING NOT NULL, name STRING,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: перевозчики варианта доставки (GET /logistics/202309/delivery_options/{id}/shipping_providers). Ключ shop_id + delivery_option_id + provider_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_categories (
  shop_id STRING NOT NULL, region STRING, locale STRING NOT NULL, category_id STRING NOT NULL, parent_id STRING,
  local_name STRING, is_leaf BOOLEAN, permission_statuses STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: дерево категорий (GET /product/202309/categories, локаль es-ES). Ключ shop_id + locale + category_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_product_categories (
  shop_id STRING NOT NULL, region STRING, product_id STRING NOT NULL, category_id STRING, category_path STRING,
  category_chain_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: листовая категория каждого товара (цепочка из GET /product/202309/products/{id}). Ключ shop_id + product_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_category_attributes (
  shop_id STRING NOT NULL, region STRING, category_id STRING NOT NULL, attribute_id STRING NOT NULL, name STRING,
  type STRING, is_required BOOLEAN, is_customizable BOOLEAN, is_multiple_selection BOOLEAN, values_count INT,
  raw_json STRING, loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: атрибуты листовых категорий наших товаров (GET /product/202309/categories/{id}/attributes). Ключ shop_id + category_id + attribute_id.';

CREATE TABLE IF NOT EXISTS dnipro_m.tiktok.raw_category_rules (
  shop_id STRING NOT NULL, region STRING, category_id STRING NOT NULL, cod_supported BOOLEAN, epr_required BOOLEAN,
  manufacturer_required BOOLEAN, responsible_person_required BOOLEAN, package_dimension_required BOOLEAN,
  size_chart_required BOOLEAN, certifications_count INT, required_certifications_count INT, raw_json STRING,
  loaded_at TIMESTAMP)
COMMENT 'TikTok Shop: правила листовых категорий наших товаров (GET /product/202309/categories/{id}/rules). Ключ shop_id + category_id.';

-- ── Часть B. Правило сторожа (Lakebase, под владельцем) — ПОСЛЕ создания джобы, с её job_id ──
-- psql "<строка владельца>" -v reference_job_id=<id> -v ON_ERROR_STOP=1 -1 -f <файл с этой частью>
-- Имя = метка пульса = имя джобы (AGENTS.md, «Одно имя джоба в трёх местах»). Раз в неделю — порог 192 ч.
-- INSERT INTO kabinet_data.job_health_rules (job_id, job_name, expected_interval_hours, schedule_description, is_active, note)
-- VALUES (:reference_job_id, 'Kabinet - TikTok Shop Reference Loader', 192, 'еженедельно, пн 12:00 Kyiv', true,
--         'TikTok Shop: склады, доставка, перевозчики, категории и их атрибуты и правила; run_as kabinet-jobs-sp')
-- ON CONFLICT (job_id) DO NOTHING;
