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
from links import amazon_url, first_amazon

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
    m = re.search(r"(\d{5,})", str(sku or ""))
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


@st.cache_data(ttl=600)
def sku_by_asin() -> dict:
    """ASIN → артикул. Нужен поиску: человек ищет тем кодом, который у
    него в буфере, и это чаще артикул, чем ASIN."""
    return {a: s for s, a in asin_by_sku().items()}


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
        out.append(amazon_url(first_amazon(mk) or FALLBACK_MARKET, a))
    return out
