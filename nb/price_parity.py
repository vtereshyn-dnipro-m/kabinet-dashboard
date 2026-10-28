# Databricks notebook source
# DBTITLE 1,Kabinet - Price Parity: цены каналов → kabinet_data.price_parity
# Kabinet - Price Parity (28.10.2026, T-37, вариант 3 — решение владельца 28.10.2026). Раньше паритет собирала ячейка 6
# `Kabinet - Economics Loader` раз в сутки (12:30) из утреннего снимка офферов, и цена LM и CF бралась как
# coalesce(discount_price, price) без срока скидки: 27.10.2026 LM весь день показывал цену паузы между акциями (129 €
# вместо 48,99/57,99), а Carrefour — скидку, кончившуюся 25.10. Теперь:
# - паритет собирается после загрузок офферов и снимка SP-API (08:50, 10:50, 16:50 Киев: LM 08:00 и 16:00, MM 09:30,
#   CF 09:45, SP-API ~16:30);
# - цена LM и CF — по сроку скидки на момент сборки (nb/price_parity_rows.py); закончившаяся скидка не берётся;
# - пауза между акциями (скидки нет, но была недавно: срок кончился меньше parity_promo_pause_days назад или скидка
#   была в истории снимков LM) — цена как есть, канал в promo_pause_channels, выбросом строку из-за него не считаем.
# Цены Amazon — из SP-API Listings Items (dnipro_m.raw_amazon_listing_offers, снимок дня по всем рынкам сразу; пишет
# ячейка 1 Kabinet - Plan Matrix Prices ~16:30), по правилам Plan Matrix: только листинг в продаже, меньшая из нашей цены
# и действующей скидки, из двух листингов (FBA и FBM) — меньшая. Раньше — снимки витрины Listing Suite с разными датами
# по рынкам (28.10.2026: 81123011 ES от 21.10, DE от 26.10) и подстановкой рекомендованной цены без цены продажи
# (решение владельца 28.10.2026: «всё должно синхронно быть»). Названия товаров — из sku_master. Ячейка 6 Economics Loader после выкладки этой джобы паритет не пишет (патч nb/patches/…_Economics_Loader).
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
                       WHERE key IN ('parity_promo_pause_days', 'parity_shrink_guard_pct', 'parity_outlier_pct',
                                     'parity_offer_run_window_min', 'parity_amz_snapshot_max_age_h',
                                     'parity_amz_min_markets')""")
        _p = {k: v for k, v in cur.fetchall()}
        _miss = [k for k in ("parity_promo_pause_days", "parity_shrink_guard_pct", "parity_outlier_pct",
                             "parity_offer_run_window_min", "parity_amz_snapshot_max_age_h",
                             "parity_amz_min_markets") if k not in _p]
        if _miss:
            raise RuntimeError(f"в reorder_params нет {_miss} — сначала SQL sql/price_parity_promo_2026-10-28.sql")
        PAUSE_DAYS = int(_p["parity_promo_pause_days"])
        # сборка меньше этой доли прежней — пропавшие SKU не удаляем (источник ответил не весь)
        SHRINK_GUARD = float(_p["parity_shrink_guard_pct"]) / 100
        OUTLIER_PCT = float(_p["parity_outlier_pct"])
        RUN_WINDOW_S = float(_p["parity_offer_run_window_min"]) * 60
        AMZ_MAX_AGE_H = float(_p["parity_amz_snapshot_max_age_h"])
        AMZ_MIN_MARKETS = int(_p["parity_amz_min_markets"])
        cur.execute("SELECT sku, marketplace_code, price FROM kabinet_data.raw_mm_offers WHERE offer_is_online = true AND price > 0")
        mm_rows = cur.fetchall()
        cur.execute("""SELECT shop_sku, price, origin_price, discount_price, discount_start, discount_end, loaded_at
                       FROM kabinet_data.raw_lm_offers WHERE active = true AND quantity > 0""")
        lm_rows = cur.fetchall()
        cur.execute("""SELECT shop_sku, price, origin_price, discount_price, discount_start, discount_end, loaded_at
                       FROM kabinet_data.raw_cf_offers WHERE active = true AND quantity > 0""")
        cf_rows = cur.fetchall()
        cur.execute("SELECT sku, name FROM kabinet_data.sku_master WHERE name IS NOT NULL AND name <> ''")
        names = {pr.norm_sku(s): n for s, n in cur.fetchall() if pr.norm_sku(s)}
        cur.execute("SELECT shop_sku, product_title FROM kabinet_data.raw_lm_offers WHERE product_title IS NOT NULL")
        for s, n in cur.fetchall():
            if pr.norm_sku(s):
                names.setdefault(pr.norm_sku(s), n)
        cur.execute("SELECT count(*) FROM kabinet_data.price_parity")
        prev_count = cur.fetchone()[0]
finally:
    _c.close()

# 2. Цены Amazon — SP-API Listings Items: по каждому рынку его последний снимок. Plan Matrix не трогает рынок, который у
# него упал, — такой рынок берётся из своего последнего снимка, а не выпадает молча; снимок старше
# parity_amz_snapshot_max_age_h или рынков меньше parity_amz_min_markets — сбой (красный прогон после пульса)
_li = spark.sql("""WITH last AS (SELECT marketplace, max(snapshot_date) AS d, max(loaded_at) AS la
                                  FROM dnipro_m.dnipro_m.raw_amazon_listing_offers GROUP BY marketplace)
                     SELECT o.marketplace, o.seller_sku, o.status, o.our_price, o.discounted_price, o.discount_start,
                            o.discount_end, l.d AS snapshot_date, l.la AS snapshot_loaded
                     FROM dnipro_m.dnipro_m.raw_amazon_listing_offers o
                     JOIN last l ON l.marketplace = o.marketplace AND l.d = o.snapshot_date
                     WHERE o.audience = 'ALL'""").collect()
amz_rows = [(r["marketplace"], r["seller_sku"], r["status"], r["our_price"], r["discounted_price"], r["discount_start"],
             r["discount_end"]) for r in _li]
_snap = {}
for r in _li:
    _snap[r["marketplace"]] = (r["snapshot_date"], r["snapshot_loaded"])
AMZ_SNAPSHOT = ", ".join(f"{m} {d}" for m, (d, _) in sorted(_snap.items())) or None
for m, (d, la) in sorted(_snap.items()):
    _la = la if la.tzinfo else la.replace(tzinfo=dt.timezone.utc)
    if (now - _la).total_seconds() / 3600 > AMZ_MAX_AGE_H:
        errors.append(f"снимок SP-API Amazon {m} от {d} старше {AMZ_MAX_AGE_H:.0f} ч — цены Amazon {m} устарели")
if len(_snap) < AMZ_MIN_MARKETS:
    errors.append(f"снимок SP-API Amazon — рынков {len(_snap)} ({', '.join(sorted(_snap)) or 'нет'}), "
                  f"ждём не меньше {AMZ_MIN_MARKETS}")

# 3. Недавние скидки LM из истории снимков: LM в паузе очищает поля скидки, и пауза видна только по истории
recent_lm = set()
try:
    recent_lm = {r["shop_sku"] for r in spark.sql(
        f"""SELECT DISTINCT shop_sku FROM dnipro_m.kabinet_data.raw_lm_offers_history
            WHERE discount_price IS NOT NULL AND snapshot_date >= date_sub(current_date(), {PAUSE_DAYS})""").collect()}
except Exception as e:
    errors.append(f"история скидок LM: {type(e).__name__}: {str(e)[:200]}")
print(f"Amazon {len(amz_rows)} (снимок {AMZ_SNAPSHOT}) · MM {len(mm_rows)} · LM {len(lm_rows)} · CF {len(cf_rows)} · "
      f"LM со скидкой за {PAUSE_DAYS} дн {len(recent_lm)}")

MP = {"ES": "amz_es", "FR": "amz_fr", "DE": "amz_de", "IT": "amz_it", "GB": "amz_gb", "UK": "amz_gb"}
MM = {"MM-ES": "mm_es", "MM-FR": "mm_fr"}
D, PAUSED = {}, {}
n_not_buyable = 0
for mp, sku, status, ourp, disc, d_start, d_end in amz_rows:
    ns, ch = pr.norm_sku(sku), MP.get(str(mp).upper())
    if not ns or not ch:
        continue
    p = pr.amazon_price(status, ourp, disc, d_start, d_end, now)
    if p is None:
        n_not_buyable += 1
        continue
    cur_p = D.setdefault(ns, {}).get(ch)
    D[ns][ch] = p if cur_p is None else min(cur_p, p)        # FBA и FBM — меньшая
stats["amz_not_buyable"] = n_not_buyable
if AMZ_SNAPSHOT:
    stats["amz_snapshot"] = AMZ_SNAPSHOT
for sku, mc, price in mm_rows:
    ns, ch = pr.norm_sku(sku), MM.get(mc)
    if ns and ch:
        D.setdefault(ns, {})[ch] = float(price)
for col, rows_, recent in (("lm_es", lm_rows, recent_lm), ("cf_es", cf_rows, set())):
    n_promo = n_pause = 0
    picked = pr.pick_offers(rows_, RUN_WINDOW_S)       # последняя загрузка, один самый свежий оффер на norm_sku
    stats[f"{col}_stale_or_dup"] = len(rows_) - len(picked)
    for ns, (sku, price, origin, disc, d_start, d_end, _la) in picked.items():
        p, active = pr.mirakl_price(price, origin, disc, d_start, d_end, now)
        if not p:
            continue
        D.setdefault(ns, {})[col] = p
        n_promo += active
        if pr.in_pause(active, d_end, now, str(sku).strip() in recent, PAUSE_DAYS):
            PAUSED.setdefault(ns, set()).add(col)
            n_pause += 1
    stats[f"{col}_promo"], stats[f"{col}_pause"] = n_promo, n_pause

for ns, d in D.items():
    if names.get(ns):
        d.setdefault("t", names[ns])
rows = [r for r in (pr.parity_row(ns, d, PAUSED.get(ns, set()), OUTLIER_PCT) for ns, d in D.items()) if r]
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
