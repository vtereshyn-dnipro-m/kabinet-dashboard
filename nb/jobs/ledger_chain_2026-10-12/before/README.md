# Настройки до вечерней цепочки (12.10.2026)

Полный ответ `databricks jobs get` для двух джоб в том виде, в каком они работали до #282. Нужны для отката.

Откат:
1. `databricks jobs delete 414072669598061` («Kabinet - После Ledger Summary») и `databricks jobs delete 936210060909607` («… (запасной)»).
2. Вернуть расписания:
   - Stock Loader: `databricks jobs update --json '{"job_id": 201160589560980, "new_settings": {"schedule": {"quartz_cron_expression": "0 0 12,15,17 * * ?", "timezone_id": "Europe/Kyiv", "pause_status": "UNPAUSED"}}}'`
   - Coverage Projection: `databricks jobs update --json '{"job_id": 847957236064692, "new_settings": {"schedule": {"quartz_cron_expression": "0 30 15,17 * * ?", "timezone_id": "Europe/Kyiv", "pause_status": "UNPAUSED"}}}'`
3. Удалить строку `job_health_rules` с job_id 936210060909607 и метку `system_pulse` «Kabinet - Запасной прогон после Ledger Summary».
