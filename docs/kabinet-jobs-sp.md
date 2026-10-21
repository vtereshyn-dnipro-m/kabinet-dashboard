# Сервисный принципал джоб `kabinet-jobs-sp` — вариант В (план 22.10.2026)

Решение владельца 21.10.2026: у Кабинета будет свой принципал для джоб, а `claude-uc-ro` станет действительно «только
чтение». Здесь — пошагово, что делает владелец руками, что в репозитории и как откатить. Агент ничего не применяет.

## Что сейчас (проверено чтением 21.10.2026)

- 20 наших джоб ходят от `claude-uc-ro` (b1698364-…). В Lakebase Кабинета у него прямые гранты на 219 объектов
  `kabinet_data` — 173 таблицы, 7 секционированных, 39 вью; SELECT на все, запись на 66. Ещё 16 последовательностей
  (USAGE, SELECT), USAGE на схему и права по умолчанию на новые таблицы (SELECT, от `claude_code_rw` и владельца). В базе
  Listing Suite прямых грантов нет. Выгружено из каталога (`aclexplode` по `pg_class.relacl` и `pg_default_acl`).
  `information_schema.role_table_grants` для этого не годится: он показывает только гранты с участием спрашивающей
  роли. Первая выгрузка 21.10 через него дала 120 объектов — без `system_pulse`, `orders_history`, `raw_lm_*`, `raw_mm_*`.
- У всех 20 `run_as` в настройках не задан: джоба идёт от своего владельца, а владелец — `claude-uc-ro` (IS_OWNER;
  у группы `admins` — CAN_MANAGE).
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
4. Право на проект Lakebase, скорее всего, **не нужно**: `claude-uc-ro` подключается без него — хватает роли в базе
   (шаг 2, файл 1, A1). Давать CAN USE на проект `kabinet-dashboard`, только если первый прогон упадёт на
   `generate_database_credential` с отказом в доступе.

## Шаг 2. Права «только добавить» (владелец, SQL)

`sql/kabinet_jobs_sp_2026-10-22.sql`:
- **Часть A — Lakebase Кабинета, два файла по порядку**, оба через psql (переменные `:"sp"` и `:'sp'` понимает только
  psql, SQL-редактор Lakebase — нет), каждый одной транзакцией (`-1`):
  1. `sql/kabinet_jobs_sp_2026-10-22.sql` — под владельцем базы: `psql "<строка владельца>" -v sp=<Application ID>
     -v ON_ERROR_STOP=1 -1 -f sql/kabinet_jobs_sp_2026-10-22.sql`.
     - A1 — роль: `databricks_create_role(:'sp', 'SERVICE_PRINCIPAL')`. Если роль уже заведена в интерфейсе Lakebase
       или функция откажет внутри транзакции — завести роль в интерфейсе, строку закомментировать, запустить заново.
     - A2 — USAGE на схему.
     - A3 — ровно те гранты, что у `claude-uc-ro`: 219 объектов, запись на 66.
     - A5 — права по умолчанию на новые таблицы, которые создаёт сам владелец.
  2. `sql/kabinet_jobs_sp_2026-10-22_ro.sql` — под подключением `claude_code_ro`, той же строкой, что у прежних
     грантов: A4 (16 последовательностей, USAGE на все, SELECT где он есть у `claude-uc-ro`) и права по умолчанию на
     таблицы, которые создаёт `claude_code_rw`. Под владельцем это не выдать: последовательности принадлежат
     `claude_code_ro`, а владелец состоит в `claude_code_ro` и `claude_code_rw` только с ADMIN, без INHERIT и SET.
     GRANT на последовательности тогда молча вернёт `WARNING: no privileges were granted`, а `ON_ERROR_STOP`
     предупреждения не ловит. Смена прав по умолчанию за `claude_code_rw` упадёт с ошибкой.
  3. Проверка чтением — запросы в конце второго файла. Ожидается: 235 объектов (219 и 16 последовательностей), пустая
     разница с `claude-uc-ro`, 2 строки прав по умолчанию. Без этой проверки недовыдачу не увидеть.
- **Часть B — Unity Catalog** (SQL-склад, `<sp>` подставить руками):
  - чтение — `USE CATALOG`, плюс `USE SCHEMA` и `SELECT` на `dnipro_m`, `kabinet`, `kabinet_data`, `listing_data`.
    У `claude-uc-ro` явных грантов в UC почти нет (USE CATALOG и `kabinet_data`), остальное он получает через
    `account users`. Новому принципалу чтение даётся явно, чтобы ничего не пропало, когда `account users` урежут;
  - запись (`CREATE TABLE`, `MODIFY` на `dnipro_m.dnipro_m`) — **не сейчас**: первым пяти джобам она не нужна, девяти
    пишущим её дадут вторым PR вместе с передачей владения 14 таблицами.

**«Только чтение» в UC пока на бумаге.** Пока у `account users` на каталог ALL PRIVILEGES и MANAGE, новый принципал (как
и любой) может писать в UC через группу. По-настоящему ограничение заработает после последнего шага «Дальше».

Ничего не отнимается: `claude-uc-ro` и `account users` работают как прежде.

## Шаг 3. Доступ к ноутбукам (владелец, интерфейс)

Для первых пяти: `Kabinet - Dependent Demand`, `Kabinet - Shipment Facts` — ноутбуки в папке `/Users/b1698364-…/`;
`SKU Master Loader`, `Product Entities Loader`, `Assortment Matrix Loader` — в `/Users/v.tereshyn@dniprom.com/`.
**Can Read** для `kabinet-jobs-sp` — каждому из пяти ноутбуков отдельно (ноутбук → Share/Permissions), не папке:
право на домашнюю папку открыло бы принципалу все ноутбуки в ней.
- `/Users/b1698364-6ec5-4240-8cd6-e06dd6e60856/Kabinet - Dependent Demand`
- `/Users/b1698364-6ec5-4240-8cd6-e06dd6e60856/Kabinet - Shipment Facts`
- `/Users/v.tereshyn@dniprom.com/Kabinet - SKU Master Loader`
- `/Users/v.tereshyn@dniprom.com/Kabinet - Product Entities Loader`
- `/Users/v.tereshyn@dniprom.com/Kabinet - Assortment Matrix Loader`

Секреты этим пяти джобам не нужны.

## Шаг 4. Перевести первые пять джоб (по «мержи», по одной)

Файлы — в `nb/jobs/kabinet_jobs_sp_2026-10-22/`:
- `N_*.json` — ставит `run_as` = новый принципал (Application ID подставить);
- `N_*.rollback.json` — убирает `run_as` (`fields_to_remove`). Без `run_as` джоба снова идёт от владельца, то есть от
  `claude-uc-ro`. Так откат не зависит от роли Service Principal: User на `claude-uc-ro`: она нужна, чтобы записать
  его в `run_as` явно, а есть ли она у владельца, не проверялось. Почему эти пять: в Unity Catalog не пишут, секретов не читают, идут
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
- Откат — `databricks jobs update --json @…rollback.json`: `run_as` убран, джоба снова идёт от владельца
  (`claude-uc-ro`), его права не трогались.

## Дальше (отдельными PR, по «мержи»)

1. Остальные 6 джоб без записи в UC (Reconciliation, Warehouse Owner from Odoo, Unified Pricing, ClickUp Sync, Forecast
   Plan, Buy Box) — плюс READ на их секреты (`odoo`, `kabinet-external`, `clickup`, `amazon-sp-api`).
2. Девять пишущих в UC — `CREATE TABLE, MODIFY` на `dnipro_m.dnipro_m`, передача владения 14 таблицами
   (`ALTER TABLE … OWNER TO`), READ на `amazon-sp-api`.
3. Владение: у всех 20 джоб владелец — `claude-uc-ro`. Перед тем как урезать его права, передать владение джобами
   владельцу Кабинета или новому принципалу. Иначе после урезания любая джоба, у которой `run_as` по ошибке сброшен,
   пойдёт от `claude-uc-ro` с правами только на чтение. Тогда же перенести ноутбуки 9 джоб (2 из первой пятёрки:
   Dependent Demand и Shipment Facts) из `/Users/b1698364-…/` в общую папку Кабинета и поправить `notebook_path`.
4. Правило «новая таблица — гранты обоим принципалам» (AGENTS.md) — отдельной правкой AGENTS.md и
   `docs/facts/platform.md`, по «мержи». На переходный период — трём: приложению, `claude-uc-ro` и `kabinet-jobs-sp`.
   Права по умолчанию (A5) покрывают таблицы, созданные `claude_code_rw` и владельцем; таблицы других создателей —
   нет.
5. Когда все 20 на новом принципале и сутки зелёные: у `claude-uc-ro` убрать запись в Lakebase (REVOKE INSERT,
   UPDATE, DELETE), в UC оставить USE и SELECT. Затем отдельным планом — `account users` только на чтение.
