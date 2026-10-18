# Databricks notebook source
# DBTITLE 1,Реплики рекламы Amazon в Lakebase (раздел «Реклама»)
# ═════════════════════════════════════════════════════════════
# KABINET - ADS REPLICA — данные рекламы из Unity Catalog в Lakebase, чтобы их видел экран Кабинета
# Страницы читают только Lakebase, а отчёты рекламы, счета и сборы лежат в Unity Catalog (решение владельца 18.10.2026,
# первый PR из трёх: реплики → экран; кнопки минус-слов не будет).
# Пишет (kabinet_data, таблицы заводит sql/ads_replica_2026-10-18.sql):
#   ads_campaign_daily        — кампания × день: SP из raw_amazon_ads_sp_placement (сумма по плейсментам), SB и SD из
#                               таблиц кампаний аналитика raw_amazon_ads_{sb,sd}_campaign_<рынок> — все кампании, включая SB
#                               без товара (в Spend Power BI их нет: ES сентябрь 2026 — 44 €);
#   ads_search_term_daily     — поисковый запрос × таргет × день, SP и SB, окно ads_replica_search_term_days (35);
#   ads_placement_daily       — SP: кампания × плейсмент × день;
#   ads_invalid_traffic_daily — SP и SB: всего и недействительных показов и кликов × кампания × день;
#   ads_fees_daily            — регуляторный сбор по дням (dnipro_m.v_amazon_ads_fees_daily);
#   ads_invoices              — счета Amazon Ads (сумма без НДС со сбором, НДС), без сырого ответа.
# Окно ads_replica_days (120) — каждая таблица в окне заменяется целиком одной транзакцией; счета — целиком.
# Суммы — в валюте профиля; Британия — GB (у профиля рекламы она UK, у таблиц аналитика — суффикс uk).
# Запуск в 10:20 Kyiv — после рекламных джоб аналитика (Ads First 08:30, Ads Second 09:40, SB Campaigns 09:50), наших
# отчётов рекламы (07:10) и счетов (08:50). Квоты Amazon не трогает: только чтение таблиц и запись в Lakebase.
# Параметр dry_run=1 — прочитать и показать объёмы без записи. Метка пульса — последней и безусловно.
# ═════════════════════════════════════════════════════════════
import datetime as dt
import json

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient

JOB_NAME = "Kabinet - Ads Replica"
UC = "dnipro_m.dnipro_m"
SB_SD_MARKETS = {"be": "BE", "de": "DE", "es": "ES", "fr": "FR", "ie": "IE", "it": "IT", "nl": "NL", "pl": "PL",
                 "se": "SE", "uk": "GB"}
CURRENCY = {"GB": "GBP", "SE": "SEK", "PL": "PLN"}       # остальные рынки — евро

try:
    dbutils.widgets.text("dry_run", "0")
except Exception:
    pass
DRY_RUN = dbutils.widgets.get("dry_run").strip() in ("1", "true", "yes")
_w = WorkspaceClient()


def pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_w.current_user.me().user_name,
                            password=_w.postgres.generate_database_credential(
                                endpoint="projects/kabinet-dashboard/branches/production/endpoints/primary").token,
                            sslmode="require")


DAYS, TERM_DAYS = 120, 35
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("SELECT key, value FROM kabinet_data.reorder_params WHERE key IN ('ads_replica_days', 'ads_replica_search_term_days')")
    for k, v in _cur.fetchall():
        if v:
            DAYS, TERM_DAYS = (int(v), TERM_DAYS) if k == "ads_replica_days" else (DAYS, int(v))
today = dt.date.today()
START, TERM_START = today - dt.timedelta(days=DAYS), today - dt.timedelta(days=TERM_DAYS)
GB = "CASE WHEN country = 'UK' THEN 'GB' ELSE country END"


def rows(sql):
    return [tuple(r) for r in spark.sql(sql).collect()]


def exists(t):
    return spark.catalog.tableExists(f"{UC}.{t}")


# ── кампании: SP из плейсментов + SB и SD из таблиц аналитика ──
camp = rows(f"""
    SELECT date, {GB}, 'SP', campaign_id, max(campaign_name), max(campaign_status), max(currency),
           sum(impressions), sum(clicks), sum(cost), sum(purchases14d), sum(sales14d), sum(units_sold_clicks14d)
    FROM {UC}.raw_amazon_ads_sp_placement WHERE date >= DATE'{START}'
    GROUP BY 1, 2, 3, 4""")
missing = []
for suf, mk in SB_SD_MARKETS.items():
    for prod in ("sb", "sd"):
        t = f"raw_amazon_ads_{prod}_campaign_{suf}"
        if not exists(t):
            missing.append(t)
            continue
        camp += rows(f"""
            SELECT date, '{mk}', '{prod.upper()}', campaignId, max(campaignName), max(campaignStatus),
                   coalesce(max(campaignBudgetCurrencyCode), '{CURRENCY.get(mk, "EUR")}'),
                   sum(impressions), sum(clicks), sum(cost), sum(purchases), sum(sales), sum(unitsSold)
            FROM {UC}.{t} WHERE date >= DATE'{START}' AND campaignId IS NOT NULL
            GROUP BY 1, 2, 3, 4""")

terms = rows(f"""
    SELECT date, {GB}, 'SP', campaign_id, campaign_name, ad_group_id, ad_group_name, keyword_id, keyword, match_type,
           search_term, currency, impressions, clicks, cost, purchases14d, sales14d, units_sold_clicks14d
    FROM {UC}.raw_amazon_ads_sp_search_term WHERE date >= DATE'{TERM_START}' AND search_term IS NOT NULL
    UNION ALL
    SELECT date, {GB}, 'SB', campaign_id, campaign_name, ad_group_id, ad_group_name, keyword_id, keyword_text, match_type,
           search_term, currency, impressions, clicks, cost, purchases, sales, units_sold
    FROM {UC}.raw_amazon_ads_sb_search_term WHERE date >= DATE'{TERM_START}' AND search_term IS NOT NULL""")

place = rows(f"""
    SELECT date, {GB}, campaign_id, placement_classification, max(campaign_name), max(currency),
           sum(impressions), sum(clicks), sum(cost), sum(purchases14d), sum(sales14d), sum(units_sold_clicks14d)
    FROM {UC}.raw_amazon_ads_sp_placement WHERE date >= DATE'{START}' AND placement_classification IS NOT NULL
    GROUP BY 1, 2, 3, 4""")

invalid = rows(f"""
    SELECT date, {GB}, CASE ad_product WHEN 'SPONSORED_PRODUCTS' THEN 'SP' WHEN 'SPONSORED_BRANDS' THEN 'SB' ELSE ad_product END,
           campaign_id, max(campaign_name), sum(impressions), sum(clicks), sum(gross_impressions),
           sum(gross_click_throughs), sum(invalid_impressions), sum(invalid_click_throughs)
    FROM {UC}.raw_amazon_ads_gross_invalid WHERE date >= DATE'{START}'
    GROUP BY 1, 2, 3, 4""")

fees = rows(f"""
    SELECT date, CASE WHEN profile_country = 'UK' THEN 'GB' ELSE profile_country END, fee_country, fee_type, currency,
           fee_amount, invoice_key, invoice_status, allocation
    FROM {UC}.v_amazon_ads_fees_daily WHERE date >= DATE'{START}'""")

invoices = rows(f"""
    SELECT invoice_key, CASE WHEN profile_country = 'UK' THEN 'GB' ELSE profile_country END, invoice_id, status,
           invoice_date, from_date, to_date, amount_due, tax_amount_due, currency
    FROM {UC}.raw_amazon_ads_invoices""")

# ── сверка до записи: SP + SB + SD по стране и месяцу — то, с чем экран будет сверять Spend Кабинета ──
by = {}
for r in camp:
    if r[0] >= today.replace(day=1) - dt.timedelta(days=62):
        key = (r[1], r[0].strftime("%Y-%m"))
        by[key] = by.get(key, 0.0) + float(r[9] or 0)
check = "; ".join(f"{k[0]} {k[1]} {v:,.0f}" for k, v in sorted(by.items()) if v)
counts = {"кампаний×дней": len(camp), "запросов": len(terms), "плейсментов": len(place),
          "недействительный трафик": len(invalid), "сборов": len(fees), "счетов": len(invoices)}
summary = (f"окно с {START} (запросы с {TERM_START}); " + ", ".join(f"{k} {v}" for k, v in counts.items())
           + f"; расход по стране и месяцу: {check}" + (f"; нет таблиц: {', '.join(missing)}" if missing else ""))
print("📊 " + summary)
if DRY_RUN:
    dbutils.notebook.exit(json.dumps({"summary": summary, "counts": counts}, ensure_ascii=False))

# ── запись: каждая таблица в окне заменяется целиком, всё одной транзакцией ──
WRITES = [
    ("ads_campaign_daily", "date >= %s", START,
     "date, country, ad_product, campaign_id, campaign_name, campaign_status, currency, impressions, clicks, cost, orders, sales, units", camp),
    ("ads_search_term_daily", "date >= %s", TERM_START,
     "date, country, ad_product, campaign_id, campaign_name, ad_group_id, ad_group_name, keyword_id, keyword, match_type, "
     "search_term, currency, impressions, clicks, cost, orders, sales, units", terms),
    ("ads_placement_daily", "date >= %s", START,
     "date, country, campaign_id, placement, campaign_name, currency, impressions, clicks, cost, orders, sales, units", place),
    ("ads_invalid_traffic_daily", "date >= %s", START,
     "date, country, ad_product, campaign_id, campaign_name, impressions, clicks, gross_impressions, gross_clicks, "
     "invalid_impressions, invalid_clicks", invalid),
    ("ads_fees_daily", "date >= %s", START,
     "date, profile_country, fee_country, fee_type, currency, fee_amount, invoice_key, invoice_status, allocation", fees),
    ("ads_invoices", "true", None,
     "invoice_key, profile_country, invoice_id, status, invoice_date, from_date, to_date, amount_due, tax_amount_due, currency", invoices),
]
with pg() as _c, _c.cursor() as _cur:
    for table, cond, arg, cols, data in WRITES:
        _cur.execute(f"DELETE FROM kabinet_data.{table} WHERE {cond}", (arg,) if arg else None)
        if data:
            psycopg2.extras.execute_values(_cur, f"INSERT INTO kabinet_data.{table} ({cols}) VALUES %s", data, page_size=2000)
    _c.commit()

# ── SYSTEM PULSE: безусловно, последним ──
with pg() as _c, _c.cursor() as _cur:
    _cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note)
                    VALUES (%s, now(), %s)
                    ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""",
                 (JOB_NAME, summary[:900]))
print(f"💓 {JOB_NAME}")
