-- Время Мадрида в сырье Mirakl и ManoMano (14.10.2026). Выполнять ПОСЛЕ миграции nb/mirakl_madrid_migration.py
-- (dry_run = 0): колонки created_date_utc до неё нет, и правило с ней сломалось бы.
-- Содержимое заказов LM проверяется по моменту заказа: created_date теперь хранит часы Мадрида, записанные как UTC,
-- и разница с now() по нему ошибается на час-два. Строку UC сторож пересевает из своего списка RULES — там правка
-- тем же коммитом (nb/patches/2026-10-14_madrid_time_Watchdog.diff); строка Lakebase живёт только в базе.
UPDATE kabinet_data.data_freshness_rules
   SET content_date_column = 'created_date_utc', updated_at = now()
 WHERE table_name IN ('dnipro_m.kabinet_data.raw_lm_orders', 'kabinet_data.raw_lm_orders')
   AND content_date_column = 'created_date';
