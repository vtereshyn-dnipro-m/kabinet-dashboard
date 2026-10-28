# Databricks notebook source
# DBTITLE 1,Kabinet - Price Parity: цены каналов → kabinet_data.price_parity
# Kabinet - Price Parity (28.10.2026, T-37, вариант 3 — решение владельца 28.10.2026). Раньше паритет собирала ячейка 6
# `Kabinet - Economics Loader` раз в сутки (12:30) из утреннего снимка офферов, и цена LM и CF бралась как
# coalesce(discount_price, price) без срока скидки: 27.10.2026 LM весь день показывал цену паузы между акциями (129 €
# вместо 48,99/57,99), а Carrefour — скидку, кончившуюся 25.10. Теперь:
# - паритет собирается после каждой загрузки офферов (08:20, 10:20, 16:20 Киев: LM 08:00 и 16:00, MM 09:30, CF 09:45);
# - цена LM и CF — по сроку скидки на момент сборки (nb/price_parity_rows.py); закончившаяся скидка не берётся;
# - пауза между акциями (скидки нет, но была недавно: срок кончился меньше parity_promo_pause_days назад или скидка
#   была в истории снимков LM) — цена как есть, канал в promo_pause_channels, выбросом строку из-за него не считаем.
# Цены Amazon — как прежде, из витрины Listing Suite (listing_latest по product_matrix, вариант — по seller_sku из
# sku_asin_map). Ячейка 6 Economics Loader после выкладки этой джобы паритет не пишет (патч nb/patches/…_Economics_Loader).
# Хосты баз и учётка в коде не зашиты: хост — из описания endpoint Lakebase, пользователь — тот, под кем идёт джоба.
# Запись — upsert по norm_sku и удаление только тех SKU, которых в сборке больше нет (не всей таблицы); если сборка
# заметно меньше прежней (источник ответил не полностью) — удаление пропускается, сбой — в пульс. Пульс
# `Kabinet - Price Parity` — последним и безусловно, сбои роняют прогон после него. dry_run=1 — без записи и без пульса.
# Источник кода — nb/price_parity.py в kabinet-dashboard.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.118.0" psycopg2-binary -q
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
import price_parity_rows as pr

JOB_NAME = "Kabinet - Price Parity"
KABINET_EP = "projects/kabinet-dashboard/branches/production/endpoints/primary"
LISTING_EP = "projects/listing-suite/branches/production/endpoints/primary"
dbutils.widgets.text("dry_run", "0")
DRY = dbutils.widgets.get("dry_run").strip() == "1"
w = WorkspaceClient()
_user = w.current_user.me().user_name


def connect(endpoint):
    """Подключение к Lakebase: хост — из описания endpoint, пароль — временный токен, пользователь — тот, под кем идёт джоба."""
    host = w.postgres.get_endpoint(name=endpoint).status.hosts.host
    cred = w.postgres.generate_database_credential(endpoint=endpoint)
    return psycopg2.connect(host=host, port=5432, dbname="databricks_postgres", user=_user, password=cred.token,
                            sslmode="require")


errors, stats = [], {}
now = dt.datetime.now(dt.timezone.utc)

# 1. Настройка и цены каналов Кабинета (Lakebase)
_c = connect(KABINET_EP)
try:
    with _c.cursor() as cur:
        cur.execute("""SELECT key, value FROM kabinet_data.reorder_params
                       WHERE key IN ('parity_promo_pause_days', 'parity_shrink_guard_pct')""")
        _p = {k: v for k, v in cur.fetchall()}
        _miss = [k for k in ("parity_promo_pause_days", "parity_shrink_guard_pct") if k not in _p]
        if _miss:
            raise RuntimeError(f"в reorder_params нет {_miss} — сначала SQL sql/price_parity_promo_2026-10-28.sql")
        PAUSE_DAYS = int(_p["parity_promo_pause_days"])
        # сборка меньше этой доли прежней — пропавшие SKU не удаляем (источник ответил не весь)
        SHRINK_GUARD = float(_p["parity_shrink_guard_pct"]) / 100
        cur.execute("SELECT sku, marketplace_code, price FROM kabinet_data.raw_mm_offers WHERE offer_is_online = true AND price > 0")
        mm_rows = cur.fetchall()
        cur.execute("""SELECT shop_sku, price, origin_price, discount_price, discount_start, discount_end
                       FROM kabinet_data.raw_lm_offers WHERE active = true AND quantity > 0""")
        lm_rows = cur.fetchall()
        cur.execute("""SELECT shop_sku, price, origin_price, discount_price, discount_start, discount_end
                       FROM kabinet_data.raw_cf_offers WHERE active = true AND quantity > 0""")
        cf_rows = cur.fetchall()
        # ASIN → seller_sku: отсюда ключ варианта для амазоновских цен
        cur.execute("""SELECT asin, lower(marketplace), seller_sku FROM kabinet_data.sku_asin_map
                       WHERE asin IS NOT NULL AND seller_sku IS NOT NULL""")
        asin_sku = {}
        for a, m, s in cur.fetchall():
            asin_sku.setdefault((a, m), []).append(s)
        cur.execute("SELECT count(*) FROM kabinet_data.price_parity")
        prev_count = cur.fetchone()[0]
finally:
    _c.close()

# 2. Цены Amazon (Listing Suite) — как в прежней ячейке 6
_c = connect(LISTING_EP)
try:
    with _c.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ll.asin, ll.marketplace, COALESCE(ll.display_price, ll.list_price) AS price, ll.title
            FROM listing_data.product_matrix pm
            JOIN listing_data.listing_latest ll ON pm.asin = ll.asin AND pm.marketplace = ll.marketplace
            WHERE COALESCE(ll.display_price, ll.list_price) > 0 AND NOT pm.is_competitor""")
        amz_rows = cur.fetchall()
finally:
    _c.close()

# 3. Недавние скидки LM из истории снимков: LM в паузе очищает поля скидки, и пауза видна только по истории
recent_lm = set()
try:
    recent_lm = {r["shop_sku"] for r in spark.sql(
        f"""SELECT DISTINCT shop_sku FROM dnipro_m.kabinet_data.raw_lm_offers_history
            WHERE discount_price IS NOT NULL AND snapshot_date >= date_sub(current_date(), {PAUSE_DAYS})""").collect()}
except Exception as e:
    errors.append(f"история скидок LM: {type(e).__name__}: {str(e)[:200]}")
print(f"Amazon {len(amz_rows)} · MM {len(mm_rows)} · LM {len(lm_rows)} · CF {len(cf_rows)} · ASIN→SKU {len(asin_sku)} · "
      f"LM со скидкой за {PAUSE_DAYS} дн {len(recent_lm)}")


def _amz_key(asin, mp):
    keys = sorted({k for k in (pr.norm_sku(s) for s in asin_sku.get((asin, mp), [])) if k}, key=len)
    return keys[0] if keys else None


MP = {"es": "amz_es", "fr": "amz_fr", "de": "amz_de", "it": "amz_it", "co.uk": "amz_gb"}
MM = {"MM-ES": "mm_es", "MM-FR": "mm_fr"}
D, PAUSED = {}, {}
for asin, mp, price, title in amz_rows:
    ns, ch = _amz_key(asin, mp), MP.get(mp)
    if ns and ch:
        D.setdefault(ns, {})[ch] = float(price)
        if title:
            D[ns].setdefault("t", title)
for sku, mc, price in mm_rows:
    ns, ch = pr.norm_sku(sku), MM.get(mc)
    if ns and ch:
        D.setdefault(ns, {})[ch] = float(price)
for col, rows_, recent in (("lm_es", lm_rows, recent_lm), ("cf_es", cf_rows, set())):
    n_promo = n_pause = 0
    for sku, price, origin, disc, d_start, d_end in rows_:
        ns = pr.norm_sku(sku)
        if not ns:
            continue
        p, active = pr.mirakl_price(price, origin, disc, d_start, d_end, now)
        if not p:
            continue
        D.setdefault(ns, {})[col] = p
        n_promo += active
        if pr.in_pause(active, d_end, now, str(sku).strip() in recent, PAUSE_DAYS):
            PAUSED.setdefault(ns, set()).add(col)
            n_pause += 1
    stats[f"{col}_promo"], stats[f"{col}_pause"] = n_promo, n_pause

rows = [r for r in (pr.parity_row(ns, d, PAUSED.get(ns, set())) for ns, d in D.items()) if r]
stats["rows"] = len(rows)
print(f"строк {len(rows)} (было {prev_count}); " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))

# 4. Запись: upsert по norm_sku; пропавшие SKU — удаление по списку, и только если сборка не «обвалилась»
COLS = ["norm_sku", "product_name", *pr.PCOLS, "min_price", "max_price", "max_deviation_pct", "channels_count",
        "outlier_channels", "promo_pause_channels"]
if DRY:
    print("dry_run: в таблицу не пишется")
elif not rows:
    errors.append("сборка пустая — таблица не тронута")
else:
    _c = connect(KABINET_EP)
    try:
        with _c.cursor() as cur:
            upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLS if c != "norm_sku") + ", updated_at = now()"
            execute_values(cur, f"INSERT INTO kabinet_data.price_parity ({', '.join(COLS)}) VALUES %s "
                                f"ON CONFLICT (norm_sku) DO UPDATE SET {upd}",
                           [tuple(r[c] for c in COLS) for r in rows], page_size=500)
            if prev_count and len(rows) < prev_count * SHRINK_GUARD:
                errors.append(f"сборка {len(rows)} строк против {prev_count} прежних — пропавшие SKU не удалены")
            else:
                cur.execute("DELETE FROM kabinet_data.price_parity WHERE NOT (norm_sku = ANY(%s))",
                            ([r["norm_sku"] for r in rows],))
                stats["removed"] = cur.rowcount
        _c.commit()
    except Exception as e:
        _c.rollback()
        errors.append(f"запись price_parity: {type(e).__name__}: {str(e)[:200]}")
    finally:
        _c.close()

# Пульс — последним и безусловно; сбои — падение после него
note = (", ".join(f"{k} {v}" for k, v in sorted(stats.items())) + (f"; сбоев {len(errors)}" if errors else ""))[:500]
if DRY:
    print("dry_run: пульс не пишется —", note)
else:
    _c = connect(KABINET_EP)
    try:
        with _c.cursor() as cur:
            cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
                           VALUES (%s, now(), %s, NULL)
                           ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                        (JOB_NAME, note))
        _c.commit()
    finally:
        _c.close()
    print(f"💓 {JOB_NAME}: {note}")
if errors:
    raise RuntimeError(f"{JOB_NAME}: сбоев {len(errors)}: " + " | ".join(errors)[:900])
