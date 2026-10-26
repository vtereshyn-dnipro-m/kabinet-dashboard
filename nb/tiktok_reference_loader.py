# Databricks notebook source
# DBTITLE 1,Kabinet - TikTok Shop Reference Loader: склады, доставка, перевозчики, категории → dnipro_m.tiktok
# Kabinet - TikTok Shop Reference Loader (26.10.2026, шаг 1 из групп 2–5 плана «все группы TikTok API на чтение»: логистика и
# категории, решение владельца; docs/tiktok-shop.md).
#
# Только GET: клиент (tiktok_client.py рядом) вызывает только пути белого списка. Справочники магазина, раз в неделю
# (пн 12:00 Киев: после окна 09:30–11:30 и далеко от прогонов заказов 06:30 и аналитики 06:45 с их повторами — три
# джобы делят один refresh-токен, и одновременное обновление токена не должно случиться),
# снимком (MERGE по ключу, loaded_at — время прогона; исчезнувшая у TikTok строка остаётся со старым loaded_at):
# - склады (logistics/202309/warehouses) — без адреса и контакта: из адреса только регион и страна;
# - варианты доставки склада и перевозчики каждого варианта (fulfillment: как отгружаются заказы);
# - дерево категорий для локали es-ES (product/202309/categories);
# - категория каждого нашего товара (карточка товара GET product/202309/products/{id}: цепочка категорий);
# - атрибуты и правила только для листовых категорий наших товаров (обязательные поля и сертификаты для листинга).
# Отгрузки по заказам (посылки, трекинг) здесь не грузятся: в них адрес покупателя и номер отслеживания.
# Пульс — последним, безусловно; сбои — падение после пульса. dry_run=1 — без записи и пульса.
# Источник — nb/tiktok_reference_loader.py в kabinet-dashboard.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.118.0" requests psycopg2-binary -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import datetime as dt
import os
import sys

import psycopg2
from databricks.sdk import WorkspaceClient

_nb_dir = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
sys.path.insert(0, "/Workspace" + _nb_dir)
import tiktok_client as tt
import tiktok_reference_rows as rr

JOB_NAME = "Kabinet - TikTok Shop Reference Loader"
SCHEMA = "dnipro_m.tiktok"
LOCALE = "es-ES"                     # магазин ES; локаль — для названий категорий и атрибутов
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
spark.conf.set("spark.sql.session.timeZone", "UTC")
w = WorkspaceClient()


def pg():
    cred = w.postgres.generate_database_credential(endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=w.current_user.me().user_name, password=cred.token,
                            sslmode="require")


errors, stats = [], {}
loaded_at = dt.datetime.now(dt.timezone.utc)


def merge(table, keys, rows):
    bad = [r for r in rows if not rr.has_keys(r, keys)]
    if bad:
        errors.append(f"{table}: {len(bad)} строк без ключа {keys} — пропущены")
        rows = [r for r in rows if rr.has_keys(r, keys)]
    if not rows:
        return 0
    uniq = {tuple(r[k] for k in keys): r for r in rows}
    if DRY:
        stats[table] = stats.get(table, 0) + len(uniq)
        return len(uniq)
    schema = spark.table(f"{SCHEMA}.{table}").schema
    df = spark.createDataFrame([tuple(r.get(f.name) for f in schema.fields) for r in uniq.values()], schema)
    view = f"src_{table}"
    df.createOrReplaceTempView(view)
    on = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    spark.sql(f"MERGE INTO {SCHEMA}.{table} t USING {view} s ON {on} "
              f"WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
    stats[table] = stats.get(table, 0) + len(uniq)        # в заметку пульса — только записанное
    return len(uniq)


client = tt.TikTokClient.from_databricks(dbutils)
shops = client.get_authorized_shops()
print(f"магазинов: {len(shops)}; dry_run={int(DRY)}; локаль категорий {LOCALE}")

for shop in shops:
    sid, label, q = shop["id"], f"{shop.get('region')}/{shop['id']}", {"shop_cipher": shop["cipher"]}

    # склады → варианты доставки → перевозчики
    try:
        whs = client.call("GET", "/logistics/202309/warehouses", q).get("warehouses") or []
        merge("raw_warehouses", ("shop_id", "warehouse_id"), [rr.warehouse_row(shop, x, loaded_at) for x in whs])
        opts, provs = [], []
        for wh in whs:
            try:
                for d in client.call("GET", f"/logistics/202309/warehouses/{wh['id']}/delivery_options", q).get("delivery_options") or []:
                    opts.append(rr.delivery_option_row(shop, wh["id"], d, loaded_at))
            except Exception as e:
                errors.append(f"{label} варианты доставки склада {wh.get('id')}: {str(e)[:200]}")
        for opt_id in sorted({o["delivery_option_id"] for o in opts if o.get("delivery_option_id")}):
            try:
                for p in client.call("GET", f"/logistics/202309/delivery_options/{opt_id}/shipping_providers", q).get("shipping_providers") or []:
                    provs.append(rr.shipping_provider_row(shop, opt_id, p, loaded_at))
            except Exception as e:
                errors.append(f"{label} перевозчики варианта {opt_id}: {str(e)[:200]}")
        merge("raw_delivery_options", ("shop_id", "warehouse_id", "delivery_option_id"), opts)
        merge("raw_shipping_providers", ("shop_id", "delivery_option_id", "provider_id"), provs)
        print(f"{label}: складов {len(whs)}, вариантов доставки {len(opts)}, перевозчиков {len(provs)}")
    except Exception as e:
        errors.append(f"{label} логистика: {str(e)[:300]}")

    # дерево категорий
    try:
        cats = client.call("GET", "/product/202309/categories", {**q, "locale": LOCALE}).get("categories") or []
        merge("raw_categories", ("shop_id", "locale", "category_id"), [rr.category_row(shop, LOCALE, c, loaded_at) for c in cats])
        print(f"{label}: категорий {len(cats)}")
    except Exception as e:
        errors.append(f"{label} категории: {str(e)[:300]}")

    # категории наших товаров (кроме удалённых) → атрибуты и правила их листовых категорий
    try:
        pids = [r["product_id"] for r in spark.sql(
            f"SELECT product_id FROM {SCHEMA}.raw_products WHERE shop_id = :sid AND coalesce(status, '') <> 'DELETED'",
            args={"sid": sid}).collect()]
        prow = []
        for pid in pids:
            try:
                chain = client.call("GET", f"/product/202309/products/{pid}", q).get("category_chains") or []
                prow.append(rr.product_category_row(shop, pid, chain, loaded_at))
            except Exception as e:
                errors.append(f"{label} категория товара {pid}: {str(e)[:200]}")
        merge("raw_product_categories", ("shop_id", "product_id"), prow)
        leaves = sorted({r["category_id"] for r in prow if r.get("category_id")})
        attrs, rules = [], []
        for cid in leaves:
            try:
                for a in client.call("GET", f"/product/202309/categories/{cid}/attributes", {**q, "locale": LOCALE}).get("attributes") or []:
                    attrs.append(rr.attribute_row(shop, cid, a, loaded_at))
                rules.append(rr.rules_row(shop, cid, client.call("GET", f"/product/202309/categories/{cid}/rules", {**q, "locale": LOCALE}), loaded_at))
            except Exception as e:
                errors.append(f"{label} атрибуты и правила категории {cid}: {str(e)[:200]}")
        merge("raw_category_attributes", ("shop_id", "category_id", "attribute_id"), attrs)
        merge("raw_category_rules", ("shop_id", "category_id"), rules)
        print(f"{label}: товаров {len(prow)}, листовых категорий {len(leaves)}, атрибутов {len(attrs)}")
    except Exception as e:
        errors.append(f"{label} категории товаров: {str(e)[:300]}")

if not shops:
    errors.append("Get Authorized Shops вернул пустой список")

# Пульс — последним и безусловно (в той же ячейке); сбои — падение после него
note = (f"магазинов {len(shops)}; " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items()))
        + (f"; сбоев {len(errors)}" if errors else ""))[:500]
if DRY:
    print("dry_run: пульс не пишется —", note)
else:
    _c = pg()
    try:
        with _c.cursor() as _cur:
            # порог ожидания — только в job_health_rules (192 ч, sql/tiktok_reference_2026-10-26.sql, часть B): в пульс
            # NULL, а не своя константа; сводка и сторож берут порог из правила (AGENTS.md, «Пороги и правила живут в БД»)
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
