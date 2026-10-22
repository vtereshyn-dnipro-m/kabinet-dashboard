# Databricks notebook source
# DBTITLE 1,Kabinet - TikTok Shop Loader: заказы, товары, финансы → dnipro_m.tiktok.raw_*
# Kabinet - TikTok Shop Loader (22.10.2026, решение владельца: «TikTok Shop — подключаем, только чтение»;
# docs/tiktok-shop.md).
#
# Только чтение у TikTok: клиент (tiktok_client.py рядом) вызывает только пути белого списка — два POST-поиска (заказы,
# товары) и GET. Магазины — все авторизованные (Get Authorized Shops), shop_cipher — из ответа, не хранится.
#
# Что грузит, по каждому магазину:
# - заказы — поиск по update_time кусками по tiktok_window_days: первый запуск — tiktok_history_days назад, дальше от
#   max(update_time) минус tiktok_order_overlap_days (статусы и отмены меняются задним числом); заказ и его строки;
# - товары — снимок целиком (поиск со статусом ALL; SKU, цены и остатки приходят в нём же);
# - выписки — по statement_time: первый запуск — tiktok_history_days, дальше от max(statement_time) минус
#   tiktok_finance_overlap_days (payment_status меняется после выписки); по каждой выписке — её операции.
# Запись — MERGE по ключу, по частям (кусок заказов, все товары, выписка с операциями): падение на середине не уносит
# уже записанное, повторный прогон ничего не задваивает. Персональные данные покупателей срезаются до записи
# (tiktok_rows.py); для повторных покупок — buyer_hash = sha256(соль + user_id), соль — tiktok-shop/buyer-salt.
# Настройки — kabinet_data.reorder_params (tiktok_*), не константы.
#
# Пульс `Kabinet - TikTok Shop Loader` — последним, безусловно; сбои копятся и роняют прогон ПОСЛЕ пульса.
# dry_run=1 — без записи в таблицы и без пульса: печатает, сколько записал бы. full=1 — первый запуск заново
# (tiktok_history_days), даже если в таблицах уже есть данные.
# Пока #364 не смержен — без расписания, прогоны владелец запускает руками под своей учёткой; потом — джоба под
# kabinet-jobs-sp. Источник кода — nb/tiktok_loader.py в kabinet-dashboard.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.118.0" requests psycopg2-binary -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import datetime as dt
import os
import sys
import time

import psycopg2
from databricks.sdk import WorkspaceClient

_nb_dir = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
sys.path.insert(0, "/Workspace" + _nb_dir)
import tiktok_client as tt
import tiktok_rows as tr

JOB_NAME = "Kabinet - TikTok Shop Loader"
SCHEMA = "dnipro_m.tiktok"
dbutils.widgets.text("dry_run", "0")
dbutils.widgets.text("full", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
FULL = dbutils.widgets.get("full").strip() == "1"
spark.conf.set("spark.sql.session.timeZone", "UTC")      # время в строках — UTC без пояса
w = WorkspaceClient()


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


_c = pg()
try:
    with _c.cursor() as _cur:
        _cur.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key LIKE 'tiktok\\_%'")
        settings = {k: int(v) for k, v in _cur.fetchall()}
finally:
    _c.close()
_need = ("tiktok_history_days", "tiktok_order_overlap_days", "tiktok_finance_overlap_days", "tiktok_window_days")
_missing = [k for k in _need if k not in settings]
if _missing:
    raise RuntimeError(f"в reorder_params нет {_missing} — сначала SQL sql/tiktok_schema_2026-10-22.sql, часть C")
HISTORY, ORD_OVL, FIN_OVL, WIN = (settings[k] for k in _need)

errors, stats = [], {}
now = int(time.time())
loaded_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def merge(table, keys, rows):
    """MERGE строк в dnipro_m.tiktok.<table> по ключу; дубли ключа в пачке — последняя строка."""
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


def start_from(table, col, shop_id, overlap_days):
    if FULL:
        return now - HISTORY * 86400
    row = spark.sql(f"SELECT max({col}) AS m FROM {SCHEMA}.{table} WHERE shop_id = :sid", args={"sid": shop_id}).first()
    if not row or row["m"] is None:
        return now - HISTORY * 86400
    last = int(row["m"].replace(tzinfo=dt.timezone.utc).timestamp())
    return max(last - overlap_days * 86400, now - HISTORY * 86400)


client = tt.TikTokClient.from_databricks(dbutils)
try:
    SALT = dbutils.secrets.get(tt.SCOPE, "buyer-salt")      # значение не печатается
except Exception:
    SALT = None
if not SALT:
    raise RuntimeError("нет секрета tiktok-shop/buyer-salt — соль для buyer_hash задаёт владелец (docs/tiktok-shop.md)")
shops = client.get_authorized_shops()
print(f"магазинов: {len(shops)}; dry_run={int(DRY)} full={int(FULL)}; история {HISTORY} сут, перекрытие заказов "
      f"{ORD_OVL}, выписок {FIN_OVL}, кусок {WIN}")
exp = client.expiries()
print(f"токены: access до {tt.fmt_ts(exp['access_expires'])}, refresh до {tt.fmt_ts(exp['refresh_expires'])}")

for shop in shops:
    sid = shop["id"]
    q = {"shop_cipher": shop["cipher"]}
    label = f"{shop.get('region')}/{sid}"

    # заказы
    try:
        t0 = start_from("raw_orders", "update_time", sid, ORD_OVL)
        n_orders = 0
        for a, b in tr.windows(t0, now, WIN):
            heads, lines = [], []
            for order in client.pages("POST", "/order/202309/orders/search", "orders",
                                      {**q, "sort_field": "update_time", "sort_order": "ASC"},
                                      {"update_time_ge": a, "update_time_lt": b}, page_size=100):
                h, ls = tr.order_rows(shop, order, loaded_at, SALT)
                heads.append(h)
                lines.extend(ls)
            n_orders += merge("raw_orders", ("shop_id", "order_id"), heads)
            merge("raw_order_lines", ("shop_id", "line_item_id"), lines)
        print(f"{label}: заказов {n_orders} с {tt.fmt_ts(t0)}")
    except Exception as e:
        errors.append(f"{label} заказы: {str(e)[:300]}")

    # товары — снимок целиком
    try:
        heads, skus = [], []
        for product in client.pages("POST", "/product/202502/products/search", "products", q, {"status": "ALL"},
                                    page_size=100):
            h, ss = tr.product_rows(shop, product, loaded_at)
            heads.append(h)
            skus.extend(ss)
        merge("raw_products", ("shop_id", "product_id"), heads)
        merge("raw_product_skus", ("shop_id", "sku_id"), skus)
        print(f"{label}: товаров {len(heads)}, SKU {len(skus)}")
    except Exception as e:
        errors.append(f"{label} товары: {str(e)[:300]}")

    # выписки и их операции
    try:
        t0 = start_from("raw_finance_statements", "statement_time", sid, FIN_OVL)
        n_st = n_tr = 0
        for a, b in tr.windows(t0, now, WIN):
            for st in client.pages("GET", "/finance/202309/statements", "statements",
                                   {**q, "sort_field": "statement_time", "sort_order": "ASC",
                                    "statement_time_ge": a, "statement_time_lt": b}, page_size=100):
                rows, cur = [], st.get("currency")
                for t in client.pages("GET", f"/finance/202501/statements/{st['id']}/statement_transactions",
                                      "transactions", {**q, "sort_field": "order_create_time"}, page_size=100):
                    rows.append(tr.transaction_row(shop, st["id"], cur, t, loaded_at))
                # операции раньше выписки: выписка без операций не выглядит полной
                n_tr += merge("raw_finance_statement_transactions", ("shop_id", "statement_id", "transaction_id"), rows)
                n_st += merge("raw_finance_statements", ("shop_id", "statement_id"), [tr.statement_row(shop, st, loaded_at)])
        print(f"{label}: выписок {n_st}, операций {n_tr} с {tt.fmt_ts(t0)}")
    except Exception as e:
        errors.append(f"{label} финансы: {str(e)[:300]}")

if not shops:
    errors.append("Get Authorized Shops вернул пустой список")

# Пульс — последним и безусловно (в той же ячейке: ячейка самодостаточна); сбои — падение после него
note = (f"магазинов {len(shops)}; " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items()))
        + (f"; сбоев {len(errors)}" if errors else ""))[:500]
if DRY:
    print("dry_run: пульс не пишется —", note)
else:
    _c = pg()
    try:
        with _c.cursor() as _cur:
            _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                            VALUES (%s, now(), %s, 26)
                            ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                         (JOB_NAME, note))
        _c.commit()
    finally:
        _c.close()
    print(f"💓 {JOB_NAME}: {note}")
if errors:
    raise RuntimeError(f"{JOB_NAME}: сбоев {len(errors)}: " + " | ".join(errors)[:900])
