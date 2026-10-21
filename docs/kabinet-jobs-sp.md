# Сервисный принципал джоб `kabinet-jobs-sp` — вариант В (план 22.10.2026)

Решение владельца 21.10.2026: у Кабинета будет свой принципал для джоб, а `claude-uc-ro` станет действительно «только
чтение». Здесь — пошагово, что делает владелец руками, что в репозитории и как откатить. Агент ничего не применяет.

## Что сейчас (проверено чтением 21.10.2026)

- 20 наших джоб ходят от `claude-uc-ro` (b1698364-…). В Lakebase Кабинета у него прямые гранты на 120 таблиц и вью
  `kabinet_data` (SELECT на все, запись на часть) и на 16 последовательностей; в базе Listing Suite прямых грантов нет.
- В Unity Catalog из этих 20 пишут 9 — каждая в СВОИ таблицы схемы `dnipro_m.dnipro_m` (владелец — `claude-uc-ro`, 14
  таблиц): Settlements, Inventory Age, FBA Shipments, Listing Snapshots Replica, FBA Charges, Odoo Purchase Orders,
  Sales & Traffic Replica, Account Health, Brand Analytics. Остальные 11 в UC только читают.
- Секреты: `amazon-sp-api` (9 джоб), `odoo` (2), `kabinet-external` (2), `clickup` (1); у 6 джоб секретов нет.
- Ноутбуки 9 джоб лежат в домашней папке самого `claude-uc-ro` (`/Users/b1698364-…/`), остальных — в папке владельца.

## Шаг 1. Создать принципал (владелец, интерфейс)

1. Настройки воркспейса → Identity and access → Service principals → Add → «Add new», имя `kabinet-jobs-sp`.
   Записать **Application ID** — он дальше везде вместо `<sp>`.
2. У принципала: Entitlements — `Workspace access` (без SQL-доступа и создания кластеров). Секрет OAuth не нужен:
   джобы получают токен от Databricks сами.
3. Permissions принципала → дать себе роль **Service Principal: User** — без неё Databricks не даст поставить «Run as»
   этого принципала в настройках джобы.
4. Lakebase: проект `kabinet-dashboard` → Permissions → `kabinet-jobs-sp` — право подключаться (CAN USE /
   «Can connect»), иначе `generate_database_credential` в ноутбуке вернёт отказ.

## Шаг 2. Права «только добавить» (владелец, SQL)

`sql/kabinet_jobs_sp_2026-10-22.sql`:
- **Часть A — Lakebase Кабинета**: роль принципала (`databricks_create_role`), `USAGE` на схему, те же гранты, что у
  `claude-uc-ro` (120 строк, выгружены из `information_schema`), последовательности.
- **Часть B — Unity Catalog**: только чтение (`USE CATALOG`, `USE SCHEMA`, `SELECT` на `dnipro_m`, `kabinet`,
  `kabinet_data`, `listing_data`). Запись (`CREATE TABLE`, `MODIFY` на `dnipro_m.dnipro_m`) — НЕ сейчас: первым пяти
  джобам она не нужна; для девяти пишущих — вторым PR вместе с передачей владения 14 таблицами.

Ничего не отнимается: `claude-uc-ro` и `account users` работают как прежде.

## Шаг 3. Доступ к ноутбукам (владелец, интерфейс)

Для первых пяти: `Kabinet - Dependent Demand`, `Kabinet - Shipment Facts` — ноутбуки в папке `/Users/b1698364-…/`;
`SKU Master Loader`, `Product Entities Loader`, `Assortment Matrix Loader` — в `/Users/v.tereshyn@dniprom.com/`.
Каждому ноутбуку (или папке) → Permissions → `kabinet-jobs-sp` — **Can Read**. Секреты первым пяти не нужны.

## Шаг 4. Перевести первые пять джоб (по «мержи», по одной)

`nb/jobs/kabinet_jobs_sp_2026-10-22/N_*.json` — `run_as` = новый принципал (подставить Application ID), рядом
`N_*.rollback.json` — обратно на `claude-uc-ro`. Почему эти пять: в Unity Catalog не пишут, секретов не читают, идут
утром одна за другой и не трогают квоту Amazon:

| # | джоба | расписание (Киев) | пишет |
|---|---|---|---|
| 1 | Kabinet - Dependent Demand | 08:05 | Lakebase |
| 2 | Kabinet - Shipment Facts | 16:30 | Lakebase |
| 3 | Kabinet - SKU Master Loader | 07:15 | Lakebase |
| 4 | Kabinet - Product Entities Loader | 07:30 | Lakebase |
| 5 | Kabinet - Assortment Matrix Loader | 07:45 | Lakebase |

Перевод: `databricks jobs update --json @nb/jobs/kabinet_jobs_sp_2026-10-22/1_dependent_demand.json` (после подстановки
id). Не в окна 09:30–11:30 и 16:00–17:30; лучше днём, чтобы ближайший плановый прогон шёл уже под новым принципалом.

## Шаг 5. Проверка и откат

- Ближайший плановый прогон каждой — зелёный, пульс в `system_pulse` свежий, строки в её таблицах Lakebase обновились;
  «Run as» прогона — `kabinet-jobs-sp`. Признак нехватки прав — `permission denied for table …` (Lakebase) или
  `PERMISSION_DENIED` (UC) в ошибке прогона.
- Откат — `databricks jobs update --json @…rollback.json`: джоба снова от `claude-uc-ro`, права которого не трогались.

## Дальше (отдельными PR, по «мержи»)

1. Остальные 6 джоб без записи в UC (Reconciliation, Warehouse Owner from Odoo, Unified Pricing, ClickUp Sync, Forecast
   Plan, Buy Box) — плюс READ на их секреты (`odoo`, `kabinet-external`, `clickup`, `amazon-sp-api`).
2. Девять пишущих в UC — `CREATE TABLE, MODIFY` на `dnipro_m.dnipro_m`, передача владения 14 таблицами
   (`ALTER TABLE … OWNER TO`), READ на `amazon-sp-api`.
3. Когда все 20 на новом принципале и сутки зелёные: `claude-uc-ro` — убрать запись в Lakebase (REVOKE INSERT/UPDATE/
   DELETE), в UC оставить USE + SELECT; затем — план для `account users` (только чтение), отдельно.
