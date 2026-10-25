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
#   отметки последнего ЦЕЛИКОМ записанного куска минус tiktok_order_overlap_days (статусы и отмены меняются задним
#   числом); заказ и его строки;
# - товары — снимок целиком (поиск со статусом ALL; SKU, цены и остатки приходят в нём же);
# - выписки — по statement_time так же, перекрытие tiktok_finance_overlap_days (payment_status меняется после
#   выписки); по каждой выписке — её операции.
# Продолжение — по отметке `dnipro_m.tiktok.sync_state` (магазин × поток → done_until — конец последнего куска,
# записанного целиком), а НЕ по max(update_time): TikTok отдаёт update_time и за пределами запрошенного диапазона, и
# после сбоя в середине первого прогона max перепрыгнул бы дыру. На первом сбойном куске поток останавливается —
# следующий прогон начнёт с него. Запись — MERGE по ключу, по частям; строки и операции — раньше заголовков и выписок. Персональные данные покупателей срезаются до записи
# (tiktok_rows.py); для повторных покупок — buyer_hash = sha256(соль + user_id), соль — tiktok-shop/buyer-salt.
# Настройки — kabinet_data.reorder_params (tiktok_*), не константы.
#
# Реплика для страниц Кабинета (с 22.10.2026): после сырья — kabinet_data.raw_tiktok_orders / _order_lines /
# _finance_tx в Lakebase, upsert по ключу из таблиц сырья целиком (их немного), только колонки страницы, без raw_json.
# Пульс `Kabinet - TikTok Shop Loader` — последним, безусловно; в заметке пульса — срок access-токена и было ли
# обновление (их читает утренняя сводка, секрета она не касается). Сбои копятся и роняют прогон ПОСЛЕ пульса.
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
import re
import sys
import time

import psycopg2
from psycopg2.extras import execute_values
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
spark.conf.set("spark.sql.session.timeZone", "UTC")      # чтение и вывод TIMESTAMP — в UTC
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
loaded_at = dt.datetime.now(dt.timezone.utc)                  # aware UTC: Spark переводит его верно


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


def start_from(stream, shop_id, overlap_days):
    """Начало чтения: отметка done_until минус перекрытие; нет отметки или full=1 — глубина первого запуска."""
    if FULL:
        return now - HISTORY * 86400
    row = spark.sql(f"SELECT unix_timestamp(done_until) AS u FROM {SCHEMA}.sync_state "
                    f"WHERE shop_id = :sid AND stream = :st", args={"sid": shop_id, "st": stream}).first()
    if not row or row["u"] is None:
        return now - HISTORY * 86400
    return max(int(row["u"]) - overlap_days * 86400, now - HISTORY * 86400)


def mark_done(stream, shop_id, until):
    """Кусок записан целиком — отметка продолжения сдвигается на его конец."""
    merge("sync_state", ("shop_id", "stream"),
          [{"shop_id": shop_id, "stream": stream, "done_until": dt.datetime.fromtimestamp(until, tz=dt.timezone.utc),
            "updated_at": loaded_at}])


client = tt.TikTokClient.from_databricks(dbutils)
try:                                         # срок ДО первого запроса: обновление токена делает именно он
    EXP_BEFORE = client.expiries()
except Exception:
    EXP_BEFORE = {}
try:
    SALT = dbutils.secrets.get(tt.SCOPE, "buyer-salt")      # значение не печатается
except Exception as e:
    _salt_err = str(e)
    SALT = None
    if not re.search(r"does not exist|not found|RESOURCE_DOES_NOT_EXIST", _salt_err, re.I):
        raise PermissionError(f"скоуп {tt.SCOPE}, ключ buyer-salt: чтение не удалось — {_salt_err[:200]}")
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

    # заказы: кусок за куском; первый сбойный кусок останавливает поток, отметка остаётся на последнем целом
    try:
        t0 = start_from("orders", sid, ORD_OVL)
    except Exception as e:                       # сбой чтения отметки — поток пропускаем, остальное идёт дальше
        errors.append(f"{label} заказы, отметка sync_state: {str(e)[:300]}")
        t0 = now
    n_orders = 0
    for a, b in tr.windows(t0, now, WIN):
        try:
            heads, lines = [], []
            for order in client.pages("POST", "/order/202309/orders/search", "orders",
                                      {**q, "sort_field": "update_time", "sort_order": "ASC"},
                                      {"update_time_ge": a, "update_time_lt": b}, page_size=100):
                h, ls = tr.order_rows(shop, order, loaded_at, SALT)
                heads.append(h)
                lines.extend(ls)
            merge("raw_order_lines", ("shop_id", "line_item_id"), lines)
            n_orders += merge("raw_orders", ("shop_id", "order_id"), heads)
            mark_done("orders", sid, b)
        except Exception as e:
            errors.append(f"{label} заказы, кусок с {tt.fmt_ts(a)}: {str(e)[:300]}")
            break
    print(f"{label}: заказов {n_orders} с {tt.fmt_ts(t0)}")

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

    # выписки и их операции — так же, по кускам с отметкой
    try:
        t0 = start_from("statements", sid, FIN_OVL)
    except Exception as e:
        errors.append(f"{label} финансы, отметка sync_state: {str(e)[:300]}")
        t0 = now
    n_st = n_tr = 0
    for a, b in tr.windows(t0, now, WIN):
        try:
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
            mark_done("statements", sid, b)
        except Exception as e:
            errors.append(f"{label} финансы, кусок с {tt.fmt_ts(a)}: {str(e)[:300]}")
            break
    print(f"{label}: выписок {n_st}, операций {n_tr} с {tt.fmt_ts(t0)}")

if not shops:
    errors.append("Get Authorized Shops вернул пустой список")

# Раскладка комиссий операции (решение владельца 25.10.2026) — из fee_tax_breakdown в raw_json сырья: комиссия TikTok
# (platform_commission_amount), комиссия аффилиатов (affiliate_commission_amount + affiliate_ads_commission_amount +
# affiliate_partner_commission_amount) и прочие сборы — остаток до fee_tax_amount (на 25.10.2026 это Smart Promotion и
# EPR), так что три колонки в сумме всегда равны fee_tax_amount. Нет разбивки в ответе — все три NULL, а не 0.
_FB = "get_json_object(t.raw_json, '$.fee_tax_breakdown.fee.{}')"
_HAS_FB = "get_json_object(t.raw_json, '$.fee_tax_breakdown') IS NOT NULL"
_TT_FEE = f"coalesce(cast({_FB.format('platform_commission_amount')} AS decimal(18,2)), 0)"
_AFF_FEE = " + ".join(f"coalesce(cast({_FB.format(k)} AS decimal(18,2)), 0)" for k in
                      ("affiliate_commission_amount", "affiliate_ads_commission_amount", "affiliate_partner_commission_amount"))
FEE_SPLIT = (f"CASE WHEN {_HAS_FB} THEN {_TT_FEE} END AS commission_tiktok, "
             f"CASE WHEN {_HAS_FB} THEN {_AFF_FEE} END AS commission_affiliate, "
             f"CASE WHEN {_HAS_FB} THEN t.fee_tax_amount - {_TT_FEE} - ({_AFF_FEE}) END AS fee_other")

# Реплика в Lakebase для страниц — из таблиц сырья целиком, upsert по ключу
REPLICA = (
    ("raw_tiktok_orders", ("shop_id", "order_id"),
     f"""SELECT shop_id, order_id, region, status, create_time, update_time, is_sample_order, currency,
                original_total_product_price, seller_discount, platform_discount, sub_total, total_amount
         FROM {SCHEMA}.raw_orders"""),
    ("raw_tiktok_order_lines", ("shop_id", "line_item_id"),
     f"""SELECT shop_id, line_item_id, order_id, sku_id, seller_sku, product_name, currency, original_price, sale_price,
                seller_discount, platform_discount, display_status
         FROM {SCHEMA}.raw_order_lines"""),
    ("raw_tiktok_finance_tx", ("shop_id", "statement_id", "transaction_id"),
     f"""SELECT t.shop_id, t.statement_id, t.transaction_id, t.order_id, t.type, s.statement_time, s.payment_status,
                t.currency, t.revenue_amount, t.fee_tax_amount, t.shipping_cost_amount, t.adjustment_amount,
                t.settlement_amount, {FEE_SPLIT}
         FROM {SCHEMA}.raw_finance_statement_transactions t
         LEFT JOIN {SCHEMA}.raw_finance_statements s ON s.shop_id = t.shop_id AND s.statement_id = t.statement_id"""),
)
for table, keys, select_sql in REPLICA:
    try:
        df = spark.sql(select_sql)
        cols = df.columns
        rows = [tuple(r[c] for c in cols) for r in df.collect()]
        stats[f"lakebase.{table}"] = len(rows)
        if DRY or not rows:
            continue
        upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in keys) + ", loaded_at = now()"
        _c = pg()
        try:
            with _c.cursor() as _cur:
                _cur.execute("SET TIME ZONE 'UTC'")      # время из Spark — UTC без пояса
                execute_values(_cur, f"INSERT INTO kabinet_data.{table} ({', '.join(cols)}) VALUES %s "
                                     f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {upd}", rows, page_size=500)
            _c.commit()
        finally:
            _c.close()
    except Exception as e:
        errors.append(f"реплика {table}: {str(e)[:300]}")

# Пульс — последним и безусловно (в той же ячейке: ячейка самодостаточна); сбои — падение после него
try:
    _exp_now = client.expiries()
    _token = (f"access до {tt.fmt_ts(_exp_now['access_expires'])}"
              + ("; токен обновлён" if EXP_BEFORE.get("access_expires") is not None
                 and _exp_now["access_expires"] != EXP_BEFORE["access_expires"] else ""))
except Exception as e:                       # срок токена — не повод терять пульс
    _token = "срок токена не прочитан"
    errors.append(f"срок токена: {type(e).__name__}")
note = (f"{_token}; магазинов {len(shops)}; " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items()))
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
