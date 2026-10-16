# Databricks notebook source
# DBTITLE 1,Счета Amazon Ads (Billing API) → сырьё
# ═════════════════════════════════════════════════════════════
# KABINET - AMAZON ADS INVOICES — счета рекламы Amazon по всем рекламным профилям
# Источник: Amazon Ads Billing API, GET /invoices (список счетов профиля, постранично).
# Пишет: dnipro_m.dnipro_m.raw_amazon_ads_invoices      — строка на счёт
#        dnipro_m.dnipro_m.raw_amazon_ads_invoice_fees  — строка на сбор счёта (тип × страна)
# Каждый прогон перечитывает ВСЮ историю, которую отдаёт API: счетов сотни, это секунды,
# а статус и остаток к оплате у старых счетов меняются. MERGE — повторный прогон ничего не множит.
# Квоту createReport не трогает: у Ads API свои лимиты.
# Параметр dry_run=1 — ничего не пишет (ни таблицы, ни пульс), только отчёт.
# Самодостаточная ячейка: своё подключение, свои константы.
# ═════════════════════════════════════════════════════════════
import collections
import datetime
import json
import time

import requests
from pyspark.sql.types import (DateType, DoubleType, StringType, StructField, StructType,
                               TimestampType)

JOB_NAME = "Kabinet - Amazon Ads Invoices"
T_INV = "dnipro_m.dnipro_m.raw_amazon_ads_invoices"
T_FEE = "dnipro_m.dnipro_m.raw_amazon_ads_invoice_fees"
ADS = "https://advertising-api-eu.amazon.com"
# Рынок профиля → суффикс сырых таблиц рекламы (для разноса сбора по месяцам в отчёте)
MK_SUFFIX = {"ES": "es", "DE": "de", "FR": "fr", "IT": "it", "NL": "nl", "BE": "be",
             "PL": "pl", "SE": "se", "UK": "uk", "GB": "uk", "IE": "ie"}

try:
    dbutils.widgets.text("dry_run", "0")
    DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
except Exception:
    DRY_RUN = False

sec = lambda k: dbutils.secrets.get("amazon-sp-api", k)
_cid = sec("ads_lwa_client_id")
_tok = requests.post("https://api.amazon.com/auth/o2/token", timeout=30, data={
    "grant_type": "refresh_token", "refresh_token": sec("ads_lwa_refresh_token"),
    "client_id": _cid, "client_secret": sec("ads_lwa_client_secret")})
_tok.raise_for_status()
BASE_H = {"Authorization": f"Bearer {_tok.json()['access_token']}", "Amazon-Advertising-API-ClientId": _cid}


def ads_get(path, headers, params=None):
    """GET с терпением к 429/5xx: Retry-After или 2^n секунд, до 6 попыток."""
    for attempt in range(6):
        r = requests.get(ADS + path, headers=headers, params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("Retry-After") or 2 ** attempt))
            continue
        return r
    return r


def d8(s):
    """'20260802' → date; пусто → None."""
    return datetime.datetime.strptime(s, "%Y%m%d").date() if s else None


def amt(x):
    return (x or {}).get("amount")


profiles = ads_get("/v2/profiles", BASE_H)
profiles.raise_for_status()
profiles = profiles.json()

now = datetime.datetime.now(datetime.timezone.utc)
inv_rows, fee_rows, errors, ok_profiles = [], [], [], []
for p in profiles:
    pid, pc = str(p["profileId"]), p.get("countryCode")
    h = {**BASE_H, "Amazon-Advertising-API-Scope": pid, "Accept": "application/json"}
    cursor, failed = None, False
    for _ in range(200):
        prm = {"count": 100}
        if cursor:
            prm["cursor"] = cursor
        r = ads_get("/invoices", h, prm)
        if r.status_code != 200:
            errors.append(f"{pc}: HTTP {r.status_code} {r.text[:200]}")
            failed = True
            break
        pl = r.json().get("payload") or {}
        for x in pl.get("invoiceSummaries") or []:
            # У ещё набирающегося счёта (ACCUMULATING) номера нет: ключ — профиль + дата начала.
            # Такие строки каждый прогон заменяются целиком: когда счёт закроется, он придёт с номером.
            key = x.get("id") or f"ACCUMULATING:{x.get('fromDate')}"
            raw = {k: v for k, v in x.items() if k != "downloadableDocuments"}  # ссылки на PDF не храним
            inv_rows.append((pid, pc, p.get("currencyCode"), key, x.get("id"), x.get("status"),
                             d8(x.get("invoiceDate")), d8(x.get("fromDate")), d8(x.get("toDate")),
                             amt(x.get("amountDue")), (x.get("amountDue") or {}).get("currencyCode"),
                             amt(x.get("taxAmountDue")), amt(x.get("remainingAmountDue")),
                             amt(x.get("remainingTaxAmountDue")), x.get("countryCode"),
                             x.get("adProductGroup"), json.dumps(raw, ensure_ascii=False), now))
            rem = {(f.get("feeType"), (f.get("feeIdentifiers") or {}).get("countryCode")): amt(f.get("cost"))
                   for f in x.get("remainingFees") or []}
            for f in x.get("fees") or []:
                fc = (f.get("feeIdentifiers") or {}).get("countryCode")
                fee_rows.append((pid, key, f.get("feeType"), fc, amt(f.get("cost")),
                                 (f.get("cost") or {}).get("currencyCode"),
                                 rem.get((f.get("feeType"), fc)), now))
        cursor = pl.get("nextCursor")
        if not cursor or not pl.get("invoiceSummaries"):
            break
    if not failed:
        ok_profiles.append(pid)

# ── ОТЧЁТ: с какой даты есть счета, сколько, сбор по месяцам ─────────────────
# Счёт выставляется по порогу и в месяц не укладывается (у DE один счёт 02.07–02.08), поэтому
# сбор счёта разносится по дням его периода пропорционально расходу из Ads API за эти дни
# (SP + SB + SD по кампаниям); дней без расхода нет — поровну. Сумма по счёту сохраняется
# до цента, приблизителен только раздел между месяцами.
fees_by_inv = collections.defaultdict(float)
for pid, key, ft, fc, a, cur_, rem_, _ in fee_rows:
    fees_by_inv[(pid, key)] += a or 0.0

daily = {}
for pc in {r[1] for r in inv_rows}:
    suf = MK_SUFFIX.get(pc)
    if not suf:
        continue
    parts = [f"SELECT CAST(date AS DATE) d, sum(cost) c FROM dnipro_m.dnipro_m.raw_amazon_ads_{t}_campaign_{suf} GROUP BY 1"
             for t in ("sp", "sb", "sd") if spark.catalog.tableExists(f"dnipro_m.dnipro_m.raw_amazon_ads_{t}_campaign_{suf}")]
    if parts:
        q = "SELECT d, sum(c) c FROM (" + " UNION ALL ".join(parts) + ") GROUP BY d"
        daily[pc] = {row["d"]: float(row["c"] or 0) for row in spark.sql(q).collect()}

by_month = collections.defaultdict(float)   # (месяц, страна профиля) → сбор
summary_by_c = {}
today = datetime.date.today()
for (pid, pc, pcur, key, iid, st, idate, fd, td, due, cur_, tax, *_rest) in inv_rows:
    s = summary_by_c.setdefault(pc, {"currency": pcur, "invoices": 0, "accumulating": 0, "first_from": None,
                                     "last_to": None, "amount_due": 0.0, "tax": 0.0, "fees": 0.0})
    s["invoices"] += 1 if iid else 0
    s["accumulating"] += 0 if iid else 1
    s["first_from"] = min(filter(None, [s["first_from"], fd])) if fd else s["first_from"]
    s["last_to"] = max(filter(None, [s["last_to"], td])) if td else s["last_to"]
    s["amount_due"] += due or 0.0
    s["tax"] += tax or 0.0
    fee = fees_by_inv.get((pid, key), 0.0)
    s["fees"] += fee
    if not fee or not fd:
        continue
    days = [fd + datetime.timedelta(n) for n in range(((td or today) - fd).days + 1)]
    w = [daily.get(pc, {}).get(d, 0.0) for d in days]
    if sum(w) <= 0:
        w = [1.0] * len(days)
    for d, wi in zip(days, w):
        by_month[(d.strftime("%Y-%m"), pc)] += fee * wi / sum(w)

countries = sorted(summary_by_c)
months = sorted({m for m, _ in by_month})
print(f"Профилей {len(profiles)}, со счетами {len(countries)}; счетов {sum(s['invoices'] for s in summary_by_c.values())}, "
      f"строк сборов {len(fee_rows)}; ошибок {len(errors)}")
for c in countries:
    s = summary_by_c[c]
    print(f"  {c}: счета с {s['first_from']} по {s['last_to'] or 'сейчас'}, {s['invoices']} шт"
          f"{' + набирающийся' if s['accumulating'] else ''}; к оплате {s['amount_due']:.2f} {s['currency']}, "
          f"сбор {s['fees']:.2f}, НДС {s['tax']:.2f}")
print("Сбор по месяцам (валюта профиля):\n" + "месяц    " + "".join(f"{c:>10}" for c in countries))
for m in months:
    print(f"{m}  " + "".join(f"{by_month.get((m, c), 0.0):>10.2f}" for c in countries))
for e in errors:
    print("⚠️ " + e)

report = {"dry_run": DRY_RUN, "profiles": [[p["profileId"], p.get("countryCode"), p.get("currencyCode")] for p in profiles],
          "by_country": {c: {**v, "first_from": str(v["first_from"]), "last_to": str(v["last_to"])} for c, v in summary_by_c.items()},
          "fee_by_month": {m: {c: round(by_month.get((m, c), 0.0), 2) for c in countries} for m in months},
          "errors": errors, "n_invoices": len(inv_rows), "n_fees": len(fee_rows)}
summary = (f"счетов {len(inv_rows)} по {len(countries)} странам ({', '.join(countries)}), сборов {len(fee_rows)}"
           + (f"; ОШИБКИ: {'; '.join(errors)}" if errors else ""))

if DRY_RUN:
    dbutils.notebook.exit(json.dumps(report, ensure_ascii=False, default=str))

# ── ЗАПИСЬ В СЫРЬЁ ───────────────────────────────────────────────────────────
INV_SCHEMA = StructType([StructField(n, t) for n, t in [
    ("profile_id", StringType()), ("profile_country", StringType()), ("profile_currency", StringType()),
    ("invoice_key", StringType()), ("invoice_id", StringType()), ("status", StringType()),
    ("invoice_date", DateType()), ("from_date", DateType()), ("to_date", DateType()),
    ("amount_due", DoubleType()), ("currency", StringType()), ("tax_amount_due", DoubleType()),
    ("remaining_amount_due", DoubleType()), ("remaining_tax_amount_due", DoubleType()),
    ("invoice_country", StringType()), ("ad_product_group", StringType()), ("raw", StringType()),
    ("loaded_at", TimestampType())]])
FEE_SCHEMA = StructType([StructField(n, t) for n, t in [
    ("profile_id", StringType()), ("invoice_key", StringType()), ("fee_type", StringType()),
    ("fee_country", StringType()), ("amount", DoubleType()), ("currency", StringType()),
    ("remaining_amount", DoubleType()), ("loaded_at", TimestampType())]])

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {T_INV} (
        profile_id STRING COMMENT 'Рекламный профиль Amazon Ads (страна рынка)',
        profile_country STRING, profile_currency STRING,
        invoice_key STRING COMMENT 'Номер счёта; у набирающегося счёта без номера — ACCUMULATING:<дата начала>',
        invoice_id STRING, status STRING COMMENT 'PAID_IN_FULL / ACCUMULATING / …',
        invoice_date DATE, from_date DATE, to_date DATE,
        amount_due DOUBLE COMMENT 'К оплате БЕЗ НДС: реклама + регуляторный сбор',
        currency STRING, tax_amount_due DOUBLE COMMENT 'НДС счёта (у ES 21 %, у IT/FR/DE ноль)',
        remaining_amount_due DOUBLE, remaining_tax_amount_due DOUBLE,
        invoice_country STRING, ad_product_group STRING,
        raw STRING COMMENT 'Ответ API без ссылок на документы',
        loaded_at TIMESTAMP
    ) USING DELTA
    COMMENT 'Счета Amazon Ads (Billing API) по всем рекламным профилям. Реклама счёта = amount_due − сумма сборов. Пишет Kabinet - Amazon Ads Invoices.'
""")
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {T_FEE} (
        profile_id STRING, invoice_key STRING,
        fee_type STRING COMMENT 'REGULATORY_ADVERTISING_FEE и др.',
        fee_country STRING COMMENT 'Страна, за показы в которой сбор (у профиля DE — в основном AT)',
        amount DOUBLE, currency STRING, remaining_amount DOUBLE, loaded_at TIMESTAMP
    ) USING DELTA
    COMMENT 'Сборы в счетах Amazon Ads: строка на счёт × тип × страна. Сумма входит в amount_due счёта. Пишет Kabinet - Amazon Ads Invoices.'
""")

spark.createDataFrame(inv_rows, INV_SCHEMA).createOrReplaceTempView("_ads_inv_new")
spark.createDataFrame(fee_rows, FEE_SCHEMA).createOrReplaceTempView("_ads_fee_new")
if ok_profiles:
    ids = ", ".join(f"'{x}'" for x in ok_profiles)
    # Набирающийся счёт меняет и сумму, и (когда закроется) ключ — его строки заменяются целиком,
    # но только у профилей, ответ по которым пришёл полностью
    spark.sql(f"DELETE FROM {T_INV} WHERE profile_id IN ({ids}) AND invoice_key LIKE 'ACCUMULATING:%'")
    spark.sql(f"DELETE FROM {T_FEE} WHERE profile_id IN ({ids}) AND invoice_key LIKE 'ACCUMULATING:%'")
spark.sql(f"""
    MERGE INTO {T_INV} t USING _ads_inv_new s
       ON t.profile_id = s.profile_id AND t.invoice_key = s.invoice_key
     WHEN MATCHED THEN UPDATE SET *
     WHEN NOT MATCHED THEN INSERT *
""")
spark.sql(f"""
    MERGE INTO {T_FEE} t USING _ads_fee_new s
       ON t.profile_id = s.profile_id AND t.invoice_key = s.invoice_key
      AND t.fee_type <=> s.fee_type AND t.fee_country <=> s.fee_country
     WHEN MATCHED THEN UPDATE SET *
     WHEN NOT MATCHED THEN INSERT *
""")
_n = spark.sql(f"SELECT count(*) n, count(DISTINCT profile_id) p FROM {T_INV}").collect()[0]
summary += f"; в таблице {_n['n']} счетов, профилей {_n['p']}"
print("🧾 " + summary)

# ── SYSTEM PULSE: безусловно, последним ──
import psycopg2
from databricks.sdk import WorkspaceClient

_w = WorkspaceClient()
_cred = _w.postgres.generate_database_credential(
    endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary")
_c = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com",
                      port=5432, dbname="databricks_postgres", user=_w.current_user.me().user_name,
                      password=_cred.token, sslmode="require")
_cur = _c.cursor()
_cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                VALUES (%s, now(), %s)
                ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
             (JOB_NAME, summary[:900]))
_c.commit(); _c.close()
print(f"💓 {JOB_NAME}")

# Профиль, по которому ответ не пришёл, — не тишина: данные остальных и пульс записаны, прогон падает
if errors:
    raise RuntimeError("Billing API не отдал счета: " + "; ".join(errors))
