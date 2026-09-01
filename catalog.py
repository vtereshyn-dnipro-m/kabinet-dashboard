# catalog.py — сведения о товаре, общие для всех страниц
"""ASIN по артикулу — один источник на весь Кабинет.

Страницы приходят к товару с разных сторон: где-то есть готовый ASIN,
где-то только SKU, а на «Дозаказе», «Инцидентах» и «Площадках» ASIN не
приходит вовсе. Чтобы ссылка на карточку была везде одинаковой, связь
живёт здесь, а не собирается заново на каждой странице.
"""
import re

import pandas as pd
import streamlit as st

from db.connection import get_connection
from i18n import t
from links import AMAZON_DOMAIN, amazon_url
from util import as_text

# Рынок для ссылки, когда своего у страницы нет. ASIN у Amazon общий на
# всю Европу, поэтому карточка откроется та же — меняется только витрина
FALLBACK_MARKET = "ES"


def asin_column(label: str = "ASIN"):
    """Колонка ASIN-ссылки, одинаковая во всех таблицах Кабинета.

    display_text вырезает ASIN из адреса: в ячейке стоит сам код, а не
    слово «открыть», — и колонка остаётся тем же ASIN, каким была, просто
    кликабельным. Отдельный столбец со стрелкой ради этого не нужен."""
    return st.column_config.LinkColumn(
        label, display_text=r"/dp/([A-Z0-9]{10})", width="small",
        help=t("catalog.asin_help"))


def base_sku(sku) -> str:
    """Числовая часть артикула — общий ключ между витринами.

    В разных таблицах один товар записан как 11111, 11111-FBA и
    DM-11111-ES. Связывать их можно только по числу внутри."""
    m = re.search(r"(\d{5,})", as_text(sku))
    return m.group(1) if m else ""


@st.cache_data(ttl=600)
def asin_by_sku() -> dict:
    """Артикул → ASIN. Пустой словарь, если справочник недоступен:
    страница должна остаться рабочей без ссылок, а не упасть целиком."""
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT sku_group, MAX(asin) AS asin
            FROM kabinet_data.sku_asin_map
            WHERE asin IS NOT NULL
            GROUP BY sku_group
        """, conn)
    except Exception:
        return {}
    finally:
        conn.close()
    return dict(zip(df["sku_group"].astype(str), df["asin"].astype(str)))


# Серая рамка вместо пустой ячейки. Картинка инлайновая: внешняя
# заглушка означала бы сетевой запрос ради того, чтобы показать «ничего»,
# и ломалась бы ровно тогда, когда сеть и так подводит
NO_PHOTO = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'>"
    "<rect width='64' height='64' rx='8' fill='%23e9edf2'/>"
    "<path d='M16 44l10-13 7 9 5-6 10 10z' fill='%23b9c4d0'/>"
    "<circle cx='24' cy='24' r='5' fill='%23b9c4d0'/></svg>"
)


# Один и тот же рынок записан в базе тремя способами: economics_summary
# и listing_cards держат код страны (DE), orders_history — имя канала
# (Amazon.de), asin_reviews_daily — хвост домена (de, co.uk). Последний
# ломался тише всех: «co.uk» не код страны, поэтому британские строки
# теряли и заголовок, и ссылку — она молча уезжала на испанскую витрину.
# Таблицу хвостов выводим из справочника доменов, а не пишем заново
_SUFFIX = {}
for _code, _dom in AMAZON_DOMAIN.items():
    _SUFFIX.setdefault(_dom.split(".", 1)[1], _code)


def _mk(v) -> str:
    """Код рынка, приведённый к виду kabinet_data, из любого из трёх."""
    v = as_text(v).strip()
    low = v.lower()
    if low.startswith("amazon."):
        low = low[len("amazon."):]
    return _SUFFIX.get(low, v.upper())


@st.cache_data(ttl=600)
def listing_cards() -> pd.DataFrame:
    """Карточки листингов: заголовок и главное фото по рынку.

    Единственный источник, где заголовок снят с самой витрины. До этого
    название бралось из economics_summary, а там под немецким рынком
    лежит испанский текст — рынок совпадает, язык нет, и поймать это
    сравнением кодов невозможно.

    Таблица реплицируется из другой Lakebase раз в сутки: кросс-проектных
    запросов Кабинет не делает."""
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT asin, marketplace, title, main_image
            FROM kabinet_data.listing_cards
        """, conn)
    except Exception:
        return pd.DataFrame(columns=["asin", "marketplace", "title",
                                     "main_image"])
    finally:
        conn.close()
    if df.empty:
        return df
    df["asin"] = df["asin"].astype(str).str.strip()
    df["marketplace"] = df["marketplace"].map(_mk)
    return df


@st.cache_data(ttl=600)
def _cards_maps() -> tuple:
    """Три готовых словаря: заголовок по рынку, заголовок по любому рынку
    (с указанием какому) и фото по любому рынку.

    Собираем один раз: словарь на 977 карточек дешевле, чем merge на
    каждой из тринадцати таблиц."""
    df = listing_cards()
    if df.empty:
        return {}, {}, {}
    by_mk, any_title, any_img = {}, {}, {}
    for a, m, ti, im in zip(df["asin"], df["marketplace"], df["title"],
                            df["main_image"]):
        if ti and str(ti) not in ("None", "nan"):
            by_mk[(a, m)] = str(ti)
            any_title.setdefault(a, (m, str(ti)))
        if im and str(im) not in ("None", "nan"):
            any_img.setdefault((a, m), str(im))
            any_img.setdefault(a, str(im))
    return by_mk, any_title, any_img


def title_for(asin, market):
    """Заголовок с витрины этого рынка. Возвращает (текст, метка): метка
    пустая, если рынок совпал, иначе код рынка, откуда взят текст."""
    by_mk, any_title, _ = _cards_maps()
    a, m = str(asin), _mk(market)
    ti = by_mk.get((a, m))
    if ti:
        return ti, ""
    alt = any_title.get(a)
    return (alt[1], alt[0]) if alt else (None, "")


def image_series(asins=None, skus=None, markets=None) -> list:
    """Ссылки на фото для колонки таблицы.

    Принимает то же, что url_series: готовые ASIN, артикулы или и то и
    другое. Нет фото — заглушка, а не пустая ячейка: пустота в первой
    колонке читается как сбой вёрстки, а не как отсутствие данных."""
    _, _, any_img = _cards_maps()
    m = asin_by_sku() if skus is not None else {}
    n = len(asins if asins is not None else skus)
    asins = list(asins) if asins is not None else [None] * n
    skus = list(skus) if skus is not None else [None] * n
    markets = list(markets) if markets is not None else [None] * n
    out = []
    for a, s_, mk in zip(asins, skus, markets):
        if a is None or str(a) in ("None", "nan", ""):
            a = m.get(base_sku(s_), "")
        a = str(a)
        out.append(any_img.get((a, _mk(mk))) or any_img.get(a) or NO_PHOTO)
    return out


def image_column(label: str = ""):
    """Колонка фото, одинаковая во всех таблицах Кабинета."""
    return st.column_config.ImageColumn(label, width="small",
                                        help=t("catalog.photo_help"))


@st.cache_data(ttl=600)
def sku_by_asin() -> dict:
    """ASIN → артикул. Нужен поиску: человек ищет тем кодом, который у
    него в буфере, и это чаще артикул, чем ASIN."""
    return {a: s for s, a in asin_by_sku().items()}


def _first_market(markets) -> str:
    """Первый амазоновский рынок из списка «где продавалось».

    Список идёт по убыванию продаж, но брать просто первый нельзя: сверху
    может стоять Mirakl-канал, у которого домена нет. Каждый элемент
    сперва приводим к коду страны — иначе британское «co.uk» не опознаётся
    и строка уезжает на испанскую витрину."""
    for m in as_text(markets).split(","):
        code = _mk(m)
        if code in AMAZON_DOMAIN:
            return code
    return ""


def url_series(skus=None, asins=None, markets=None) -> list:
    """Ссылки на карточки для колонки таблицы.

    Принимает что есть: готовые ASIN, артикулы или и то и другое. Рынок
    берётся из строки, и из него — первый амазоновский: сверху списка
    может стоять Mirakl-канал, у которого домена нет, и товар остался бы
    без ссылки при живом листинге на Amazon."""
    # Справочник нужен всегда, когда есть артикулы: даже при готовой
    # колонке ASIN часть строк приходит пустыми, и добирать их неоткуда
    m = asin_by_sku() if skus is not None else {}
    n = len(asins if asins is not None else skus)
    asins = list(asins) if asins is not None else [None] * n
    skus = list(skus) if skus is not None else [None] * n
    markets = list(markets) if markets is not None else [None] * n
    out = []
    for a, s, mk in zip(asins, skus, markets):
        if a is None or str(a) in ("None", "nan", ""):
            a = m.get(base_sku(s), "")
        out.append(amazon_url(_first_market(mk) or FALLBACK_MARKET, a))
    return out
