# Databricks notebook source
# DBTITLE 1,Kabinet - Worten Loader: офферы и заказы Worten (Mirakl) → dnipro_m.worten.raw_*
# Kabinet - Worten Loader (28.10.2026, решение владельца: «подключи Worten по API тем же путём, что TikTok»; docs/worten.md).
#
# Только чтение у Worten: клиент (worten_client.py рядом) вызывает только три GET белого списка — A01 магазин, OF21
# офферы, OR11 заказы. Магазин — reorder_params.worten_shop_id; ключ — скоуп worten/api-key (кладёт владелец).
#
# Что грузит:
# - офферы — снимок целиком (все страницы OF21); цена для покупателя — цена канала WRT_PT_ONLINE по сроку скидки на момент
#   снимка (worten_rows.py); MERGE по (shop_id, offer_id), у пропавших из ответа офферов остаётся прежний loaded_at —
#   реплика помечает их in_last_load = false, не удаляя;
# - заказы — поиск OR11 по дате изменения кусками worten_window_days: первый запуск — worten_history_days назад, дальше
#   от отметки последнего ЦЕЛИКОМ записанного куска минус worten_order_overlap_days (статусы меняются задним числом);
#   заказ и его строки, без данных покупателя (из адреса — индекс и страна). Отметка — dnipro_m.worten.sync_state.
# Реплика для страниц Кабинета — kabinet_data.raw_worten_offers / _orders / _order_lines в Lakebase, upsert из сырья
# целиком (данных немного), только колонки страниц, без raw_json; loaded_at — из сырья (время снимка). Время заказов —
# приёмом сырья Mirakl, но по Лиссабону: рабочая колонка — часы Лиссабона как UTC, *_utc — исходный момент (docs/worten.md).
# Хост базы и пользователь не зашиты: хост — из описания
# endpoint Lakebase, пользователь — тот, под кем идёт джоба. Настройки — reorder_params (worten_*), не константы.
# Пульс `Kabinet - Worten Loader` — последним и безусловно; порог — только в job_health_rules (в пульсе NULL). Сбои
# копятся и роняют прогон ПОСЛЕ пульса. dry_run=1 — без записи и без пульса. Источник кода — nb/worten_loader.py.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.118.0" requests psycopg2-binary -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import datetime as dt
import os
import sys

import psycopg2
from psycopg2.extras import execute_values
from databricks.sdk import WorkspaceClient

_nb_dir = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
sys.path.insert(0, "/Workspace" + _nb_dir)
import worten_client as wc
import worten_rows as wr

JOB_NAME = "Kabinet - Worten Loader"
SCHEMA = "dnipro_m.worten"
BASE_URL = "https://marketplace.worten.pt"          # адрес Mirakl Worten — не секрет (A01 и версия 3.1320, 28.10.2026)
KABINET_EP = "projects/kabinet-dashboard/branches/production/endpoints/primary"
dbutils.widgets.text("dry_run", "0")
dbutils.widgets.text("full", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
FULL = dbutils.widgets.get("full").strip() == "1"
spark.conf.set("spark.sql.session.timeZone", "UTC")
w = WorkspaceClient()
_user = w.current_user.me().user_name


def pg():
    host = w.postgres.get_endpoint(name=KABINET_EP).status.hosts.host
    cred = w.postgres.generate_database_credential(endpoint=KABINET_EP)
    return psycopg2.connect(host=host, port=5432, dbname="databricks_postgres", user=_user, password=cred.token,
                            sslmode="require")


_need = ("worten_shop_id", "worten_history_days", "worten_order_overlap_days", "worten_window_days")
_c = pg()
try:
    with _c.cursor() as _cur:
        _cur.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key = ANY(%s)", (list(_need),))
        settings = {k: int(v) for k, v in _cur.fetchall()}
finally:
    _c.close()
_missing = [k for k in _need if k not in settings]
if _missing:
    raise RuntimeError(f"в reorder_params нет {_missing} — сначала SQL sql/worten_2026-10-28.sql, часть B (Lakebase)")
SHOP, HISTORY, OVL, WIN = (settings[k] for k in _need)

errors, stats = [], {}
now = dt.datetime.now(dt.timezone.utc)
loaded_at = now


def merge(table, keys, rows):
    """MERGE строк в dnipro_m.worten.<table> по ключу; дубли ключа в пачке — последняя строка."""
    if not rows:
        return 0
    uniq = {tuple(r[k] for k in keys): r for r in rows}
    stats[table] = stats.get(table, 0) + len(uniq)
    if DRY:
        return len(uniq)
    schema = spark.table(f"{SCHEMA}.{table}").schema
    df = spark.createDataFrame([tuple(r.get(f.name) for f in schema.fields) for r in uniq.values()], schema)
    view = f"src_{table}"
    df.createOrReplaceTempView(view)
    on = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    spark.sql(f"MERGE INTO {SCHEMA}.{table} t USING {view} s ON {on} "
              f"WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
    return len(uniq)


def start_from(stream):
    floor = now - dt.timedelta(days=HISTORY)
    if FULL:
        return floor
    row = spark.sql(f"SELECT done_until FROM {SCHEMA}.sync_state WHERE shop_id = :sid AND stream = :st",
                    args={"sid": str(SHOP), "st": stream}).first()
    if not row or row["done_until"] is None:
        return floor
    d = row["done_until"]
    d = d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    return max(d - dt.timedelta(days=OVL), floor)


def mark_done(stream, until):
    merge("sync_state", ("shop_id", "stream"),
          [{"shop_id": str(SHOP), "stream": stream, "done_until": until, "updated_at": loaded_at}])


client = wc.WortenClient.from_databricks(dbutils, BASE_URL, SHOP)
try:                                   # сбой проверки магазина не должен терять пульс
    acc = client.account()
    print(f"магазин {acc.get('shop_id')} «{acc.get('shop_name')}», {acc.get('shop_state')}; dry_run={int(DRY)} "
          f"full={int(FULL)}; история {HISTORY} сут, перекрытие {OVL}, кусок {WIN}")
    if str(acc.get("shop_id")) != str(SHOP):
        errors.append(f"ключ привязан к магазину {acc.get('shop_id')}, а не {SHOP}")
except Exception as e:
    errors.append(f"магазин (A01): {str(e)[:300]}")

# офферы — снимок целиком
try:
    offers = [wr.offer_row(SHOP, o, loaded_at, now) for o in client.pages("/api/offers", "offers")]
    merge("raw_offers", ("shop_id", "offer_id"), offers)
    stats["offers_promo"] = sum(1 for r in offers if r["promo_active"])
    print(f"офферов {len(offers)}, со скидкой сейчас {stats['offers_promo']}")
except Exception as e:
    errors.append(f"офферы: {str(e)[:300]}")

# заказы — кусками по дате изменения, отметка после каждого целого куска
try:
    t0 = start_from("orders")
except Exception as e:
    errors.append(f"заказы, отметка sync_state: {str(e)[:300]}")
    t0 = now
n_orders = 0
for a, b in wr.windows(t0, now, WIN):
    try:
        heads, lines = [], []
        for order in client.pages("/api/orders", "orders", {"start_update_date": wr.iso(a), "end_update_date": wr.iso(b)}):
            h, ls = wr.order_rows(SHOP, order, loaded_at)
            heads.append(h)
            lines.extend(ls)
        merge("raw_order_lines", ("shop_id", "order_line_id"), lines)
        n_orders += merge("raw_orders", ("shop_id", "order_id"), heads)
        mark_done("orders", b)
    except Exception as e:
        errors.append(f"заказы, кусок с {wr.iso(a)}: {str(e)[:300]}")
        break
print(f"заказов {n_orders} с {wr.iso(t0)}")

# Реплика в Lakebase для страниц — из сырья целиком, upsert по ключу
REPLICA = (
    ("raw_worten_offers", ("shop_id", "offer_id"),
     f"""SELECT shop_id, offer_id, shop_sku, product_title, category_code, active, quantity, channel_code, price,
                origin_price, discount_price, discount_start, discount_end, promo_active, currency,
                loaded_at = (SELECT max(loaded_at) FROM {SCHEMA}.raw_offers) AS in_last_load, loaded_at
         FROM {SCHEMA}.raw_offers"""),
    ("raw_worten_orders", ("shop_id", "order_id"),
     f"""SELECT shop_id, order_id, order_state, channel_code, created_at, updated_at, created_at_utc, updated_at_utc,
                currency, price, shipping_price, total_price, total_commission, country, loaded_at
         FROM {SCHEMA}.raw_orders"""),
    ("raw_worten_order_lines", ("shop_id", "order_line_id"),
     f"""SELECT shop_id, order_line_id, order_id, order_line_state, shop_sku, product_title, quantity, price_unit, price,
                total_price, commission_fee, tax_amount, shipped_at, shipped_at_utc, loaded_at
         FROM {SCHEMA}.raw_order_lines"""),
)
for table, keys, select_sql in REPLICA:
    try:
        df = spark.sql(select_sql)
        cols = df.columns
        rows = [tuple(r[c] for c in cols) for r in df.collect()]
        stats[f"lakebase.{table}"] = len(rows)
        if DRY or not rows:
            continue
        # loaded_at — из сырья, не now(): правило свежести видит возраст снимка, а не время записи реплики
        upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in keys)
        _c = pg()
        try:
            with _c.cursor() as _cur:
                _cur.execute("SET TIME ZONE 'UTC'")
                execute_values(_cur, f"INSERT INTO kabinet_data.{table} ({', '.join(cols)}) VALUES %s "
                                     f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {upd}", rows, page_size=500)
            _c.commit()
        finally:
            _c.close()
    except Exception as e:
        errors.append(f"реплика {table}: {str(e)[:300]}")

# Пульс — последним и безусловно; сбои — падение после него
note = (", ".join(f"{k} {v}" for k, v in sorted(stats.items())) + (f"; сбоев {len(errors)}" if errors else ""))[:500]
if DRY:
    print("dry_run: пульс не пишется —", note)
else:
    _c = pg()
    try:
        with _c.cursor() as _cur:
            _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                            VALUES (%s, now(), %s, NULL)
                            ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                         (JOB_NAME, note))
        _c.commit()
    finally:
        _c.close()
    print(f"💓 {JOB_NAME}: {note}")
if errors:
    raise RuntimeError(f"{JOB_NAME}: сбоев {len(errors)}: " + " | ".join(errors)[:900])
