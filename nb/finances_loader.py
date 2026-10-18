# Databricks notebook source
# DBTITLE 1,Транзакции Amazon (Finances API v2024-06-19) → сырьё
# ═════════════════════════════════════════════════════════════
# KABINET - AMAZON FINANCES LOADER — каждое движение денег Amazon сразу, не дожидаясь settlement
# Источник: SP-API Finances v2024-06-19, listTransactions (postedAfter / postedBefore, по каждому рынку Amazon).
# Пишет:    dnipro_m.dnipro_m.raw_amazon_finances_transactions — транзакция: тип, статус, дата, рынок, сумма, заказ,
#                                                               отгрузка, settlement, отложенность;
#           dnipro_m.dnipro_m.raw_amazon_finances_breakdowns   — разбивка суммы построчно (путь вида
#                                                               «Sales/ProductCharges/OurPricePrincipal»), на уровне
#                                                               транзакции и позиции (SKU, ASIN, штуки).
# Данные покупателя не храним (решение владельца 18.10.2026): берём только разрешённые поля — суммы, SKU, ASIN,
# номера заказа/отгрузки/settlement. Контекст AddressContext отбрасывается целиком, сырого ответа в таблицах нет.
# Окно: таблица пуста — вся история, которую отдаёт Amazon (не старше двух лет); дальше каждый прогон перечитывает
# последние reorder_params.finances_reread_days (статус транзакции меняется: отложенная → выплаченная) и всё, чего
# ещё нет. Окно заменяется целиком по дате проводки — дублей нет. Блок, в котором упал хоть один запрос, не пишется.
# Квота listTransactions — 0,5 запроса в секунду (запас 10) на аккаунт; кроме нас Finances API не вызывает никто
# (сверка кода всех джоб 18.10.2026). Квоту createReport не трогает.
# Параметры: dry_run=1 — days последних дней без записи; since=ГГГГ-ММ-ДД — перечитать с даты.
# Самодостаточная ячейка: своё подключение, свои константы. Метка пульса — последней и безусловно.
# ═════════════════════════════════════════════════════════════
import datetime as dt
import json
import time
from collections import Counter

import psycopg2
import requests
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import (DateType, DoubleType, IntegerType, StringType, StructField, StructType,
                               TimestampType)

JOB_NAME = "Kabinet - Amazon Finances Loader"
EP = "https://sellingpartnerapi-eu.amazon.com"
T_TX = "dnipro_m.dnipro_m.raw_amazon_finances_transactions"
T_BD = "dnipro_m.dnipro_m.raw_amazon_finances_breakdowns"
CHUNK_DAYS = 14          # отрезок одного запроса postedAfter…postedBefore
BLOCK_DAYS = 30          # блок записи: заменяется целиком или не пишется
PAUSE_SEC = 2.1          # 0,5 запроса в секунду
# только эти идентификаторы транзакции попадают в таблицу — остальное (включая обезличенный номер отгрузки) не нужно
REL_IDS = {"ORDER_ID": "order_id", "SHIPMENT_ID": "shipment_id", "SETTLEMENT_ID": "settlement_id",
           "FINANCIAL_EVENT_GROUP_ID": "financial_event_group_id", "REFUND_ID": "refund_id",
           "DEFERRED_TRANSACTION_ID": "deferred_transaction_id", "RELEASE_TRANSACTION_ID": "release_transaction_id"}

for _n, _d in (("dry_run", "0"), ("days", "2"), ("since", "")):
    try:
        dbutils.widgets.text(_n, _d)
    except Exception:
        pass
DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
PROBE_DAYS = int(dbutils.widgets.get("days").strip() or 2)
SINCE = dbutils.widgets.get("since").strip()

_w = WorkspaceClient()


def pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_w.current_user.me().user_name,
                            password=_w.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token,
                            sslmode="require")


REREAD_DAYS = 30
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""SELECT amazon_id, upper(country) FROM kabinet_data.marketplaces
                    WHERE is_active = true AND amazon_id IS NOT NULL""")
    MARKETS = dict(_cur.fetchall())
    _cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'finances_reread_days'")
    _row = _cur.fetchone()
    if _row and _row[0]:
        REREAD_DAYS = int(_row[0])

NOW = dt.datetime.now(dt.timezone.utc)
END = (NOW - dt.timedelta(minutes=5)).replace(microsecond=0)      # Amazon: postedBefore не позже 2 минут до сейчас
EARLIEST = (NOW - dt.timedelta(days=729)).replace(hour=0, minute=0, second=0, microsecond=0)
if DRY_RUN:
    START = END - dt.timedelta(days=PROBE_DAYS)
elif SINCE:
    START = max(dt.datetime.fromisoformat(SINCE).replace(tzinfo=dt.timezone.utc), EARLIEST)
else:
    last = None
    if spark.catalog.tableExists(T_TX):
        last = spark.sql(f"SELECT max(posted_at) m FROM {T_TX}").collect()[0]["m"]
    if last is None:
        START = EARLIEST
    else:
        last = last.replace(tzinfo=dt.timezone.utc) if last.tzinfo is None else last
        START = min(last, END - dt.timedelta(days=REREAD_DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
print(f"рынков {len(MARKETS)}: {sorted(MARKETS.values())}; окно {START:%Y-%m-%d %H:%M} … {END:%Y-%m-%d %H:%M} UTC"
      + (" (проба, без записи)" if DRY_RUN else ""))

# ── SP-API ──
sec = lambda k: dbutils.secrets.get("amazon-sp-api", k)
_tok = {"v": None, "exp": 0}


def headers():
    if not _tok["v"] or time.time() > _tok["exp"] - 120:
        r = requests.post("https://api.amazon.com/auth/o2/token", timeout=30, data={
            "grant_type": "refresh_token", "refresh_token": sec("refresh-token"),
            "client_id": sec("lwa-app-id"), "client_secret": sec("lwa-client-secret")})
        r.raise_for_status()
        _tok.update(v=r.json()["access_token"], exp=time.time() + int(r.json().get("expires_in", 3600)))
    return {"x-amz-access-token": _tok["v"]}


_last_call = [0.0]


def list_page(params):
    """Одна страница listTransactions. 429 — пауза по Retry-After и до 6 попыток (своя квота, чужим не мешаем)."""
    for attempt in range(6):
        wait = _last_call[0] + PAUSE_SEC - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        r = requests.get(f"{EP}/finances/2024-06-19/transactions", headers=headers(), params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(float(r.headers.get("Retry-After") or 5 * (attempt + 1)), 60))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"listTransactions {r.status_code}: {r.text[:300]}")
        j = r.json()
        return j.get("payload", j)
    raise RuntimeError(f"listTransactions: 429/5xx шесть раз подряд ({r.status_code})")


def money(node):
    try:
        return float(node["currencyAmount"]), node.get("currencyCode")
    except (KeyError, TypeError, ValueError):
        return None, None


def ts(v):
    return dt.datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def flat_breakdowns(bds, path, out, level=1):
    for b in bds or []:
        name = b.get("breakdownType") or "?"
        amt, cur = money(b.get("breakdownAmount"))
        p = f"{path}/{name}" if path else name
        children = b.get("breakdowns") or []
        out.append((p, name, level, amt, cur, not children))
        flat_breakdowns(children, p, out, level + 1)


def parse_tx(t, mk_fallback):
    """Транзакция → строка транзакции и строки разбивки. Только разрешённые поля, AddressContext пропускаем."""
    md = t.get("marketplaceDetails") or {}
    mp_id = md.get("marketplaceId") or (t.get("sellingPartnerMetadata") or {}).get("marketplaceId")
    rel = {REL_IDS[x["relatedIdentifierName"]]: x.get("relatedIdentifierValue")
           for x in t.get("relatedIdentifiers") or [] if x.get("relatedIdentifierName") in REL_IDS}
    deferral = maturity = None
    for c in t.get("contexts") or []:
        if c.get("contextType") == "DeferredContext":
            deferral, maturity = c.get("deferralReason"), c.get("maturityDate")
    total, cur = money(t.get("totalAmount"))
    posted = ts(t.get("postedDate"))
    tid = t.get("transactionId")
    tx = (tid, t.get("transactionType"), t.get("transactionStatus"), t.get("description"), posted,
          posted.date() if posted else None, mp_id, MARKETS.get(mp_id) or mk_fallback, total, cur,
          rel.get("order_id"), rel.get("shipment_id"), rel.get("settlement_id"), rel.get("financial_event_group_id"),
          rel.get("refund_id"), rel.get("deferred_transaction_id"), rel.get("release_transaction_id"),
          deferral, ts(maturity), len(t.get("items") or []))
    rows = []
    fl = []
    flat_breakdowns(t.get("breakdowns"), "", fl)
    for p, name, lvl, amt, bcur, leaf in fl:
        rows.append((tid, posted, None, None, None, None, None, p, name, lvl, leaf, amt, bcur))
    for i, it in enumerate(t.get("items") or []):
        sku = asin = qty = None
        for c in it.get("contexts") or []:
            if c.get("contextType") == "ProductContext":
                sku, asin = c.get("sku"), c.get("asin")
                qty = int(c["quantityShipped"]) if c.get("quantityShipped") is not None else None
        item_total, _ = money(it.get("totalAmount"))
        fl = []
        flat_breakdowns(it.get("breakdowns"), "", fl)
        for p, name, lvl, amt, bcur, leaf in fl:
            rows.append((tid, posted, i, sku, asin, qty, item_total, p, name, lvl, leaf, amt, bcur))
    return tx, rows


TX_SCHEMA = StructType([
    StructField("transaction_id", StringType()), StructField("transaction_type", StringType()),
    StructField("transaction_status", StringType()), StructField("description", StringType()),
    StructField("posted_at", TimestampType()), StructField("posted_date", DateType()),
    StructField("marketplace_id", StringType()), StructField("country", StringType()),
    StructField("total_amount", DoubleType()), StructField("currency", StringType()),
    StructField("order_id", StringType()), StructField("shipment_id", StringType()),
    StructField("settlement_id", StringType()), StructField("financial_event_group_id", StringType()),
    StructField("refund_id", StringType()), StructField("deferred_transaction_id", StringType()),
    StructField("release_transaction_id", StringType()), StructField("deferral_reason", StringType()),
    StructField("maturity_at", TimestampType()), StructField("items_count", IntegerType()),
    StructField("loaded_at", TimestampType())])
BD_SCHEMA = StructType([
    StructField("transaction_id", StringType()), StructField("posted_at", TimestampType()),
    StructField("item_no", IntegerType()), StructField("sku", StringType()), StructField("asin", StringType()),
    StructField("quantity", IntegerType()), StructField("item_total_amount", DoubleType()),
    StructField("breakdown_path", StringType()), StructField("breakdown_type", StringType()),
    StructField("level", IntegerType()), StructField("is_leaf", StringType()),
    StructField("amount", DoubleType()), StructField("currency", StringType()),
    StructField("loaded_at", TimestampType())])
COMMENTS = {T_TX: "Finances API v2024-06-19, listTransactions: транзакция Amazon без данных покупателя. "
                  "Пишет Kabinet - Amazon Finances Loader, окно по posted_at перечитывается целиком.",
            T_BD: "Finances API v2024-06-19: разбивка суммы транзакции построчно (item_no пусто — уровень транзакции). "
                  "Пишет Kabinet - Amazon Finances Loader."}

# ── блоки по 30 дней: внутри — рынки × отрезки по 14 дней, все страницы ──
blocks, b1 = [], START
while b1 < END:
    b2 = min(b1 + dt.timedelta(days=BLOCK_DAYS), END)
    blocks.append((b1, b2))
    b1 = b2
LOADED = dt.datetime.now(dt.timezone.utc)
errors, parts, n_tx, n_bd, calls = [], [], 0, 0, 0
types_cnt, made = Counter(), set()
for b1, b2 in blocks:
    txs, bds, bad = {}, [], []
    for mp_id, mk in sorted(MARKETS.items(), key=lambda x: x[1]):
        c1 = b1
        while c1 < b2:
            c2 = min(c1 + dt.timedelta(days=CHUNK_DAYS), b2)
            params = {"postedAfter": c1.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "postedBefore": c2.strftime("%Y-%m-%dT%H:%M:%SZ"), "marketplaceId": mp_id}
            try:
                while True:
                    pl = list_page(params)
                    calls += 1
                    for t in pl.get("transactions") or []:
                        tid = t.get("transactionId")
                        if not tid or tid in txs:      # транзакция без рынка может прийти под каждым рынком
                            continue
                        tx, rows = parse_tx(t, mk)
                        txs[tid] = tx
                        bds.extend(rows)
                    if not pl.get("nextToken"):
                        break
                    params = {"nextToken": pl["nextToken"]}
            except Exception as e:
                bad.append(f"{mk} {c1:%Y-%m-%d}: {str(e)[:200]}")
            c1 = c2
    if bad:
        errors.append(f"блок {b1:%Y-%m-%d}…{b2:%Y-%m-%d} не записан: " + "; ".join(bad[:2]))
        continue
    n_tx += len(txs)
    n_bd += len(bds)
    types_cnt.update(t[1] for t in txs.values())
    parts.append(f"{b1:%d.%m.%y}…{b2:%d.%m.%y} {len(txs)}")
    if DRY_RUN:
        continue
    for table, schema, data in ((T_TX, TX_SCHEMA, [(*t, LOADED) for t in txs.values()]),
                                (T_BD, BD_SCHEMA, [(*r[:10], "Y" if r[10] else "N", r[11], r[12], LOADED) for r in bds])):
        if table not in made:
            ddl = ", ".join(f"{f.name} {f.dataType.simpleString().upper()}" for f in schema.fields)
            spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({ddl}) USING DELTA COMMENT '{COMMENTS[table]}'")
            made.add(table)
        pred = (f"posted_at >= TIMESTAMP'{b1:%Y-%m-%d %H:%M:%S}' AND posted_at < TIMESTAMP'{b2:%Y-%m-%d %H:%M:%S}'")
        # replaceWhere: блок заменяется атомарно — статусы обновляются, исчезнувшие транзакции уходят, дублей нет
        (spark.createDataFrame(data, schema).write.format("delta").mode("overwrite")
         .option("replaceWhere", pred).saveAsTable(table))

summary = (f"транзакций {n_tx}, строк разбивки {n_bd}, запросов {calls}, блоков {len(blocks)} "
           f"с {START:%d.%m.%Y}; типы {dict(types_cnt.most_common(6))}"
           + (f" | ⚙️ сбои: {'; '.join(errors[:3])}" if errors else ""))
print("📊 " + summary)
if DRY_RUN:
    dbutils.notebook.exit(json.dumps({"summary": summary, "errors": errors, "blocks": parts}, ensure_ascii=False))

# ── SYSTEM PULSE: безусловно, последним ──
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                    VALUES (%s, now(), %s)
                    ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                 (JOB_NAME, summary[:900]))
print(f"💓 {JOB_NAME}")

# Незаписанный блок — не тишина: записанное и пульс на месте, прогон падает
if errors:
    raise RuntimeError("транзакции Amazon не загружены: " + "; ".join(errors[:4]))
