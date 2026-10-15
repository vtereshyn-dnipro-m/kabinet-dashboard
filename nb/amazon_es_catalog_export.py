# Databricks notebook source
# MAGIC %md
# MAGIC # Kabinet - Amazon ES Catalog Export
# MAGIC
# MAGIC Параметр `marketplace` (с 15.10.2026): ES (по умолчанию), FR, IT, DE — тот же файл по другому рынку
# MAGIC Amazon, `amazon_<рынок>_catalog_latest.xlsx` в своей папке. Без параметра — Испания, как раньше.
# MAGIC
# MAGIC Выгрузка для Марко: все наши товары на Amazon ES — SKU, ASIN, EAN и ссылки на все изображения
# MAGIC (главное, затем PT01, PT02… отдельными колонками) — в Excel. С 07.10.2026 в том же листе не только
# MAGIC активные, но и неактивные и незавершённые листинги (Марко спросил, можно ли выгружать и их):
# MAGIC колонки Status и Inactive reason, порядок — Active, Inactive, Incomplete. Запускается вручную
# MAGIC кнопкой «Run now» у джобы; расписания нет.
# MAGIC
# MAGIC **Откуда что берётся**
# MAGIC - Перечень товаров — сегодняшний отчёт листингов Amazon (`raw_amazon_get_merchant_listings_all_data`,
# MAGIC   его грузит джоба Дарины «FBA Fees + Listings» в 06:15), только `Spain (ES)`, статусы `Active`,
# MAGIC   `Inactive` и `Incomplete` — статус берётся из отчёта как есть.
# MAGIC - Inactive reason — проблемы листинга из SP-API Listings Items 2021-08-01 (`issues`, на английском),
# MAGIC   только у неактивных и незавершённых. Нет проблем в ответе — колонка пуста: причину не додумываем.
# MAGIC   Строки `amzn.gr.…` — это SKU, которые Amazon сам заводит под перепродажу возвращённых
# MAGIC   товаров (Grade & Resell), а не наши, поэтому их в выгрузке нет.
# MAGIC - EAN — **свежий запрос** SP-API Catalog Items 2022-04-01 (`searchCatalogItems` по 20 ASIN),
# MAGIC   рынок ES. Не старые снимки витрины.
# MAGIC - Изображения (с 14.10.2026, решение владельца) — из НАШЕГО листинга, Listings Items
# MAGIC   (`main_product_image_locator`, `other_product_image_locator_N` → PTNN): то, что мы сами
# MAGIC   загрузили. Каталог Amazon — только если в листинге картинок нет вовсе; нет одного главного —
# MAGIC   главное из каталога. Пустые слоты PT добираются из каталога, только если главное фото
# MAGIC   каталога совпало с нашим, и только снимками, которых в листинге нет. Откуда — Image source.
# MAGIC - EAN, которого нет в каталоге Amazon, берём из справочника SKU Кабинета (`kabinet_data.sku_master`)
# MAGIC   и пишем отдельной колонкой, откуда он. Код ищем как есть и в очищенном виде (без `-FBA`,
# MAGIC   `-FBM`, хвостового `_`, «` 2`» → «`-2`»), но НЕ откатываем к базовому коду: у варианта `-B`
# MAGIC   и у набора `S2_` свой штрихкод, и чужой EAN хуже пустого.
# MAGIC - Изображения из каталога (запасной путь): у каждого варианта Amazon отдаёт несколько размеров —
# MAGIC   берём самый большой (по площади). Порядок колонок: главное (MAIN), затем PT01, PT02… по номеру. Образцы цвета
# MAGIC   (SWCH) и прочие служебные варианты в колонки не идут — их число видно в сводке.
# MAGIC - Check (с 14.10.2026) — сверка каждой строки с живыми данными перед сохранением файла:
# MAGIC   ASIN из отчёта листингов против живого листинга (Listings Items), есть ли ASIN в каталоге,
# MAGIC   есть ли главное фото в листинге. Пусто — строка подтвердилась.
# MAGIC   О фото на странице товара Check НИЧЕГО не говорит (с 14.10.2026 вечера, решение владельца):
# MAGIC   главное фото каталога (Catalog Items API) — не то, что видит покупатель. Проверка 14.10:
# MAGIC   у пяти активных SKU с пометкой «фото другого товара» на живой странице был тот же товар
# MAGIC   другим снимком (наборы и коды одного товара делят фото), а 58614000 по ссылке открывал
# MAGIC   соседа SA i120 — это переадресация страницы, не фото каталога. Сравнение главного фото
# MAGIC   каталога с нашим (по содержимому, dHash) осталось внутренним: по нему добираются слоты PT.
# MAGIC
# MAGIC **Куда** — `/Volumes/dnipro_m/dnipro_m/kabinet_raw/exports/amazon_es_catalog/`: файл с датой
# MAGIC выгрузки и копия `…_latest.xlsx`. Пульса и правила живости у джобы нет намеренно: она не по
# MAGIC расписанию, и правило «нет успеха N часов» горело бы каждый день, когда выгрузку просто не
# MAGIC просили.
# MAGIC
# MAGIC Параметр `limit` — сколько товаров взять (0 = все); `probe` = 1 — полный прогон без замены
# MAGIC `…_latest.xlsx`. Пробный файл помечен TEST и в имени (`TEST_amazon_es_catalog_…`), и внутри
# MAGIC (листы «TEST …», первая строка сводки) — чтобы его нельзя было отправить по ошибке.

# COMMAND ----------

# Ячейка 1: вся работа. Самодостаточна.
#
# Ячейки с `%pip` нет намеренно: зависимости объявлены в спецификации окружения джобы, а
# `restartPython()` рядом с ней роняет прогон SIGABRT (AGENTS.md).
import io, json, re, shutil, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import psycopg2
from PIL import Image   # сверка фото по содержимому; без Pillow прогон падает, а не пишет «не проверено»

# Файл для Марко — на английском (решение владельца 06.10.2026): заголовки, значения «откуда EAN»,
# названия листов и сводка. Значения источника — константы, по ним же считается сводка.
SRC_AMAZON, SRC_DIR, SRC_NONE = "Amazon catalog", "SKU directory", "none"
# Откуда картинки строки: наш листинг (что мы сами загрузили) главнее каталога Amazon — решение
# владельца 14.10.2026: каталог у неактивного варианта отдаёт фото соседа по семейству.
IMG_LISTING, IMG_LISTING_CAT_MAIN, IMG_CATALOG = "Our listing", "Our listing, main image from Amazon catalog", "Amazon catalog"
IMG_LISTING_CAT_EXTRA = "Our listing + extra images from Amazon catalog"
import requests
from databricks.sdk import WorkspaceClient
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

PG_HOST = "ep-delicate-cherry-d2nabn27.database.us-east-1.cloud.databricks.com"
PG_EP = "projects/kabinet-dashboard/branches/production/endpoints/primary"
EP = "https://sellingpartnerapi-eu.amazon.com"
# рынок — параметр `marketplace`; ES по умолчанию, чтобы прежний запуск джобы давал прежний файл
MARKETS = {"ES": ("A1RKKUPIHCS9HS", "Spain (ES)", "amazon.es"), "FR": ("A13V1IB3VIYZZH", "France (FR)", "amazon.fr"),
           "IT": ("APJ6JRA9NG5V4", "Italy (IT)", "amazon.it"), "DE": ("A1PA6795UKMFR9", "Germany (DE)", "amazon.de")}
try:
    dbutils.widgets.text("marketplace", "ES")  # noqa: F821
    MK = (dbutils.widgets.get("marketplace") or "ES").strip().upper()  # noqa: F821
except Exception:
    MK = "ES"
if MK not in MARKETS:
    raise ValueError(f"marketplace={MK}: известны {', '.join(MARKETS)}")
MP, MP_NAME, DOMAIN = MARKETS[MK]
mk = MK.lower()
SELLER_ID = "A4JU8NB3VJG0K"   # один на весь европейский аккаунт (AGENTS.md, Buy Box)
STATUS_ORDER = {"Active": 0, "Inactive": 1, "Incomplete": 2}
# getListingsItem: 5 запросов в секунду с запасом 10 — 0,25 с между запросами
LI_PAUSE_SEC = 0.25
OUT_DIR = f"/Volumes/dnipro_m/dnipro_m/kabinet_raw/exports/amazon_{mk}_catalog"
# searchCatalogItems: 2 запроса в секунду с запасом 2. Берём с запасом — 0,6 с между запросами.
PAUSE_SEC = 0.6
# Два фото считаются одним снимком, если разность хешей (dHash 16×16, 256 бит) не больше этого.
# Не настройка, а допуск метода, выверенный на данных 14.10.2026: перекодированный Amazon снимок
# даёт 0–24 (371 пара — ровно 0, две — 8 и 24), разные снимки — от 32 до 142; между ними пусто.
IMG_SAME_MAX_BITS = 24

try:
    dbutils.widgets.text("limit", "0")  # noqa: F821
    LIMIT = int(dbutils.widgets.get("limit") or 0)  # noqa: F821
except Exception:
    LIMIT = 0
try:
    dbutils.widgets.text("probe", "0")  # noqa: F821
    PROBE = (dbutils.widgets.get("probe") or "0").strip() == "1"  # noqa: F821
except Exception:
    PROBE = False

KYIV = timezone(timedelta(hours=3))
now = datetime.now(KYIV)
stamp = now.strftime("%Y-%m-%d")
stamp_human = now.strftime("%Y-%m-%d %H:%M")

# ── 1. листинги рынка из сегодняшнего отчёта: активные, неактивные, незавершённые ───
lst = spark.sql(f"""
    WITH last AS (SELECT max(report_date) AS d
                  FROM dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data
                  WHERE marketplace_name = '{MP_NAME}')
    SELECT DISTINCT l.seller_sku,
           coalesce(l.asin1, CASE WHEN l.product_id_type = '1' THEN l.product_id END) AS asin,
           l.fulfillment_channel, l.report_date, l.status
    FROM dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data l, last
    WHERE l.marketplace_name = '{MP_NAME}' AND l.status IN ('Active', 'Inactive', 'Incomplete')
      AND l.report_date = last.d AND l.seller_sku NOT LIKE 'amzn.gr.%'
""").toPandas()  # noqa: F821
listing_date = str(lst["report_date"].iloc[0]) if len(lst) else "—"
lst["_ord"] = lst["status"].map(STATUS_ORDER)
lst = lst.sort_values(["_ord", "seller_sku"]).reset_index(drop=True)
n_grade = spark.sql(f"""
    SELECT count(*) FROM dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data
    WHERE marketplace_name = '{MP_NAME}' AND status IN ('Active', 'Inactive', 'Incomplete')
      AND seller_sku LIKE 'amzn.gr.%'
      AND report_date = (SELECT max(report_date) FROM dnipro_m.dnipro_m.raw_amazon_get_merchant_listings_all_data
                         WHERE marketplace_name = '{MP_NAME}')
""").collect()[0][0]  # noqa: F821
if LIMIT:
    # проба: понемногу каждого статуса, чтобы проверить и колонку причины
    lst = lst.groupby("status", group_keys=False).head(LIMIT).reset_index(drop=True)
print(f"листингов {MK}: {len(lst)} (отчёт от {listing_date}; amzn.gr.* исключено: {n_grade})")
no_asin = lst[lst["asin"].isna()]
asins = sorted(set(lst["asin"].dropna()))

# ── 2. SP-API Catalog Items ────────────────────────────────────────────────────
def sec(k):
    return dbutils.secrets.get("amazon-sp-api", k)  # noqa: F821

_lwa = requests.post("https://api.amazon.com/auth/o2/token", data={
    "grant_type": "refresh_token", "refresh_token": sec("refresh-token"),
    "client_id": sec("lwa-app-id"), "client_secret": sec("lwa-client-secret")}, timeout=30)
_lwa.raise_for_status()
HDR = {"x-amz-access-token": _lwa.json()["access_token"]}

def search(batch):
    """Один запрос на ≤20 ASIN. На 429 ждём нарастающе, до ~5 минут в сумме, потом падаем."""
    params = {"identifiers": ",".join(batch), "identifiersType": "ASIN", "marketplaceIds": MP,
              "includedData": "identifiers,images,summaries,relationships", "pageSize": 20}
    wait = 2.0
    for _ in range(9):
        r = requests.get(f"{EP}/catalog/2022-04-01/items", headers=HDR, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(wait); wait = min(wait * 2, 60); continue
        r.raise_for_status()
        return r.json().get("items", [])
    raise RuntimeError(f"[QUOTA_429] searchCatalogItems: квота не освободилась, батч {batch[:3]}…")

items = {}
for i in range(0, len(asins), 20):
    for it in search(asins[i:i + 20]):
        items[it["asin"]] = it
    time.sleep(PAUSE_SEC)
print(f"ASIN запрошено {len(asins)}, в каталоге найдено {len(items)}")

# ── 2б. живой листинг: Listings Items — ASIN, наше главное фото, проблемы листинга ───
# Один запрос на SKU по ВСЕМ строкам: issues нужны для причины неактивности, summaries и
# attributes — для сверки строки перед сохранением (колонка Check).
from urllib.parse import quote

def listing_live(sku):
    """{asin, imgs, parent, issues}; None — листинга нет в Listings API (404).
    imgs — картинки, которые мы сами загрузили в листинг: {"MAIN": ссылка, "PT01": …}."""
    url = f"{EP}/listings/2021-08-01/items/{SELLER_ID}/{quote(sku, safe='')}"
    params = {"marketplaceIds": MP, "includedData": "summaries,attributes,issues", "issueLocale": "en_US"}
    wait = 2.0
    for _ in range(9):
        r = requests.get(url, headers=HDR, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(wait); wait = min(wait * 2, 60); continue
        if r.status_code == 404:
            return None          # листинга нет в Listings API — ни причины, ни сверки, не додумываем
        r.raise_for_status()
        js = r.json()
        out = []
        for i in js.get("issues", []) or []:
            msg = str(i.get("message") or "").strip()
            if msg:
                sev = str(i.get("severity") or "").strip()
                out.append(f"{sev}: {msg}" if sev else msg)
        summ = next((s_ for s_ in js.get("summaries") or [] if s_.get("marketplaceId") == MP), {})
        attrs = js.get("attributes") or {}
        imgs = {}
        for k, v in attrs.items():
            m = re.fullmatch(r"other_product_image_locator_(\d+)", k)
            slot = "MAIN" if k == "main_product_image_locator" else (f"PT{int(m.group(1)):02d}" if m else None)
            loc = [x for x in v or [] if x.get("marketplace_id") in (None, MP) and x.get("media_location")]
            if slot and loc:
                imgs[slot] = loc[0]["media_location"]
        return {"asin": summ.get("asin"), "imgs": imgs,
                "parent": any(x.get("value") == "parent" for x in attrs.get("parentage_level") or []),
                "issues": "; ".join(dict.fromkeys(out)) or None}
    raise RuntimeError(f"[QUOTA_429] getListingsItem: квота не освободилась, SKU {sku}")

live = {}
for r in lst.itertuples():
    live[r.seller_sku] = listing_live(r.seller_sku)
    time.sleep(LI_PAUSE_SEC)
reasons = {k: (v or {}).get("issues") for k, v in live.items()}
print(f"Listings Items: запрошено {len(live)}, нет в API {sum(1 for v in live.values() if v is None)}, "
      f"с причиной у неактивных {sum(1 for r in lst.itertuples() if r.status != 'Active' and reasons.get(r.seller_sku))}")

def ean_from_catalog(it):
    found = []
    for blk in it.get("identifiers", []):
        if blk.get("marketplaceId") != MP:
            continue
        for x in blk.get("identifiers", []):
            t, v = x.get("identifierType"), str(x.get("identifier") or "").strip()
            if t == "EAN" and v:
                found.append(v)
            elif t == "GTIN" and len(v) == 14 and v.startswith("0"):
                found.append(v[1:])          # GTIN-14 с ведущим нулём — тот же EAN-13
    return list(dict.fromkeys(found))

def pt_key(variant):
    if variant == "MAIN":
        return (0, 0)
    m = re.fullmatch(r"PT(\d+)", variant or "")
    return (1, int(m.group(1))) if m else None

def images(it):
    """{вариант: ссылка на самый большой размер}; служебные варианты считаем отдельно."""
    best, other = {}, set()
    for blk in it.get("images", []):
        if blk.get("marketplaceId") != MP:
            continue
        for im in blk.get("images", []):
            v = im.get("variant")
            if pt_key(v) is None:
                other.add(v); continue
            area = (im.get("height") or 0) * (im.get("width") or 0)
            if v not in best or area > best[v][0]:
                best[v] = (area, im.get("link"), im.get("width"), im.get("height"))
    return best, other

def relations(it):
    """(контейнер вариаций, вариант семейства) по каталогу рынка."""
    rel = [x for b in it.get("relationships", []) if b.get("marketplaceId") == MP
           for x in b.get("relationships", [])]
    return any(x.get("childAsins") for x in rel), any(x.get("parentAsins") for x in rel)

def title(it):
    for s in it.get("summaries", []):
        if s.get("marketplaceId") == MP:
            return s.get("itemName")
    return None

# ── 3. справочник SKU Кабинета — запасной EAN ──────────────────────────────────
_w = WorkspaceClient()
conn = psycopg2.connect(host=PG_HOST, port=5432, dbname="databricks_postgres",
                        user=_w.current_user.me().user_name,
                        password=_w.postgres.generate_database_credential(endpoint=PG_EP).token,
                        sslmode="require")
cur = conn.cursor()
cur.execute("SELECT sku, ean FROM kabinet_data.sku_master WHERE ean IS NOT NULL AND ean <> ''")
dir_ean = dict(cur.fetchall())
conn.close()

def candidates(sku):
    """Варианты записи того же кода — без отката к базовому: у варианта и набора свой EAN."""
    s = sku.strip()
    c = [s]
    t = re.sub(r"-(FBA|FBM)_?$", "", s)
    t = re.sub(r"_+$", "", t)
    c += [t, t + "_", re.sub(r" (\d)$", r"-\1", t)]
    out = []
    for x in c:
        out.append(x)
        m = re.fullmatch(r"(S\d*_)?(\d{5,7})(-.*)?", x)   # Amazon местами теряет ведущий ноль
        if m:
            out.append((m.group(1) or "") + m.group(2).zfill(8) + (m.group(3) or ""))
    return list(dict.fromkeys(out))

def ean_from_dir(sku):
    for c in candidates(sku):
        if dir_ean.get(c):
            return dir_ean[c], c
    return None, None

# ── 4. строки выгрузки ─────────────────────────────────────────────────────────
rows, other_variants = [], {}
for r in lst.itertuples():
    it = items.get(r.asin) if isinstance(r.asin, str) else None
    eans = ean_from_catalog(it) if it else []
    src, dir_code = None, None
    if eans:
        ean, src = ", ".join(eans), SRC_AMAZON
    else:
        ean, dir_code = ean_from_dir(r.seller_sku)
        src = SRC_DIR if ean else SRC_NONE
    best, other = images(it) if it else ({}, set())
    for v in other:
        other_variants[v] = other_variants.get(v, 0) + 1
    cat_imgs = {v: best[v][1] for v in sorted(best, key=pt_key)}
    lst_imgs = (live.get(r.seller_sku) or {}).get("imgs") or {}
    # Картинки — из нашего листинга; каталог — только если в листинге картинок нет вовсе.
    # Нет в листинге одного главного (4 строки на 14.10) — главное из каталога, и это видно в Image source.
    if lst_imgs:
        imgs = dict(lst_imgs)
        img_src = IMG_LISTING
        if "MAIN" not in imgs and cat_imgs.get("MAIN"):
            imgs["MAIN"], img_src = cat_imgs["MAIN"], IMG_LISTING_CAT_MAIN
    else:
        imgs, img_src = cat_imgs, (IMG_CATALOG if cat_imgs else SRC_NONE)
    order = sorted(imgs, key=pt_key)
    rows.append({
        "sku": r.seller_sku, "asin": r.asin or "", "title": title(it) if it else None,
        "in_catalog": bool(it), "ean": ean or "", "ean_src": src, "ean_multi": len(eans) > 1,
        "imgs": {v: imgs[v] for v in order}, "n_img": len(order), "img_src": img_src,
        "cat_main": cat_imgs.get("MAIN"), "our_main": lst_imgs.get("MAIN"), "cat_imgs": cat_imgs,
        "fc": "FBA" if str(r.fulfillment_channel).startswith("AMAZON") else "FBM",
        "status": r.status, "reason": (reasons.get(r.seller_sku) or "") if r.status != "Active" else "",
        "rel": relations(it) if it else (False, False),
    })


# ── 4б. сверка строки с живыми данными перед сохранением ───────────────────────
# Картинки в файле — из нашего листинга. Сверяем, показывает ли Amazon на странице товара то же
# главное фото: главное фото каталога против главного фото листинга ПО СОДЕРЖИМОМУ — Amazon
# перекодирует снимок, и у одного и того же фото ID разный. Совпадение хеша значит «тот же
# снимок», а не «тот же товар»: обновлённое фото того же товара тоже даёт разность. Поэтому
# отдельно выделяется признак ЧУЖОГО фото: главное фото каталога совпадает с фото другого нашего
# товара (другой базовый код, не контейнер вариаций), а в нашем листинге своё — так у 58614000.
MATCH_SAME, MATCH_DIFF, MATCH_NA, MATCH_PARENT = "Same", "Different", "Not verified", "Not checked (variation parent)"

def img_id(u):
    m = re.search(r"/images/I/([^./]+)", u or "")
    return m.group(1) if m else None

def img_url(u):
    """Уменьшенная копия для хеша; не-Amazon ссылку берём как есть."""
    i = img_id(u)
    return f"https://m.media-amazon.com/images/I/{i}._SL256_.jpg" if i else u

def dhash(u, n=16):
    try:
        r = requests.get(img_url(u), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        g = Image.open(io.BytesIO(r.content)).convert("L").resize((n + 1, n), Image.LANCZOS)
    except Exception:
        return None
    px = list(g.getdata())
    return sum(1 << (y * n + x) for y in range(n) for x in range(n) if px[y * (n + 1) + x] > px[y * (n + 1) + x + 1])

for x in rows:
    lv = live.get(x["sku"])
    x["parent"] = bool((lv or {}).get("parent")) or x["rel"][0]

to_hash = {u for x in rows if not x["parent"] for u in (x["our_main"], x["cat_main"])
           if u and img_id(x["our_main"]) != img_id(x["cat_main"])}
to_hash = sorted(to_hash)
with ThreadPoolExecutor(8) as ex_:
    hashes = dict(zip(to_hash, ex_.map(dhash, to_hash)))

for x in rows:
    lv, chk = live.get(x["sku"]), []   # (вид, текст); вид — для сводки, текст — для получателя
    cat_main, ours = x["cat_main"], x["our_main"]
    if lv is None:
        chk.append(("listing", "Listing not found in Amazon Listings API — row not confirmed"))
    elif lv.get("asin") and x["asin"] and lv["asin"] != x["asin"]:
        chk.append(("listing", f"ASIN differs: listings report {x['asin']}, live listing {lv['asin']}"))
    if not x["in_catalog"]:
        chk.append(("image_na", f"ASIN not found in Amazon {MK} catalog"))
    if x["parent"]:
        x["match"] = MATCH_PARENT
    elif not cat_main:
        x["match"] = MATCH_NA
        if x["in_catalog"] and lv is not None and not ours:
            chk.append(("image_na", "No main image in our listing or in Amazon catalog"))
    elif lv is not None and not ours:
        x["match"] = MATCH_NA
        chk.append(("image_na", "Our listing has no main image — main image is taken from Amazon catalog"))
    elif lv is None:
        x["match"] = MATCH_NA
    elif img_id(ours) == img_id(cat_main):
        x["match"] = MATCH_SAME
    else:
        h1, h2 = hashes.get(ours), hashes.get(cat_main)
        # сравнение главного фото каталога с нашим — только для добора слотов PT (4в), в файл вывода не идёт:
        # фото каталога — не фото живой страницы, и вывод «на странице чужое фото» из него ложный (14.10.2026)
        if h1 is None or h2 is None:
            x["match"] = MATCH_NA
        elif bin(h1 ^ h2).count("1") <= IMG_SAME_MAX_BITS:
            x["match"] = MATCH_SAME
        else:
            x["match"] = MATCH_DIFF
    x["check"] = "; ".join(t for _, t in chk)
    x["chk_kinds"] = {k for k, _ in chk}
    x["inactive_child"] = x["status"] != "Active" and x["rel"][1] and not x["parent"]
# ── 4в. недостающие дополнительные фото — из каталога, но только где страница подтвердила товар ──
# Решение владельца 14.10.2026 (вариант Б): в листинге фото часто меньше, чем показывает Amazon
# (у 123 строк одно вместо 6–9). Где главное фото страницы совпало с нашим (Same) — каталог
# показывает именно наш товар, и пустые слоты PT добираются из него тем же номером слота. Снимок,
# который уже есть среди фото листинга (по содержимому — ID у Amazon разные), второй раз не берётся.
# Где главное фото другое или не проверено — только листинг: так у 58614000 нет ни одного фото соседа.
fill = [x for x in rows if x["match"] == MATCH_SAME and x["img_src"] == IMG_LISTING
        and any(v != "MAIN" and v not in x["imgs"] for v in x["cat_imgs"])]
need = sorted({u for x in fill for u in list(x["imgs"].values())
               + [c_ for v, c_ in x["cat_imgs"].items() if v != "MAIN" and v not in x["imgs"]]} - set(hashes))
with ThreadPoolExecutor(8) as ex_:
    hashes.update(zip(need, ex_.map(dhash, need)))
n_added = 0
for x in fill:
    have = [hashes.get(u) for u in x["imgs"].values()]
    if any(h is None for h in have):
        continue                 # не смогли сравнить с фото листинга — не рискуем задвоить
    added = 0
    for v, u in x["cat_imgs"].items():
        if v == "MAIN" or v in x["imgs"]:
            continue
        h = hashes.get(u)
        if h is None or any(bin(h ^ h2).count("1") <= IMG_SAME_MAX_BITS for h2 in have):
            continue
        x["imgs"][v] = u
        have.append(h)
        added += 1
    if added:
        x["imgs"] = {v: x["imgs"][v] for v in sorted(x["imgs"], key=pt_key)}
        x["img_src"], x["n_img"] = IMG_LISTING_CAT_EXTRA, len(x["imgs"])
        n_added += added
print(f"добрано из каталога: {n_added} фото в {sum(1 for x in rows if x['img_src'] == IMG_LISTING_CAT_EXTRA)} строках")

pt_max = max([max([pt_key(v)[1] for v in x["imgs"] if v != "MAIN"] or [0]) for x in rows] or [0])
img_cols = ["MAIN"] + [f"PT{n:02d}" for n in range(1, pt_max + 1)]

n_check = sum(1 for x in rows if x["check"])
print(f"сверка: в Check {n_check} строк; главное фото каталога против листинга (внутреннее) " + ", ".join(
    f"{m_}: {sum(1 for x in rows if x['match'] == m_)}" for m_ in (MATCH_SAME, MATCH_DIFF, MATCH_NA, MATCH_PARENT)))

# ── 5. Excel ───────────────────────────────────────────────────────────────────
TEST = bool(LIMIT or PROBE)   # пробный файл: TEST в имени, в названиях листов и первой строкой сводки
wb = Workbook()
ws = wb.active
ws.title = f"TEST Amazon {MK}" if TEST else f"Amazon {MK}"
if TEST:
    wb.properties.title = "TEST — trial export, not for sending"
# новые колонки — в конце: прежние не сдвигаются, у получателя ничего не съезжает
head = (["SKU", "ASIN", "EAN", "EAN source"]
        + ["Main image" if c == "MAIN" else c for c in img_cols]
        + ["Export date", "Status", "Inactive reason", "Image source", "Check"])
ws.append(head)
for c in ws[1]:
    c.font = Font(bold=True)
    c.fill = PatternFill("solid", fgColor="DDEBF7")
    c.alignment = Alignment(wrap_text=True, vertical="top")
for x in rows:
    ws.append([x["sku"], x["asin"], x["ean"], x["ean_src"]]
              + [x["imgs"].get(c, "") for c in img_cols]
              + [stamp_human, x["status"], x["reason"], x["img_src"], x["check"]])
    if x["check"]:
        ws.cell(ws.max_row, len(head)).fill = PatternFill("solid", fgColor="FCE4D6")
# коды и штрихкоды — текстом: иначе Excel съест ведущий ноль у 08455000
for row in ws.iter_rows(min_row=2, max_col=3):
    for c in row:
        c.number_format = "@"
widths = [16, 13, 15, 16] + [40] * len(img_cols) + [16, 12, 80, 22, 80]
for i, w_ in enumerate(widths, start=1):
    ws.column_dimensions[ws.cell(1, i).column_letter].width = w_
ws.freeze_panes = "C2"
ws.auto_filter.ref = ws.dimensions

n = len(rows)
n_no_ean_amz = sum(1 for x in rows if x["ean_src"] != SRC_AMAZON)
n_ean_dir = sum(1 for x in rows if x["ean_src"] == SRC_DIR)
n_no_ean = sum(1 for x in rows if x["ean_src"] == SRC_NONE)
n_lt7 = sum(1 for x in rows if x["n_img"] < 7)
n_not_found = sum(1 for x in rows if not x["in_catalog"])
n_multi = sum(1 for x in rows if x["ean_multi"])
summary = ([("TEST FILE", "Trial run — not for sending")] if TEST else []) + [
    ("Export date", stamp_human + " (Kyiv time)"),
    ("Listings report date", listing_date),
    (f"Products in export (all Amazon {MK} SKUs)", n),
    ("  Active", sum(1 for x in rows if x["status"] == "Active")),
    ("  Inactive", sum(1 for x in rows if x["status"] == "Inactive")),
    ("  Incomplete", sum(1 for x in rows if x["status"] == "Incomplete")),
    ("Inactive / Incomplete with a reason from Amazon", sum(1 for x in rows if x["status"] != "Active" and x["reason"])),
    ("Unique ASINs", len({x["asin"] for x in rows if x["asin"]})),
    ("Excluded: amzn.gr.* (Amazon's resale of returned items, not our SKUs)", n_grade),
    (f"ASIN not found in Amazon {MK} catalog", n_not_found),
    ("No EAN in Amazon catalog", n_no_ean_amz),
    ("  of which EAN taken from SKU directory", n_ean_dir),
    ("  of which no EAN anywhere", n_no_ean),
    ("Several EANs in Amazon catalog (comma-separated)", n_multi),
    ("Fewer than 7 images", n_lt7),
    ("Products by number of images (count: products)",
     ", ".join(f"{k}: {v}" for k, v in sorted({k: sum(1 for x in rows if x["n_img"] == k)
                                                for k in {x["n_img"] for x in rows}}.items()))),
    ("Highest additional image slot", f"PT{pt_max:02d}"),
    ("Other image variants (not in columns, e.g. swatches)",
     ", ".join(f"{k}: {v}" for k, v in sorted(other_variants.items())) or "none"),
    ("EAN source values", f"{SRC_AMAZON} — from Amazon catalog; {SRC_DIR} — from our SKU directory "
                          f"when Amazon has none; {SRC_NONE} — not found in either"),
    ("Images", "From our own listing (SP-API Listings Items: the images we uploaded — main image, then PT01, "
               "PT02… by slot). Empty PT slots are filled from Amazon catalog only when Amazon catalog's main "
               "image is the same picture as ours, and only with pictures not already in our listing. Amazon "
               "catalog images for the whole row only when our listing has no images at all"),
    ("Image source", ", ".join(f"{v_}: {sum(1 for x in rows if x['img_src'] == v_)}"
                               for v_ in (IMG_LISTING, IMG_LISTING_CAT_EXTRA, IMG_LISTING_CAT_MAIN, IMG_CATALOG, SRC_NONE))),
    ("Status", "Listing status from Amazon's listings report: Active, Inactive, Incomplete; rows are sorted in that order"),
    ("Inactive reason", "Listing issues from SP-API Listings Items as Amazon returns them (severity: message); "
                        "empty when Amazon returns no issue — nothing is inferred"),
    ("Rows to check (Check is not empty)", n_check),
    ("  No main image in our listing, or ASIN not in Amazon catalog",
     sum(1 for x in rows if "image_na" in x["chk_kinds"])),
    ("  ASIN or listing not confirmed by Listings API",
     sum(1 for x in rows if "listing" in x["chk_kinds"])),
    ("Not buyable variants of a family (Inactive / Incomplete)",
     f"{sum(1 for x in rows if x['inactive_child'])} — {DOMAIN}/dp/<ASIN> may open another, buyable variant of the "
     f"same family; the row data belongs to the ASIN in the row, not to the page that opens"),
    ("Check", "Checked against live Amazon data before the file was saved: ASIN against the live listing, "
              "ASIN in Amazon catalog, main image in our listing. Empty — the row is confirmed; otherwise the "
              "reason is given. Check says nothing about the photo shown on the Amazon product page"),
    ("Source", f"SP-API Catalog Items 2022-04-01 and Listings Items 2021-08-01, {DOMAIN.capitalize()}, fresh request at export time"),
]
s2 = wb.create_sheet("TEST Summary" if TEST else "Summary")
for k, v in summary:
    s2.append([k, v])
s2.column_dimensions["A"].width = 70
s2.column_dimensions["B"].width = 60
for c in s2["A"]:
    c.font = Font(bold=True)

import os
os.makedirs(OUT_DIR, exist_ok=True)
if TEST:
    s2["A1"].font = Font(bold=True, color="C00000")
    s2["B1"].font = Font(bold=True, color="C00000")
tmp = f"/tmp/amazon_{mk}_catalog_{stamp}.xlsx"
wb.save(tmp)
name = f"{'TEST_' if TEST else ''}amazon_{mk}_catalog_{stamp}.xlsx"
shutil.copy(tmp, f"{OUT_DIR}/{name}")
if not TEST:
    shutil.copy(tmp, f"{OUT_DIR}/amazon_{mk}_catalog_latest.xlsx")
print(f"✅ {OUT_DIR}/{name}")

result = {"marketplace": MK, "file": f"{OUT_DIR}/{name}", "rows": n, "asins": len(asins), "not_found": n_not_found,
          "no_ean_amazon": n_no_ean_amz, "ean_from_dir": n_ean_dir, "no_ean": n_no_ean,
          "multi_ean": n_multi, "lt7": n_lt7, "pt_max": pt_max, "other_variants": other_variants,
          "listing_date": listing_date,
          "by_status": {s_: sum(1 for x in rows if x["status"] == s_) for s_ in STATUS_ORDER},
          "with_reason": {s_: sum(1 for x in rows if x["status"] == s_ and x["reason"]) for s_ in STATUS_ORDER}, "grade_excluded": int(n_grade), "no_asin_listings": len(no_asin),
          "img_hist": {k: sum(1 for x in rows if x["n_img"] == k) for k in sorted({x["n_img"] for x in rows})},
          "no_ean_list": [x["sku"] for x in rows if x["ean_src"] == SRC_NONE][:60],
          "test": TEST, "check_rows": n_check,
          "catalog_main_vs_listing": {m_: sum(1 for x in rows if x["match"] == m_) for m_ in (MATCH_SAME, MATCH_DIFF, MATCH_NA, MATCH_PARENT)},
          "inactive_children": sum(1 for x in rows if x["inactive_child"]),
          "img_src": {v_: sum(1 for x in rows if x["img_src"] == v_) for v_ in (IMG_LISTING, IMG_LISTING_CAT_EXTRA, IMG_LISTING_CAT_MAIN, IMG_CATALOG, SRC_NONE)},
          "check_kinds": {k_: sum(1 for x in rows if k_ in x["chk_kinds"]) for k_ in ("image_na", "listing")}}
print(json.dumps(result, ensure_ascii=False))
dbutils.notebook.exit(json.dumps(result, ensure_ascii=False))  # noqa: F821
