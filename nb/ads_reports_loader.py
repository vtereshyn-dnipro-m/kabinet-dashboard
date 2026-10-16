# Databricks notebook source
# DBTITLE 1,Отчёты Amazon Ads (Reporting v3) → сырьё
# ═════════════════════════════════════════════════════════════
# KABINET - AMAZON ADS REPORTS — поисковые запросы, таргетинг, плейсменты и невалидный трафик рекламы Amazon
# Источник: Amazon Ads Reporting API v3 (POST /reporting/reports), по каждому рекламному профилю с расходом.
# Пишет: dnipro_m.dnipro_m.raw_amazon_ads_sp_targeting     — SP: ставка/ключ/таргет × день
#        dnipro_m.dnipro_m.raw_amazon_ads_sp_placement     — SP: кампания × плейсмент × день
#        dnipro_m.dnipro_m.raw_amazon_ads_sp_search_term   — SP: поисковый запрос покупателя × день
#        dnipro_m.dnipro_m.raw_amazon_ads_sb_search_term   — SB: поисковый запрос × день
#        dnipro_m.dnipro_m.raw_amazon_ads_gross_invalid    — SP и SB: невалидные показы и клики × кампания × день
# Amazon хранит эти данные недолго и сдвигает окно каждый день (проверено 16.10.2026): SP — 95 дней, SB поисковые
# запросы — 60 дней, невалидный трафик — 365 дней. Что не забрали вовремя, потеряно навсегда, поэтому первый прогон
# берёт всё, что Amazon ещё отдаёт, а дальше каждый прогон перечитывает последние reorder_params.ads_reports_reread_days
# (атрибуция продаж закрывается за 14 дней) и всё, чего ещё нет. Начало истории спрашиваем у самого API: на слишком
# старую дату он отвечает ошибкой с датой начала хранения.
# Квоту createReport SP-API не трогает: у Ads API свои лимиты.
# Параметры: dry_run=1 — отчёты за days последних дней без записи; days — окно пробы; types — через запятую.
# Самодостаточная ячейка: своё подключение, свои константы.
# ═════════════════════════════════════════════════════════════
import datetime as dt
import gzip
import json
import re
import time
from zoneinfo import ZoneInfo

import requests
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType, TimestampType

JOB_NAME = "Kabinet - Amazon Ads Reports"
ADS = "https://advertising-api-eu.amazon.com"
CHUNK_DAYS = 31            # больше 31 дня в одном дневном отчёте Ads API не отдаёт
MAX_PENDING = 15           # столько отчётов держим в работе одновременно
POLL_LIMIT_MIN = 200       # первый прогон — около двухсот отчётов, Amazon собирает их минутами
INVOICE_DAYS = 400         # профиль без счетов за этот срок рекламу не крутил — отчёты по нему не заказываем

TEXT_COLS = {"campaignId", "campaignName", "campaignStatus", "adGroupId", "adGroupName", "keywordId", "keyword",
             "keywordText", "targeting", "keywordType", "matchType", "searchTerm", "placementClassification"}
TYPES = {
    "sp_targeting": dict(rt="spTargeting", ad="SPONSORED_PRODUCTS", gb=["targeting"], table="raw_amazon_ads_sp_targeting",
        cols=["date", "campaignId", "campaignName", "adGroupId", "adGroupName", "keywordId", "keyword", "targeting",
              "keywordType", "matchType", "impressions", "clicks", "cost", "purchases14d", "sales14d",
              "unitsSoldClicks14d", "topOfSearchImpressionShare"], retention=95),
    "sp_placement": dict(rt="spCampaigns", ad="SPONSORED_PRODUCTS", gb=["campaign", "campaignPlacement"],
        table="raw_amazon_ads_sp_placement",
        cols=["date", "campaignId", "campaignName", "campaignStatus", "placementClassification", "impressions",
              "clicks", "cost", "purchases14d", "sales14d", "unitsSoldClicks14d"], retention=95),
    "sp_search_term": dict(rt="spSearchTerm", ad="SPONSORED_PRODUCTS", gb=["searchTerm"], table="raw_amazon_ads_sp_search_term",
        cols=["date", "campaignId", "campaignName", "adGroupId", "adGroupName", "keywordId", "keyword", "matchType",
              "searchTerm", "impressions", "clicks", "cost", "purchases14d", "sales14d", "unitsSoldClicks14d"], retention=95),
    "sb_search_term": dict(rt="sbSearchTerm", ad="SPONSORED_BRANDS", gb=["searchTerm"], table="raw_amazon_ads_sb_search_term",
        cols=["date", "campaignId", "campaignName", "adGroupId", "adGroupName", "keywordId", "keywordText", "matchType",
              "searchTerm", "impressions", "clicks", "cost", "purchases", "sales", "unitsSold"], retention=60),
    # SP и SB невалидного трафика — одна таблица, различаются колонкой ad_product
    "sp_invalid": dict(rt="spGrossAndInvalids", ad="SPONSORED_PRODUCTS", gb=["campaign"], table="raw_amazon_ads_gross_invalid",
        cols=["date", "campaignId", "campaignName", "campaignStatus", "impressions", "clicks", "grossImpressions",
              "grossClickThroughs", "invalidImpressions", "invalidClickThroughs", "invalidImpressionRate",
              "invalidClickThroughRate"], retention=365),
    "sb_invalid": dict(rt="sbGrossAndInvalids", ad="SPONSORED_BRANDS", gb=["campaign"], table="raw_amazon_ads_gross_invalid",
        cols=["date", "campaignId", "campaignName", "campaignStatus", "impressions", "clicks", "grossImpressions",
              "grossClickThroughs", "invalidImpressions", "invalidClickThroughs", "invalidImpressionRate",
              "invalidClickThroughRate"], retention=365),
}


def snake(c):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", c).lower()


for _n, _d in (("dry_run", "0"), ("days", "2"), ("types", "")):
    try:
        dbutils.widgets.text(_n, _d)
    except Exception:
        pass
DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
PROBE_DAYS = int(dbutils.widgets.get("days").strip() or 2)
ONLY = {x.strip() for x in dbutils.widgets.get("types").split(",") if x.strip()}
RUN_TYPES = {k: v for k, v in TYPES.items() if not ONLY or k in ONLY}

today = dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()
END = today - dt.timedelta(days=1)          # сегодняшний день у Amazon ещё не закрыт

# ── подключение к Lakebase: настройка окна и пульс ──
import psycopg2
from databricks.sdk import WorkspaceClient

_w = WorkspaceClient()


def pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_w.current_user.me().user_name,
                            password=_w.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token,
                            sslmode="require")


REREAD_DAYS = 30
try:
    with pg() as _c, _c.cursor() as _cur:
        _cur.execute("SELECT value FROM kabinet_data.reorder_params WHERE key = 'ads_reports_reread_days'")
        _row = _cur.fetchone()
        if _row and _row[0]:
            REREAD_DAYS = int(_row[0])
except Exception as e:
    print(f"⚠️ настройка окна не прочиталась, беру {REREAD_DAYS} дней: {e}")

# ── авторизация Ads API ──
sec = lambda k: dbutils.secrets.get("amazon-sp-api", k)
_cid = sec("ads_lwa_client_id")
_tok = {"v": None, "exp": 0}


def token():
    if _tok["v"] and time.time() < _tok["exp"] - 120:
        return _tok["v"]
    r = requests.post("https://api.amazon.com/auth/o2/token", timeout=30, data={
        "grant_type": "refresh_token", "refresh_token": sec("ads_lwa_refresh_token"),
        "client_id": _cid, "client_secret": sec("ads_lwa_client_secret")})
    r.raise_for_status()
    _tok.update(v=r.json()["access_token"], exp=time.time() + int(r.json().get("expires_in", 3600)))
    return _tok["v"]


def ads(method, path, profile=None, **kw):
    """Ads API с терпением к 429/5xx (лимит Ads API, а не квота createReport SP-API): Retry-After или 2^n с, 8 попыток."""
    h = {"Authorization": f"Bearer {token()}", "Amazon-Advertising-API-ClientId": _cid}
    if profile:
        h["Amazon-Advertising-API-Scope"] = str(profile)
    if method == "post":
        h["Content-Type"] = "application/vnd.createasyncreportrequest.v3+json"
    r = None
    for attempt in range(8):
        r = requests.request(method, ADS + path, headers=h, timeout=90, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(float(r.headers.get("Retry-After") or 2 ** attempt), 120))
            continue
        return r
    return r


# ── профили: только те, по которым Amazon выставлял счета за INVOICE_DAYS ──
profiles = ads("get", "/v2/profiles").json()
active = None
try:
    active = {r["profile_id"] for r in spark.sql(f"""
        SELECT DISTINCT profile_id FROM dnipro_m.dnipro_m.raw_amazon_ads_invoices
         WHERE status = 'ACCUMULATING' OR to_date >= date_sub(current_date(), {INVOICE_DAYS})""").collect()}
except Exception as e:
    print(f"⚠️ счета Amazon Ads не прочитались — беру все профили: {e}")
PROFILES = [(str(p["profileId"]), p.get("countryCode"), p.get("currencyCode")) for p in profiles
            if active is None or str(p["profileId"]) in active]
print(f"профилей {len(profiles)}, с рекламой за {INVOICE_DAYS} дн: {', '.join(c for _, c, _ in PROFILES)}")


def body(cfg, d1, d2):
    return {"name": f"kabinet {cfg['rt']} {d1}..{d2}", "startDate": d1.isoformat(), "endDate": d2.isoformat(),
            "configuration": {"adProduct": cfg["ad"], "groupBy": cfg["gb"], "columns": cfg["cols"],
                              "reportTypeId": cfg["rt"], "timeUnit": "DAILY", "format": "GZIP_JSON"}}


# ── с какой даты Amazon хранит каждый отчёт: спрашиваем самим API ──
RET = {}
for key, cfg in RUN_TYPES.items():
    r = ads("post", "/reporting/reports", PROFILES[0][0] if PROFILES else None,
            json=body(cfg, today - dt.timedelta(days=3650), today - dt.timedelta(days=3650)))
    m = re.search(r"retention start date \((\d{4}-\d{2}-\d{2})\)", r.text or "")
    RET[key] = dt.date.fromisoformat(m.group(1)) if m else today - dt.timedelta(days=cfg["retention"])
    print(f"{key}: Amazon хранит с {RET[key]}" + ("" if m else f" (ответ без даты, беру {cfg['retention']} дн: {r.status_code} {r.text[:150]})"))


def last_loaded(table, profile_id, ad=None):
    full = f"dnipro_m.dnipro_m.{table}"
    if not spark.catalog.tableExists(full):
        return None
    cond = f" AND ad_product = '{ad}'" if ad else ""
    return spark.sql(f"SELECT max(date) d FROM {full} WHERE profile_id = '{profile_id}'{cond}").collect()[0]["d"]


# ── что заказываем: группа = профиль × отчёт, внутри куски по 31 дню ──
groups = []
for pid, pc, cur in PROFILES:
    for key, cfg in RUN_TYPES.items():
        ad = cfg["ad"] if cfg["table"] == "raw_amazon_ads_gross_invalid" else None
        if DRY_RUN:
            start = END - dt.timedelta(days=PROBE_DAYS - 1)
        else:
            last = last_loaded(cfg["table"], pid, ad)
            start = RET[key] if last is None else min(last + dt.timedelta(days=1), END - dt.timedelta(days=REREAD_DAYS - 1))
            start = max(start, RET[key])
        if start > END:
            continue
        chunks, d1 = [], start
        while d1 <= END:
            d2 = min(d1 + dt.timedelta(days=CHUNK_DAYS - 1), END)
            chunks.append({"d1": d1, "d2": d2, "id": None, "rows": None, "err": None})
            d1 = d2 + dt.timedelta(days=1)
        groups.append({"pid": pid, "pc": pc, "cur": cur, "key": key, "cfg": cfg, "ad": ad,
                       "start": start, "end": END, "chunks": chunks})
n_reports = sum(len(g["chunks"]) for g in groups)
print(f"заказываем {n_reports} отчётов в {len(groups)} группах, по {END}" + (" (проба, без записи)" if DRY_RUN else ""))

# ── заказ и ожидание: не больше MAX_PENDING в работе ──
queue = [(g, c) for g in groups for c in g["chunks"]]
pending, t0 = [], time.time()
while (queue or pending) and time.time() - t0 < POLL_LIMIT_MIN * 60:
    while queue and len(pending) < MAX_PENDING:
        g, c = queue.pop(0)
        r = ads("post", "/reporting/reports", g["pid"], json=body(g["cfg"], c["d1"], c["d2"]))
        if r.status_code in (200, 202):
            c["id"] = r.json().get("reportId")
        elif r.status_code == 425:                 # такой отчёт уже заказан — берём его номер
            m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27})", r.text or "")
            c["id"] = m.group(1) if m else None
        if c["id"]:
            pending.append((g, c))
        else:
            c["err"] = f"заказ {r.status_code}: {r.text[:200]}"
    time.sleep(20)
    still = []
    for g, c in pending:
        st = ads("get", f"/reporting/reports/{c['id']}", g["pid"])
        j = st.json() if st.status_code == 200 else {}
        if j.get("status") == "COMPLETED" and j.get("url"):
            c["rows"] = json.loads(gzip.decompress(requests.get(j["url"], timeout=300).content) or b"[]")
        elif j.get("status") == "FAILURE":
            c["err"] = f"FAILURE: {j.get('failureReason')}"
        else:
            still.append((g, c))
    pending = still
for g, c in pending + queue:
    c["err"] = c["err"] or f"не готов за {POLL_LIMIT_MIN} мин"

# ── запись: группа целиком или никак ──
NOW = dt.datetime.now(dt.timezone.utc)
errors, summary_parts, made = [], [], set()
for g in groups:
    bad = [c for c in g["chunks"] if c["err"]]
    rows = [x for c in g["chunks"] for x in (c["rows"] or [])]
    label = f"{g['pc']} {g['key']}"
    if bad:
        errors.append(f"{label}: " + "; ".join(f"{c['d1']}…{c['d2']} {c['err']}" for c in bad[:2]))
        continue
    days = len({x.get("date") for x in rows})
    summary_parts.append(f"{label} {len(rows)} стр/{days} дн с {g['start']}")
    if DRY_RUN:
        print(f"  {label}: {g['start']}…{g['end']}, строк {len(rows)}, дней с данными {days}"
              + (f", пример {json.dumps(rows[0], ensure_ascii=False)[:250]}" if rows else ""))
        continue
    cols = g["cfg"]["cols"]
    fields = [StructField("profile_id", StringType()), StructField("country", StringType()),
              StructField("currency", StringType()), StructField("ad_product", StringType())]
    fields += [StructField(snake(c), DateType() if c == "date" else StringType() if c in TEXT_COLS else DoubleType())
               for c in cols]
    fields += [StructField("loaded_at", TimestampType())]
    schema = StructType(fields)

    def conv(c, v):
        if v is None:
            return None
        if c == "date":
            return dt.date.fromisoformat(str(v)[:10])
        if c in TEXT_COLS:
            return str(v)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    data = [(g["pid"], g["pc"], g["cur"], g["cfg"]["ad"], *[conv(c, x.get(c)) for c in cols], NOW) for x in rows]
    full = f"dnipro_m.dnipro_m.{g['cfg']['table']}"
    if full not in made:
        ddl = ", ".join(f"{f.name} {f.dataType.simpleString().upper()}" for f in schema.fields)
        spark.sql(f"CREATE TABLE IF NOT EXISTS {full} ({ddl}) USING DELTA COMMENT "
                  f"'Amazon Ads Reporting v3, {g['cfg']['rt']}: строка как в отчёте, по профилям. "
                  f"Пишет {JOB_NAME}, окно перечитывается целиком.'")
        made.add(full)
    pred = f"profile_id = '{g['pid']}' AND date >= '{g['start']}' AND date <= '{g['end']}'"
    if g["ad"]:
        pred += f" AND ad_product = '{g['ad']}'"
    # replaceWhere: окно профиля заменяется атомарно — строки, которых Amazon больше не отдаёт, уходят, дублей нет
    (spark.createDataFrame(data, schema).write.format("delta").mode("overwrite")
     .option("replaceWhere", pred).saveAsTable(full))

summary = f"отчётов {n_reports}, групп {len(groups)}; " + "; ".join(summary_parts)
if errors:
    summary += " | ⚙️ сбои: " + "; ".join(errors[:4])
print("📊 " + summary)

if DRY_RUN:
    dbutils.notebook.exit(json.dumps({"summary": summary, "errors": errors, "retention": {k: str(v) for k, v in RET.items()}},
                                     ensure_ascii=False))

# ── SYSTEM PULSE: безусловно, последним ──
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                    VALUES (%s, now(), %s)
                    ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                 (JOB_NAME, summary[:900]))
    _c.commit()
print(f"💓 {JOB_NAME}")

# Группа, которая не загрузилась, — не тишина: остальные и пульс записаны, прогон падает
if errors:
    raise RuntimeError("отчёты Amazon Ads не загружены: " + "; ".join(errors))
