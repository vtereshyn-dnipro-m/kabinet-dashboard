# links.py — ссылки на карточки товара
"""Домен Amazon зависит от страны, а не от привычки.

Ссылка вида amazon.es/dp/... для немецкого листинга открывает чужую
витрину или пустую страницу, поэтому домен берётся по коду рынка. Не-
амазоновские каналы ссылки не получают вовсе: у Mirakl карточка живёт по
другому адресу, и подставлять туда ASIN бессмысленно.
"""

from i18n import t

# Идентификаторы рынков Amazon — константы самого Amazon, одни и те же
# для всех продавцов. В БД им места нет: девять строк, которые никогда не
# поменяются, — это лишняя сущность, которую надо заводить, наполнять и
# помнить. Значение здесь — код страны, чтобы связаться с доменами ниже
MARKETPLACE_ID = {
    "A1RKKUPIHCS9HS": "ES",
    "A1PA6795UKMFR9": "DE",
    "APJ6JRA9NG5V4": "IT",
    "A13V1IB3VIYZZH": "FR",
    "A1F83G8C2ARO7P": "UK",
    "A1805IZSGTT6HS": "NL",
    "A1C3SOZRARQ6R3": "PL",
    "A2NODRKZP88ZB9": "SE",
    "AMEN7PMS3EDWL": "BE",
}


def market_name(mid) -> str:
    """Название рынка по идентификатору Amazon.

    Незнакомый код возвращаем как есть: показать сырой идентификатор
    честнее, чем подписать его чужой страной, — а заодно видно, что в
    справочник добавился новый рынок."""
    code = MARKETPLACE_ID.get(str(mid or "").strip().upper())
    return t("market." + code) if code else (str(mid or "").strip() or "—")


AMAZON_DOMAIN = {
    "ES": "amazon.es", "DE": "amazon.de", "FR": "amazon.fr", "IT": "amazon.it",
    "NL": "amazon.nl", "BE": "amazon.com.be", "SE": "amazon.se", "PL": "amazon.pl",
    "IE": "amazon.ie", "UK": "amazon.co.uk", "GB": "amazon.co.uk",
}


def amazon_url(marketplace: str, asin) -> str:
    """Ссылка на листинг. Пустая строка, а не None: LinkColumn печатает
    None текстом, и в колонке появляется слово «None»."""
    dom = AMAZON_DOMAIN.get(str(marketplace or "").upper())
    if not dom or asin is None or str(asin) in ("None", "nan", ""):
        return ""
    return f"https://www.{dom}/dp/{asin}"


def first_amazon(markets) -> str:
    """Первый амазоновский рынок из списка «где продавалось».

    Список идёт по убыванию продаж, и брать просто первый нельзя: сверху
    может стоять Mirakl-канал, у которого домена нет, и товар остался бы
    без ссылки при живом листинге на Amazon."""
    for m in str(markets or "").split(","):
        m = m.strip().upper()
        if m in AMAZON_DOMAIN:
            return m
    return ""
