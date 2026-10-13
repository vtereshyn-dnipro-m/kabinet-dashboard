# Databricks notebook source
# DBTITLE 1,Время Мадрида в сырье Mirakl и ManoMano — перевод истории (разовый, 14.10.2026)
# Время Мадрида в сырье Mirakl и ManoMano (решение владельца 13.10.2026, просьба Дарины).
#
# Leroy Merlin и Carrefour (Mirakl) отдают время в UTC («…Z»), и всё, что считало день из него — витрины Дарины
# (DATE(created_date), order_date), Power BI, наша экономика и v_sales_vat_incl_daily, — относило ночные продажи
# Испании ко вчерашнему дню. ManoMano отдаёт местное смещение, у него день и так был днём Мадрида, но момент
# хранился в UTC.
#
# Правило после перевода — одно в UC и в Lakebase, то же, что date_order_madrid у Odoo:
#   рабочая колонка (created_date, created_at, transaction_date…) — часы Мадрида, записанные как время UTC
#   (Spark: from_utc_timestamp; Lakebase: (x AT TIME ZONE 'Europe/Madrid') AT TIME ZONE 'UTC'), поэтому
#   DATE(x) в UTC-сессии сразу даёт день Мадрида и чужие вьюхи править не нужно;
#   <колонка>_utc — исходный момент. Длительности («сколько ждёт», окно «последние N дней») — только по *_utc.
# Сдвиг берётся часовым поясом по дате каждой строки (летом +2, зимой +1), а не константой.
#
# Повторный запуск безопасен: строка переводится, только пока её *_utc пуст. Параметр dry_run = 1 (по умолчанию):
# только посчитать, сколько строк будет переведено и у скольких сменится день, ничего не меняя.
# Запуск — джобой под владельцем таблиц (в Lakebase они принадлежат v.tereshyn@dniprom.com, ALTER нужен ему).
# Порядок выкладки: эта миграция → сразу новые версии загрузчиков → повторный прогон миграции (поймать строки,
# если старый загрузчик успел что-то записать между ними).

# COMMAND ----------

import json
import psycopg2
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("dry_run", "1")
DRY = dbutils.widgets.get("dry_run").strip() != "0"
TZ = "Europe/Madrid"
spark.conf.set("spark.sql.session.timeZone", "UTC")   # DATE() ниже обязан видеть часы Мадрида, а не сдвигать их

# колонки времени событий; loaded_at — время нашей загрузки, остаётся UTC
UC = {
    "raw_lm_orders":       ["created_date", "last_updated_date"],
    "raw_lm_order_lines":  ["shipped_date", "created_date", "debited_date", "last_updated_date", "received_date"],
    "raw_lm_refunds":      ["created_date", "transaction_date"],
    "raw_lm_transactions": ["date_created", "last_updated", "transaction_date"],
    "raw_cf_orders":       ["created_at"],
    "raw_cf_transactions": ["date_created", "last_updated", "transaction_date"],
    "raw_mm_orders":       ["created_at"],
}
LB = {   # реплики в Lakebase — колонок там меньше
    "raw_lm_orders":       ["created_date", "last_updated_date"],
    "raw_lm_order_lines":  ["shipped_date"],
    "raw_lm_transactions": ["date_created", "last_updated", "transaction_date"],
    "raw_cf_orders":       ["created_at"],
    "raw_cf_transactions": ["date_created", "last_updated", "transaction_date"],
    "raw_mm_orders":       ["created_at"],
}
report = {"dry_run": DRY, "uc": {}, "lb": {}}

# COMMAND ----------

# DBTITLE 1,Unity Catalog (dnipro_m.kabinet_data)
for t, cols in UC.items():
    full = f"dnipro_m.kabinet_data.{t}"
    existing = set(spark.table(full).columns)
    missing = [c + "_utc" for c in cols if c + "_utc" not in existing]
    if missing and not DRY:
        spark.sql(f"ALTER TABLE {full} ADD COLUMNS ({', '.join(m + ' TIMESTAMP' for m in missing)})")
    for c in cols:
        pending = f"{c} IS NOT NULL" + (f" AND {c}_utc IS NULL" if (c + "_utc") in existing or not DRY else "")
        n, moved = spark.sql(f"""
            SELECT count(*), coalesce(sum(CASE WHEN to_date({c}) <> to_date(from_utc_timestamp({c}, '{TZ}'))
                                               THEN 1 ELSE 0 END), 0)
            FROM {full} WHERE {pending}""").first()
        if not DRY and n:
            # в одном UPDATE обе правые части берут прежнее значение строки — момент уходит в *_utc, часы в рабочую
            spark.sql(f"UPDATE {full} SET {c}_utc = {c}, {c} = from_utc_timestamp({c}, '{TZ}') WHERE {pending}")
        report["uc"][f"{t}.{c}"] = {"rows": int(n), "day_changes": int(moved)}

# день строки Carrefour — по created_at заказа; прежний (UTC) уходит в order_date_utc
full_l = "dnipro_m.kabinet_data.raw_cf_order_lines"
if "order_date_utc" not in spark.table(full_l).columns and not DRY:
    spark.sql(f"ALTER TABLE {full_l} ADD COLUMNS (order_date_utc DATE)")
_has_utc = "order_date_utc" in spark.table(full_l).columns
# заказы уже переведены (created_at_utc заполнен) — их created_at и есть часы Мадрида; в пробе до перевода — сдвигаем сами
_orders_done = "created_at_utc" in spark.table("dnipro_m.kabinet_data.raw_cf_orders").columns
src = (f"""SELECT order_ref, to_date(created_at) AS d FROM dnipro_m.kabinet_data.raw_cf_orders
           WHERE created_at IS NOT NULL AND created_at_utc IS NOT NULL""" if _orders_done else
       f"""SELECT order_ref, to_date(from_utc_timestamp(created_at, '{TZ}')) AS d FROM dnipro_m.kabinet_data.raw_cf_orders
           WHERE created_at IS NOT NULL""")
n, moved = spark.sql(f"""
    SELECT count(*), coalesce(sum(CASE WHEN l.order_date <> o.d THEN 1 ELSE 0 END), 0)
    FROM {full_l} l JOIN ({src}) o ON o.order_ref = l.order_ref
    WHERE l.order_date IS NOT NULL""" + (" AND l.order_date_utc IS NULL" if _has_utc else "")).first()
if not DRY:
    spark.sql(f"""
        MERGE INTO {full_l} l USING ({src}) o ON o.order_ref = l.order_ref
        WHEN MATCHED AND l.order_date IS NOT NULL AND l.order_date_utc IS NULL
          THEN UPDATE SET order_date_utc = l.order_date, order_date = o.d""")
report["uc"]["raw_cf_order_lines.order_date"] = {"rows": int(n), "day_changes": int(moved)}
print(json.dumps(report["uc"], ensure_ascii=False, indent=1))

# COMMAND ----------

# DBTITLE 1,Lakebase (kabinet_data)
w = WorkspaceClient()
pg = psycopg2.connect(
    host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
    dbname="databricks_postgres", user=w.current_user.me().user_name, sslmode="require",
    password=w.postgres.generate_database_credential(
        endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token)
cur = pg.cursor()
cur.execute("SET TIME ZONE 'UTC'")
MAD = "(({c} AT TIME ZONE 'Europe/Madrid') AT TIME ZONE 'UTC')"
for t, cols in LB.items():
    for c in cols:
        cur.execute("""SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'kabinet_data' AND table_name = %s AND column_name = %s""", (t, c + "_utc"))
        has = cur.fetchone() is not None
        if not has and not DRY:
            cur.execute(f"ALTER TABLE kabinet_data.{t} ADD COLUMN {c}_utc timestamptz")
        pending = f"{c} IS NOT NULL" + (f" AND {c}_utc IS NULL" if has or not DRY else "")
        cur.execute(f"SELECT count(*), count(*) FILTER (WHERE {c}::date <> {MAD.format(c=c)}::date) "
                    f"FROM kabinet_data.{t} WHERE {pending}")
        n, moved = cur.fetchone()
        if not DRY and n:
            cur.execute(f"UPDATE kabinet_data.{t} SET {c}_utc = {c}, {c} = {MAD.format(c=c)} WHERE {pending}")
        report["lb"][f"{t}.{c}"] = {"rows": n, "day_changes": moved}

cur.execute("""SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'kabinet_data' AND table_name = 'raw_cf_order_lines' AND column_name = 'order_date_utc'""")
has = cur.fetchone() is not None
if not has and not DRY:
    cur.execute("ALTER TABLE kabinet_data.raw_cf_order_lines ADD COLUMN order_date_utc date")
mad_day = "o.created_at::date" if not DRY else MAD.format(c="o.created_at") + "::date"
guard = (" AND l.order_date_utc IS NULL" if has or not DRY else "") + (" AND o.created_at_utc IS NOT NULL" if not DRY else "")
cur.execute(f"""SELECT count(*), count(*) FILTER (WHERE l.order_date <> {mad_day})
                FROM kabinet_data.raw_cf_order_lines l JOIN kabinet_data.raw_cf_orders o ON o.order_ref = l.order_ref
                WHERE l.order_date IS NOT NULL{guard}""")
n, moved = cur.fetchone()
if not DRY and n:
    cur.execute(f"""UPDATE kabinet_data.raw_cf_order_lines l SET order_date_utc = l.order_date, order_date = {mad_day}
                    FROM kabinet_data.raw_cf_orders o
                    WHERE o.order_ref = l.order_ref AND l.order_date IS NOT NULL{guard}""")
report["lb"]["raw_cf_order_lines.order_date"] = {"rows": n, "day_changes": moved}

if DRY:
    pg.rollback()
else:
    pg.commit()     # весь Lakebase — одной транзакцией: либо переведено всё, либо ничего
pg.close()
print(json.dumps(report["lb"], ensure_ascii=False, indent=1))
dbutils.notebook.exit(json.dumps(report, ensure_ascii=False))
