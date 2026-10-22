# Databricks notebook source
# DBTITLE 1,Kabinet - TikTok Shop Analytics Loader: аналитика магазина, товаров, SKU, видео и эфиров → dnipro_m.tiktok
# Kabinet - TikTok Shop Analytics Loader (22.10.2026, группа 1 плана «все группы TikTok API на чтение», решение
# владельца; docs/tiktok-shop.md).
#
# Только GET: клиент (tiktok_client.py рядом) вызывает только пути белого списка. По каждому магазину, ПО ДНЯМ
# (дата — в часовом поясе магазина, до latest_available_date из ответа):
# - магазин — GMV, заказы, штуки, покупатели, трафик (shop/performance, granularity 1D, куском до 30 дней);
# - товары и SKU — метрики за день (shop_products/performance, shop_skus/performance);
# - видео — метрики за день и товары видео с продажами в этот день (shop_videos/…);
# - эфиры — сессии трёх типов аккаунтов (у ES в API нет «ALL»: OFFICIAL, AFFILIATE, MARKETING), сессия — строка с
#   итогами, перечитывается окнами не длиннее 60 дней; товары эфира — одним запросом без дат и страниц, только у
#   официальных и маркетинговых аккаунтов (у эфиров аффилиатов API товаров не отдаёт); сбой товаров одного эфира —
#   в сбои прогона, но сессии окна пишутся.
# Оценка магазина (SPS) не грузится: для региона ES API её не отдаёт (проба 22.10.2026, код 38011502).
#
# Продолжение — по отметке dnipro_m.tiktok.sync_state (поток analytics_*: конец последнего ЦЕЛИКОМ записанного дня)
# минус tiktok_analytics_overlap_days: TikTok дописывает атрибуцию задним числом. Первый запуск —
# tiktok_history_days назад (API держит около года). На первом сбойном дне поток останавливается.
# Креаторы — только creator_id и публичный ник (tiktok_analytics_rows.py). Пульс — последним, безусловно; сбои —
# падение после пульса. dry_run=1 — без записи и пульса; full=1 — заново с глубины первого запуска.
# Пока #364 не применён — без расписания, прогоны владелец запускает руками. Источник кода —
# nb/tiktok_analytics_loader.py в kabinet-dashboard.

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
import tiktok_analytics_rows as ar
import tiktok_client as tt

JOB_NAME = "Kabinet - TikTok Shop Analytics Loader"
SCHEMA = "dnipro_m.tiktok"
ACCOUNT_TYPES = ("OFFICIAL_ACCOUNTS", "AFFILIATE_ACCOUNTS", "MARKETING_ACCOUNTS")
LIVE_PRODUCTS_FOR = ("OFFICIAL_ACCOUNTS", "MARKETING_ACCOUNTS")   # товары эфира API отдаёт только для этих аккаунтов
dbutils.widgets.text("dry_run", "0")
dbutils.widgets.text("full", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
FULL = dbutils.widgets.get("full").strip() == "1"
spark.conf.set("spark.sql.session.timeZone", "UTC")
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
_need = ("tiktok_history_days", "tiktok_analytics_overlap_days")
_missing = [k for k in _need if k not in settings]
if _missing:
    raise RuntimeError(f"в reorder_params нет {_missing} — сначала SQL sql/tiktok_analytics_2026-10-22.sql")
HISTORY, OVL = (settings[k] for k in _need)

errors, stats = [], {}
loaded_at = dt.datetime.now(dt.timezone.utc)
today = dt.date.today()


def merge(table, keys, rows):
    bad = [r for r in rows if not ar.has_keys(r, keys)]
    if bad:
        errors.append(f"{table}: {len(bad)} строк без ключа {keys} — пропущены")
        rows = [r for r in rows if ar.has_keys(r, keys)]
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


def start_day(stream, shop_id):
    first = today - dt.timedelta(days=HISTORY)
    if FULL:
        return first
    row = spark.sql(f"SELECT cast(done_until AS date) AS d FROM {SCHEMA}.sync_state WHERE shop_id = :sid AND stream = :st",
                    args={"sid": shop_id, "st": stream}).first()
    if not row or row["d"] is None:
        return first
    return max(row["d"] - dt.timedelta(days=OVL), first)


def mark_done(stream, shop_id, until_day):
    merge("sync_state", ("shop_id", "stream"),
          [{"shop_id": shop_id, "stream": stream,
            "done_until": dt.datetime.combine(until_day, dt.time(), tzinfo=dt.timezone.utc), "updated_at": loaded_at}])


def q_range(q, d0, d1, **extra):
    return {**q, "start_date_ge": d0.isoformat(), "end_date_lt": d1.isoformat(), **extra}


client = tt.TikTokClient.from_databricks(dbutils)
shops = client.get_authorized_shops()
print(f"магазинов: {len(shops)}; dry_run={int(DRY)} full={int(FULL)}; история {HISTORY} сут, перекрытие {OVL}")

for shop in shops:
    sid, q = shop["id"], {"shop_cipher": shop["cipher"]}
    label = f"{shop.get('region')}/{sid}"
    try:
        probe = client.call("GET", "/analytics/202609/shop/performance",
                            q_range(q, today - dt.timedelta(days=2), today, granularity="1D"))
        end = ar.day(probe.get("latest_available_date")) + dt.timedelta(days=1)   # [.., end) — последний готовый день включительно
    except Exception as e:
        errors.append(f"{label} аналитика: нет latest_available_date — {str(e)[:300]}")
        continue
    print(f"{label}: данные аналитики по {end - dt.timedelta(days=1)}")

    # магазин по дням — кусками до 30 дней
    try:
        d0 = start_day("analytics_shop", sid)
        n = 0
        while d0 < end:
            d1 = min(d0 + dt.timedelta(days=30), end)
            data = client.call("GET", "/analytics/202609/shop/performance", q_range(q, d0, d1, granularity="1D"))
            rows = [ar.shop_day_row(shop, iv, loaded_at) for iv in (data.get("performance") or {}).get("intervals") or []]
            n += merge("raw_analytics_shop_daily", ("shop_id", "date"), rows)
            mark_done("analytics_shop", sid, d1)
            d0 = d1
        print(f"{label}: магазин, дней {n}")
    except Exception as e:
        errors.append(f"{label} магазин: {str(e)[:300]}")

    # товары, SKU, видео — день за днём; поток останавливается на первом сбойном дне
    for stream, fn in (("analytics_products", "products"), ("analytics_skus", "skus"), ("analytics_videos", "videos")):
        try:
            d0 = start_day(stream, sid)
        except Exception as e:
            errors.append(f"{label} {fn}: отметка sync_state — {str(e)[:300]}")
            continue
        n = 0
        for d in ar.days(d0, end):
            nxt = d + dt.timedelta(days=1)
            try:
                if fn == "products":
                    rows = [ar.product_day_row(shop, d, p, loaded_at) for p in client.pages(
                        "GET", "/analytics/202605/shop_products/performance", "products", q_range(q, d, nxt), page_size=50)]
                    n += merge("raw_analytics_product_daily", ("shop_id", "date", "product_id"), rows)
                elif fn == "skus":
                    rows = [ar.sku_day_row(shop, d, s, loaded_at) for s in client.pages(
                        "GET", "/analytics/202509/shop_skus/performance", "skus", q_range(q, d, nxt), page_size=100)]
                    n += merge("raw_analytics_sku_daily", ("shop_id", "date", "sku_id"), rows)
                else:
                    vids = list(client.pages("GET", "/analytics/202605/shop_videos/performance", "videos",
                                             q_range(q, d, nxt), page_size=50))
                    vprods = []
                    for v in vids:
                        if (ar.integer(v.get("items_sold")) or 0) > 0:
                            for p in client.pages("GET", f"/analytics/202509/shop_videos/{v['id']}/products/performance",
                                                  "products", q_range(q, d, nxt), page_size=50):
                                vprods.append(ar.video_product_day_row(shop, d, v["id"], p, loaded_at))
                    merge("raw_analytics_video_product_daily", ("shop_id", "date", "video_id", "product_id"), vprods)
                    n += merge("raw_analytics_video_daily", ("shop_id", "date", "video_id"),
                               [ar.video_day_row(shop, d, v, loaded_at) for v in vids])
                mark_done(stream, sid, nxt)
            except Exception as e:
                errors.append(f"{label} {fn}, день {d}: {str(e)[:300]}")
                break
            time.sleep(0.2)
        print(f"{label}: {fn}, строк {n}")

    # эфиры — сессии окнами до 60 дней, три типа аккаунтов
    try:
        d0 = start_day("analytics_lives", sid)
        n = 0
        while d0 < end:
            d1 = min(d0 + dt.timedelta(days=59), end)
            rows, lprods = [], []
            for at in ACCOUNT_TYPES:
                for s in client.pages("GET", "/analytics/202609/shop_lives/performance", "live_stream_sessions",
                                      q_range(q, d0, d1, account_type=at), page_size=50):
                    rows.append(ar.live_row(shop, at, s, loaded_at))
                    if at in LIVE_PRODUCTS_FOR and (ar.integer((s.get("sales_performance") or {}).get("products_sold")) or 0) > 0:
                        try:
                            data = client.call("GET", f"/analytics/202512/shop/{s['id']}/products_performance", q)
                            lprods += [ar.live_product_row(shop, s["id"], p, loaded_at) for p in data.get("products") or []]
                        except Exception as e:
                            errors.append(f"{label} товары эфира {s.get('id')}: {str(e)[:200]}")
            merge("raw_analytics_live_products", ("shop_id", "live_id", "product_id"), lprods)
            n += merge("raw_analytics_lives", ("shop_id", "live_id"), rows)
            mark_done("analytics_lives", sid, d1)
            d0 = d1
        print(f"{label}: эфиров {n}")
    except Exception as e:
        errors.append(f"{label} эфиры: {str(e)[:300]}")

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
