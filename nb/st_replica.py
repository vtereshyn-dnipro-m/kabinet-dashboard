# Databricks notebook source
# DBTITLE 1,Cell 0: pip install + restartPython
# MAGIC %pip install -q "databricks-sdk>=0.118.0"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Cell 1: Sales & Traffic → kabinet_data.sales_traffic_daily из сырья Дарины
# ═════════════════════════════════════════════════════════════════════════════
# Kabinet - Sales & Traffic Replica (с 21.09.2026)
#
# Источник по конвенции слоёв — сырьё, которое уже собирает Дарина:
#   dnipro_m.raw_amazon_seller_central_sales_and_traffic_{es,it,fr,de,uk,ie,be,nl}
#   (GET_SALES_AND_TRAFFIC_REPORT по ASIN × SKU × день, её джоба «Sales & Traffic Report for Tableau» с 06.10.2026 стартует в 07:00 Kyiv).
# До этого Кабинет тянул тот же отчёт сам (8 createReport в день в Economics Loader 12:30) и отставал от её
# дашборда на полдня. Суммы по дню × рынку сходятся с нашей витриной до евро (проверено 15–19.09.2026, ES).
# Гранулярность у неё ASIN, у нас день × рынок. С 24.09.2026 тем же прогоном пишем ВТОРУЮ таблицу —
# kabinet_data.sales_traffic_asin (ASIN × день, штуки, продажи): без неё не посчитать подсказку коммерческой роли
# по ТЗ 009 («Traffic» — это много смотрят и мало зарабатываем). Сессии и просмотры — НЕ отсюда, а из ячейки 2
# (Seller Analytics): в сырье Дарины строки есть только у ASIN с продажей в этот день.
# Рынки без её таблицы (сейчас PL, SE) — по-прежнему через SP-API, тем же кодом, что раньше в ячейке 9.
# Дни без строк у неё = дни без продаж: заполняем нулями внутри её диапазона по рынку; после её последней даты
# строк не создаём — пропуск виден, нулём не маскируется.
# ═════════════════════════════════════════════════════════════════════════════
import json, gzip, time, psycopg2, psycopg2.extras, requests
from datetime import date, datetime, timedelta, timezone
from databricks.sdk import WorkspaceClient
# Запуск (с 05.10.2026): основная джоба стартует по ИЗМЕНЕНИЮ таблиц Дарины (table update trigger — через
# 20 минут тишины после её последней записи), а не по часам; запасная — та же тетрадь с mode=fallback в 11:00.
# У одной джобы Databricks не может быть сразу и триггера, и расписания, поэтому их две — и у каждой своя метка
# в system_pulse и своё правило (одна джоба — одна метка). Запасная ничего не копирует, если основная уже
# забрала всё, что Дарина записала: иначе это лишний прогон, а при сбое триггера — единственный.
dbutils.widgets.text("mode", "main")
MODE = dbutils.widgets.get("mode").strip() or "main"
JOB_NAME = "Kabinet - Sales & Traffic Replica" + (" (запасной)" if MODE == "fallback" else "")
ST_LOOKBACK_DAYS = 7; ST_LAG_DAYS = 1

_w = WorkspaceClient(); _usr = _w.current_user.me().user_name
_ep = "projects/kabinet-dashboard/branches/production/endpoints/primary"
pg = psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432, dbname="databricks_postgres",
                      user=_usr, password=_w.postgres.generate_database_credential(endpoint=_ep).token, sslmode="require")
cur = pg.cursor()
cur.execute("""SELECT upper(country_alpha2), amazon_id, lower(legacy_code), currency FROM kabinet_data.marketplaces_new
               WHERE platform_short = 'AMZ' AND is_active AND amazon_id IS NOT NULL AND sync_economics ORDER BY code""")
markets = cur.fetchall()
UPSERT = """INSERT INTO kabinet_data.sales_traffic_daily (snapshot_date, marketplace, ordered_sales, units_ordered, order_items, currency, loaded_at)
            VALUES %s ON CONFLICT (snapshot_date, marketplace) DO UPDATE SET
              ordered_sales = EXCLUDED.ordered_sales, units_ordered = EXCLUDED.units_ordered, order_items = EXCLUDED.order_items,
              currency = EXCLUDED.currency, loaded_at = now()"""
# Сессии и просмотры отсюда НЕ пишем (с 12.10.2026): в сырье Дарины есть только строки «ASIN × день» с продажей,
# и сессии дней без продаж туда не попадают — ES за сентябрь 10 480 против 22 083 в Seller Central. Полные сессии
# пишет ячейка 2 из Seller Analytics; здесь — только продажи, а у новой строки сессии пустые, пока их не заполнит она.
UPSERT_ASIN = """INSERT INTO kabinet_data.sales_traffic_asin
                   (snapshot_date, marketplace, asin, sku, sessions, page_views, units_ordered, ordered_sales, buy_box_pct, loaded_at)
                 VALUES %s ON CONFLICT (snapshot_date, marketplace, asin) DO UPDATE SET
                   sku = EXCLUDED.sku,
                   units_ordered = EXCLUDED.units_ordered, ordered_sales = EXCLUDED.ordered_sales,
                   buy_box_pct = EXCLUDED.buy_box_pct, loaded_at = now()"""
ASIN_WINDOW_DAYS = 180     # подсказке ролей хватает полугода, а таблица не разрастается без нужды
stats = []; via_api = []; failures = []; asin_stats = []

# ── запасной режим: нужен ли прогон вообще ──
_skip = None
if MODE == "fallback":
    try:
        _last_commit = None
        for _cc, _mid, _lg, _curr in markets:
            _t = f"dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_{'uk' if _lg == 'co.uk' else _lg}"
            if not spark.catalog.tableExists(_t):
                continue
            # в эпохе, а не датой: часовой пояс сессии Spark и Postgres могут не совпадать
            _ts = spark.sql(f"SELECT unix_timestamp(timestamp) AS e FROM (DESCRIBE HISTORY {_t} LIMIT 1)").collect()[0]["e"]
            _last_commit = _ts if _last_commit is None or _ts > _last_commit else _last_commit
        cur.execute("SELECT extract(epoch FROM max(loaded_at))::bigint FROM kabinet_data.sales_traffic_daily")
        _loaded = cur.fetchone()[0]
        _fmt = lambda e: datetime.fromtimestamp(e, __import__("zoneinfo").ZoneInfo("Europe/Kyiv")).strftime("%d.%m %H:%M") if e else "—"
        print(f"запасной: последняя запись у Дарины {_fmt(_last_commit)}, наша последняя загрузка {_fmt(_loaded)} (Киев)")
        if _last_commit is not None and _loaded is not None and _loaded > _last_commit:
            _skip = f"основной уже скопировал всё (Дарина {_fmt(_last_commit)}, мы {_fmt(_loaded)} Киев)"
    except Exception as _e:
        # не смогли понять — копируем: лишний прогон дешевле пропущенного дня
        print(f"запасной: проверка не удалась ({type(_e).__name__}: {str(_e)[:150]}) — копирую")
    if _skip:
        print(f"⏭️ {_skip}")
        markets = []   # ниже ни одного рынка — дойдём сразу до метки пульса
today = datetime.now(timezone.utc).date(); end_date = today - timedelta(days=ST_LAG_DAYS); start_date = end_date - timedelta(days=ST_LOOKBACK_DAYS - 1)
for cc, mid, lg, curr in markets:
    tbl = f"dnipro_m.dnipro_m.raw_amazon_seller_central_sales_and_traffic_{'uk' if lg == 'co.uk' else lg}"
    if not spark.catalog.tableExists(tbl):
        via_api.append((cc, mid, curr)); continue
    df = spark.sql(f"""
        WITH d AS (SELECT CAST(date AS DATE) AS d, SUM(unitsOrdered) AS units, SUM(orderedProductSales) AS sales, SUM(totalOrderItems) AS items
                   FROM {tbl} GROUP BY 1),
             cal AS (SELECT explode(sequence((SELECT MIN(d) FROM d), (SELECT MAX(d) FROM d), interval 1 day)) AS d)
        SELECT cal.d, COALESCE(d.sales, 0) AS sales, COALESCE(d.units, 0) AS units, COALESCE(d.items, 0) AS items
        FROM cal LEFT JOIN d ON d.d = cal.d ORDER BY cal.d""").collect()
    rows = [(r.d, cc, float(r.sales), int(r.units), int(r.items), curr or "EUR") for r in df]
    psycopg2.extras.execute_values(cur, UPSERT, rows, template="(%s, %s, %s, %s, %s, %s, now())", page_size=1000)
    pg.commit()
    stats.append((cc, len(rows), rows[-1][0] if rows else None))
    print(f"{cc}: {len(rows)} дней из {tbl.split('.')[-1]}, до {rows[-1][0] if rows else '—'}")

    # ── тот же источник, разрез по ASIN ──
    arows = [(r.d, cc, r.asin, r.sku, None, None, int(r.units or 0),
              float(r.sales or 0), float(r.bb) if r.bb is not None else None)
             for r in spark.sql(f"""
        SELECT CAST(date AS DATE) AS d, childAsin AS asin, MAX(sku) AS sku,
               SUM(unitsOrdered) AS units,
               SUM(orderedProductSales) AS sales, MAX(buyBoxPercentage) AS bb
        FROM {tbl}
        WHERE childAsin IS NOT NULL AND CAST(date AS DATE) > current_date - {ASIN_WINDOW_DAYS}
        GROUP BY 1, 2""").collect()]
    if arows:
        psycopg2.extras.execute_values(cur, UPSERT_ASIN, arows,
                                       template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, now())", page_size=1000)
        pg.commit()
    asin_stats.append((cc, len(arows)))
    print(f"   по ASIN: {len(arows)} строк за {ASIN_WINDOW_DAYS} дней")

# ── рынки без сырья Дарины — SP-API, как раньше в Economics Loader (ячейка 9) ──
if via_api:
    print(f"через SP-API (нет таблицы Дарины): {[m[0] for m in via_api]}")
# ─── SP-API token ───
_lwa_id = dbutils.secrets.get("amazon-sp-api", "lwa-app-id")
_lwa_secret = dbutils.secrets.get("amazon-sp-api", "lwa-client-secret")
_refresh = dbutils.secrets.get("amazon-sp-api", "refresh-token")

def _get_sp_token():
    r = requests.post("https://api.amazon.com/auth/o2/token",
        data={"grant_type": "refresh_token", "refresh_token": _refresh,
              "client_id": _lwa_id, "client_secret": _lwa_secret},
        headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

sp_token = _get_sp_token()
sp_headers = {"x-amz-access-token": sp_token, "Content-Type": "application/json"}
SP_API = "https://sellingpartnerapi-eu.amazon.com"

# ─── Запрос отчёта с retry на 429 ───
def _sp_request(method, url, **kwargs):
    """SP-API request with 429 exponential backoff."""
    backoffs = [60, 120, 240, 480]
    for attempt in range(5):
        resp = getattr(requests, method)(url, **kwargs)
        if resp.status_code == 429:
            wait = backoffs[min(attempt, len(backoffs)-1)]
            try:
                wait = max(wait, int(resp.headers.get("Retry-After", 0)))
            except (ValueError, TypeError):
                pass
            print(f"  429 QuotaExceeded, жду {wait}s (attempt {attempt+1}/5)")
            time.sleep(wait)
            continue
        return resp
    raise RuntimeError(f"[QUOTA_429] 5 попыток с паузами 60–480 с, всё 429: {url}")

def fetch_sales_traffic(mp_id, mp_code, d_start, d_end):
    """Fetch GET_SALES_AND_TRAFFIC_REPORT for one marketplace."""
    payload = {
        "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
        "dataStartTime": f"{d_start}T00:00:00Z",
        "dataEndTime": f"{d_end}T23:59:59Z",
        "marketplaceIds": [mp_id],
        "reportOptions": {"dateGranularity": "DAY"}
    }
    r = _sp_request("post", f"{SP_API}/reports/2021-06-30/reports",
                    headers=sp_headers, json=payload, timeout=30)
    if r.status_code != 202:
        raise RuntimeError(f"createReport {r.status_code}: {r.text[:200]}")
    report_id = r.json()["reportId"]

    # Poll
    for _ in range(60):
        time.sleep(5)
        meta = _sp_request("get", f"{SP_API}/reports/2021-06-30/reports/{report_id}",
                           headers=sp_headers, timeout=30).json()
        status = meta.get("processingStatus", "?")
        if status in ("DONE", "CANCELLED", "FATAL"):
            break
    if status != "DONE":
        print(f"  [{mp_code}] report {status}")
        return []

    doc_id = meta.get("reportDocumentId")
    if not doc_id:
        return []
    doc = _sp_request("get", f"{SP_API}/reports/2021-06-30/documents/{doc_id}",
                      headers=sp_headers, timeout=30).json()
    file_resp = requests.get(doc["url"], timeout=300)
    raw = file_resp.content
    if doc.get("compressionAlgorithm") == "GZIP":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))

    rows = []
    for day in data.get("salesAndTrafficByDate", []):
        s = day.get("salesByDate", {})
        t = day.get("trafficByDate", {})
        rows.append((
            day["date"],
            mp_code,
            float(s.get("orderedProductSales", {}).get("amount", 0)),
            int(s.get("unitsOrdered", 0)),
            int(s.get("totalOrderItems", 0)),
            int(t.get("sessions", 0)),
            int(t.get("pageViews", 0)),
            float(t.get("buyBoxPercentage", 0)),
            s.get("orderedProductSales", {}).get("currencyCode", "EUR"),
        ))
    return rows

# ─── Main loop ───

# цикл — на уровне модуля: внутри функции выше он был бы мёртвым кодом после return (так и случилось в первом прогоне)
for cc, mid, curr in via_api:
    try:
        rows = fetch_sales_traffic(mid, cc, start_date, end_date)
    except Exception as _e:
        failures.append(f"[{cc}] {_e}"); print(f"  ✗ {cc}: {_e}"); rows = []
    # fetch_sales_traffic отдаёт кортежи (date, mp, sales, units, items, sessions, page_views, buy_box, currency)
    rows6 = [(r[0], r[1], r[2], r[3], r[4], r[8]) for r in rows]
    if rows6:
        psycopg2.extras.execute_values(cur, UPSERT, rows6, template="(%s, %s, %s, %s, %s, %s, now())", page_size=1000); pg.commit()
    stats.append((cc, len(rows6), rows6[-1][0] if rows6 else None)); print(f"{cc}: {len(rows6)} дней через SP-API")
    time.sleep(3)

# ── SYSTEM PULSE: безусловно, последним ──
_note = (f"пропущен: {_skip}" if _skip else "; ".join(f"{cc}: {n} дн до {d}" for cc, n, d in stats))[:900]
cur.execute("""INSERT INTO kabinet_data.system_pulse (job_name, last_success_at, note, expected_interval_hours)
               VALUES (%s, now(), %s, 30) ON CONFLICT (job_name) DO UPDATE SET last_success_at = now(), note = EXCLUDED.note""", (JOB_NAME, _note))
pg.commit(); cur.close(); pg.close()
print(f"💓 {JOB_NAME}: {_note}")
if failures:
    _tag = "[QUOTA_429] " if any("[QUOTA_429]" in f for f in failures) else ""
    raise RuntimeError(_tag + f"Sales & Traffic через API: {len(failures)} рынков без отчёта: " + "; ".join(failures)[:1500])

# COMMAND ----------

# DBTITLE 1,Cell 2: сессии и просмотры из Seller Analytics → сырьё, sales_traffic_daily и sales_traffic_asin
# ═════════════════════════════════════════════════════════════════════════════
# Сессии (с 12.10.2026). Сырьё Sales & Traffic у Дарины — отчёт с разрезом по SKU, и Amazon кладёт в него только
# строки «ASIN × день» с продажей: сессии ASIN в дни без продаж туда не попадают вовсе. ES за сентябрь там 10 480
# сессий, а в Seller Central 22 083. Дневных сессий рынка с 20.09 у нас не было совсем — ячейка 1 их не пишет.
# Источник полных сессий — блок трафика Data Kiosk Seller Analytics (analytics_sellerAnalytics_2025_03_31): по дням
# совпал с дневными сессиями Seller Central штука в штуку (ES, 17 дней сентября). Квоту createReport он не трогает —
# у Data Kiosk своя; запросов на прогон два на каждые 31 день окна (по ASIN и по рынку), все рынки сразу.
# Отдельного Data Kiosk-набора Sales & Traffic нет: analytics_salesAndTraffic_2023_11_15 Amazon удалил 27.03.2026.
#
# Слои: ответ как есть — в сырьё dnipro_m.raw_amazon_seller_analytics_traffic (окно переписывается целиком), из
# него — sessions/page_views в sales_traffic_daily (только существующие дни: строку дня создаёт ячейка 1, иначе
# день без продаж выглядел бы нулём продаж) и в sales_traffic_asin с пометкой sessions_source = 'seller_analytics'
# (ASIN без продаж получают строку с нулём штук). Строка без этой пометки — сессий за день не знаем, читатели её
# не считают.
# Параметры: sessions_since (ГГГГ-ММ-ДД) — добор истории; dry_run=1 — запросы без записи, итоги в выводе.
# Метку пульса пишет ячейка 1 (одна джоба — одна метка); сбой здесь роняет прогон после неё.
# ═════════════════════════════════════════════════════════════════════════════
import json, gzip, time, psycopg2, psycopg2.extras, requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from databricks.sdk import WorkspaceClient
from pyspark.sql import functions as F

for _wn, _wd in (("mode", "main"), ("sessions_since", ""), ("dry_run", "0")):
    try:
        dbutils.widgets.text(_wn, _wd)
    except Exception:
        pass                                         # «mode» уже объявлен ячейкой 1
SA_MODE = dbutils.widgets.get("mode").strip() or "main"
SA_SINCE = dbutils.widgets.get("sessions_since").strip()
SA_DRY = dbutils.widgets.get("dry_run").strip() == "1"
SA_WINDOW_DAYS = 14          # Amazon уточняет трафик задним числом — окно перечитываем каждый прогон
SA_CHUNK_DAYS = 31
SA_DK = "https://sellingpartnerapi-eu.amazon.com/dataKiosk/2023-11-15"
SA_RAW = "dnipro_m.dnipro_m.raw_amazon_seller_analytics_traffic"
SA_POLL_MIN = 25

sa_today = datetime.now(ZoneInfo("Europe/Kyiv")).date()
sa_end = sa_today - timedelta(days=1)
sa_start = date.fromisoformat(SA_SINCE) if SA_SINCE else sa_end - timedelta(days=SA_WINDOW_DAYS - 1)

_sa_w = WorkspaceClient(); _sa_usr = _sa_w.current_user.me().user_name
_sa_ep = "projects/kabinet-dashboard/branches/production/endpoints/primary"
def sa_pg():
    return psycopg2.connect(host="ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com", port=5432,
                            dbname="databricks_postgres", user=_sa_usr,
                            password=_sa_w.postgres.generate_database_credential(endpoint=_sa_ep).token, sslmode="require")

_c = sa_pg(); _cur = _c.cursor()
_cur.execute("""SELECT amazon_id, upper(country_alpha2) FROM kabinet_data.marketplaces_new
                WHERE platform_short = 'AMZ' AND is_active AND amazon_id IS NOT NULL ORDER BY code""")
SA_MK = {mid: cc for mid, cc in _cur.fetchall()}
_c.close()

# запасной запуск: окно уже забрано сегодня — второй раз не ходим
sa_skip = None
if SA_MODE == "fallback" and not SA_SINCE and spark.catalog.tableExists(SA_RAW):
    _r = spark.sql(f"""SELECT max(date) AS d, max(loaded_at) >= current_timestamp() - INTERVAL 12 HOURS AS fresh
                       FROM {SA_RAW}""").collect()[0]
    if _r.d is not None and _r.d >= sa_end and _r.fresh:
        sa_skip = f"сессии по {_r.d} уже загружены основным прогоном"
print(f"сессии Seller Analytics: {sa_start} … {sa_end}, рынков {len(SA_MK)}" + (" (проба, без записи)" if SA_DRY else "")
      + (f" — пропуск: {sa_skip}" if sa_skip else ""))

_sa_tok = {"t": None, "exp": 0}
def sa_token():
    if _sa_tok["t"] and time.time() < _sa_tok["exp"] - 60:
        return _sa_tok["t"]
    r = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token",
        "refresh_token": dbutils.secrets.get("amazon-sp-api", "refresh-token"),
        "client_id": dbutils.secrets.get("amazon-sp-api", "lwa-app-id"),
        "client_secret": dbutils.secrets.get("amazon-sp-api", "lwa-client-secret")}, timeout=30)
    r.raise_for_status()
    _sa_tok.update(t=r.json()["access_token"], exp=time.time() + int(r.json().get("expires_in", 3600)))
    return _sa_tok["t"]

def sa_call(method, url, **kw):
    # 429 на createQuery ждём шагом 65 с, а не 60: ровно минутный шаг попадает в момент до выдачи токена квоты
    for _ in range(40):
        r = requests.request(method, url, headers={"x-amz-access-token": sa_token(), "Content-Type": "application/json"},
                             timeout=60, **kw)
        if r.status_code != 429:
            return r
        time.sleep(65)
    raise RuntimeError(f"[QUOTA_429] Data Kiosk: 40 попыток по 65 с, всё 429: {url}")

def sa_doc(doc_id):
    r = sa_call("GET", f"{SA_DK}/documents/{doc_id}")
    if r.status_code != 200:
        raise RuntimeError(f"documents {r.status_code}: {r.text[:300]}")
    d = r.json(); raw = requests.get(d["documentUrl"], timeout=300).content
    if d.get("compressionAlgorithm") == "GZIP":
        raw = gzip.decompress(raw)
    return [json.loads(x) for x in raw.decode("utf-8").split("\n") if x.strip()]

def sa_query(group_by, d1, d2):
    """Один запрос Seller Analytics по дням, все рынки сразу; строка документа = один день."""
    q = ('query { analytics_sellerAnalytics_2025_03_31 { sellerAnalyticsView(startDate: "%s", endDate: "%s", '
         'aggregateBy: DAY, currencyCode: "EUR", marketplaceId: [%s]) { startDate endDate metrics { groupByKey { %s } '
         'metrics { traffic { sessions { value } pageViews { value } featureOfferPct { value } } } } } } }'
         % (d1, d2, ", ".join(f'"{m}"' for m in SA_MK), group_by))
    r = sa_call("POST", f"{SA_DK}/queries", json={"query": q})
    if r.status_code != 202:
        raise RuntimeError(f"createQuery {r.status_code}: {r.text[:500]}")
    qid = r.json()["queryId"]; t0 = time.time(); meta = {}
    while time.time() - t0 < SA_POLL_MIN * 60:
        meta = sa_call("GET", f"{SA_DK}/queries/{qid}").json()
        if meta.get("processingStatus") in ("DONE", "FATAL", "CANCELLED"):
            break
        time.sleep(15)
    st = meta.get("processingStatus")
    if meta.get("errorDocumentId"):
        raise RuntimeError(f"Data Kiosk {st}: {json.dumps(sa_doc(meta['errorDocumentId']))[:600]}")
    if st != "DONE":
        raise RuntimeError(f"Data Kiosk: запрос {qid} в статусе {st} через {SA_POLL_MIN} мин")
    time.sleep(62)                                   # createQuery — один в минуту
    return sa_doc(meta["dataDocumentId"]) if meta.get("dataDocumentId") else []   # DONE без документа — данных нет

def sa_rows(days, level):
    out = []
    for day in days:
        d = date.fromisoformat(day["startDate"][:10])
        for g in day.get("metrics") or []:
            k = g.get("groupByKey") or {}; t = (g.get("metrics") or {}).get("traffic") or {}
            mid = k.get("marketplaceId")
            if mid not in SA_MK:
                continue
            v = lambda f: (t.get(f) or {}).get("value")
            out.append((d, mid, SA_MK[mid], level, k.get("asin") if level == "asin" else None,
                        int(v("sessions") or 0), int(v("pageViews") or 0),
                        float(v("featureOfferPct")) if v("featureOfferPct") is not None else None))
    return out

sa_failures, sa_all = [], []
if not sa_skip and SA_MK:
    d1 = sa_start
    while d1 <= sa_end:
        d2 = min(d1 + timedelta(days=SA_CHUNK_DAYS - 1), sa_end)
        try:
            # кусок берётся целиком или никак: окно в сырье переписывается по датам, полкуска затёрло бы ASIN
            chunk = sa_rows(sa_query("marketplaceId", d1, d2), "market") + sa_rows(sa_query("marketplaceId asin", d1, d2), "asin")
            sa_all.append((d1, d2, chunk))
            print(f"  {d1} … {d2}: рынок×день {sum(1 for r in chunk if r[3] == 'market')}, "
                  f"ASIN×день {sum(1 for r in chunk if r[3] == 'asin')}")
        except Exception as e:
            sa_failures.append(f"{d1}…{d2}: {e}"); print(f"  ✗ {d1} … {d2}: {str(e)[:300]}")
        d1 = d2 + timedelta(days=1)

# ── запись: сырьё, затем Lakebase; каждый кусок — своё соединение (добор истории бывает долгим) ──
sa_stats = []
for d1, d2, chunk in sa_all:
    mk_rows = [r for r in chunk if r[3] == "market"]; as_rows = [r for r in chunk if r[3] == "asin"]
    by_mk = {}
    for r in mk_rows:
        by_mk.setdefault(r[2], [0, 0]); by_mk[r[2]][0] += r[5]
    for r in as_rows:
        by_mk.setdefault(r[2], [0, 0]); by_mk[r[2]][1] += r[5]
    sa_stats.append((d1, d2, by_mk))
    print(f"  {d1} … {d2}: сессии рынка / сумма по ASIN — " +
          ", ".join(f"{cc} {a}/{b}" for cc, (a, b) in sorted(by_mk.items())))
    if SA_DRY or not chunk:
        continue
    sdf = spark.createDataFrame(
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in chunk],
        "date DATE, marketplace_id STRING, marketplace STRING, level STRING, asin STRING, sessions BIGINT, "
        "page_views BIGINT, feature_offer_pct DOUBLE").withColumn("loaded_at", F.current_timestamp())
    if not spark.catalog.tableExists(SA_RAW):
        sdf.limit(0).write.format("delta").saveAsTable(SA_RAW)
        spark.sql(f"COMMENT ON TABLE {SA_RAW} IS 'Data Kiosk Seller Analytics, блок трафика: сессии и просмотры по рынку "
                  f"(level = market) и по ASIN (level = asin) × день. Пишет Kabinet - Sales & Traffic Replica, ячейка 2.'")
    sdf.write.format("delta").mode("overwrite").option("replaceWhere", f"date >= '{d1}' AND date <= '{d2}'").saveAsTable(SA_RAW)

    c = sa_pg(); cur2 = c.cursor()
    try:
        # дневные сессии рынка — только в существующие дни (строку дня создаёт ячейка 1)
        psycopg2.extras.execute_values(cur2, """UPDATE kabinet_data.sales_traffic_daily t
            SET sessions = v.s, page_views = v.pv FROM (VALUES %s) v(d, m, s, pv)
            WHERE t.snapshot_date = v.d AND t.marketplace = v.m""",
            [(r[0], r[2], r[5], r[6]) for r in mk_rows], template="(%s::date, %s, %s, %s)", page_size=1000)
        upd_daily = cur2.rowcount
        # Amazon публикует трафик с задержкой: последнего дня окна (вчера) в ответе обычно ещё нет НИ ПО ОДНОМУ рынку.
        # Такой день — «не знаем», а не ноль (13.10.2026 утренний прогон записал 12.10 нулём по всем рынкам, и CVR
        # недельного отчёта посчитал бы его днём без посетителей). Поэтому ноль ставится только по последний день,
        # который есть в ответе хоть по одному рынку, а дни после него в окне куска — пусто
        pub_end = max((r[0] for r in mk_rows), default=None)
        all_mk = sorted(set(SA_MK.values()))
        zero_daily = 0
        if pub_end is not None:
            # день, которого нет в ответе по рынку, — день без трафика: ноль, а не пусто (пусто = «не знаем»)
            cur2.execute("""UPDATE kabinet_data.sales_traffic_daily t SET sessions = 0, page_views = 0
                            WHERE t.snapshot_date BETWEEN %s AND %s AND t.marketplace = ANY(%s)
                              AND NOT (t.snapshot_date, t.marketplace) IN (SELECT d, m FROM unnest(%s::date[], %s::text[]) AS u(d, m))""",
                         (d1, pub_end, all_mk, [r[0] for r in mk_rows], [r[2] for r in mk_rows]))
            zero_daily = cur2.rowcount
        unpub_from = (pub_end + timedelta(days=1)) if pub_end is not None else d1
        cur2.execute("""UPDATE kabinet_data.sales_traffic_daily SET sessions = NULL, page_views = NULL
                        WHERE snapshot_date BETWEEN %s AND %s AND marketplace = ANY(%s)""", (unpub_from, d2, all_mk))
        unpub_daily = cur2.rowcount
        # по ASIN: всё окно куска из ответа; ASIN, которого в ответе нет, в этот день сессий не имел
        cur2.execute("CREATE TEMP TABLE _sa (d date, m text, asin text, s int, pv int) ON COMMIT DROP")
        psycopg2.extras.execute_values(cur2, "INSERT INTO _sa VALUES %s",
                                       [(r[0], r[2], r[4], r[5], r[6]) for r in as_rows if r[4]], page_size=2000)
        cur2.execute("""INSERT INTO kabinet_data.sales_traffic_asin
                          (snapshot_date, marketplace, asin, sku, sessions, page_views, units_ordered, ordered_sales,
                           buy_box_pct, sessions_source, loaded_at)
                        SELECT d, m, asin, NULL, s, pv, 0, 0, NULL, 'seller_analytics', now() FROM _sa
                        ON CONFLICT (snapshot_date, marketplace, asin) DO UPDATE SET
                          sessions = EXCLUDED.sessions, page_views = EXCLUDED.page_views,
                          sessions_source = EXCLUDED.sessions_source, loaded_at = now()""")
        ups_asin = cur2.rowcount
        zero_asin = 0
        if pub_end is not None:
            cur2.execute("""UPDATE kabinet_data.sales_traffic_asin t
                            SET sessions = 0, page_views = 0, sessions_source = 'seller_analytics', loaded_at = now()
                            WHERE t.snapshot_date BETWEEN %s AND %s AND t.marketplace = ANY(%s)
                              AND NOT EXISTS (SELECT 1 FROM _sa WHERE _sa.d = t.snapshot_date AND _sa.m = t.marketplace
                                              AND _sa.asin = t.asin)""",
                         (d1, pub_end, all_mk))
            zero_asin = cur2.rowcount
        # неопубликованные дни по ASIN — тоже «не знаем»: строки, заведённые только ради сессий (без SKU и продаж),
        # уходят, у строк с продажами сессии пустеют
        cur2.execute("""DELETE FROM kabinet_data.sales_traffic_asin
                        WHERE snapshot_date BETWEEN %s AND %s AND marketplace = ANY(%s)
                          AND sessions_source = 'seller_analytics' AND sku IS NULL AND COALESCE(units_ordered, 0) = 0""",
                     (unpub_from, d2, all_mk))
        cur2.execute("""UPDATE kabinet_data.sales_traffic_asin SET sessions = NULL, page_views = NULL, sessions_source = NULL
                        WHERE snapshot_date BETWEEN %s AND %s AND marketplace = ANY(%s)
                          AND sessions_source = 'seller_analytics'""", (unpub_from, d2, all_mk))
        c.commit()
        print(f"    записано: дней рынка {upd_daily} (без трафика {zero_daily}), ASIN×день {ups_asin}, без сессий {zero_asin}; "
              f"ещё не опубликовано с {unpub_from} по {d2}: дней рынка {unpub_daily}")
    finally:
        c.close()

if SA_DRY:
    # проба: итоги по рынкам и дням, ASIN — только по Испании (для сверки с сырьём)
    dbutils.notebook.exit(json.dumps({
        "chunks": [[str(a), str(b), m] for a, b, m in sa_stats], "failures": sa_failures,
        "market_days": [[str(r[0]), r[2], r[5], r[6]] for _, _, ch in sa_all for r in ch if r[3] == "market"],
        "es_asin_days": [[str(r[0]), r[4], r[5]] for _, _, ch in sa_all for r in ch if r[3] == "asin" and r[2] == "ES"],
    }, ensure_ascii=False))

if sa_failures:
    _tag = "[QUOTA_429] " if any("[QUOTA_429]" in f for f in sa_failures) else ""
    raise RuntimeError(_tag + "Сессии Seller Analytics не загружены: " + "; ".join(sa_failures)[:1500])
