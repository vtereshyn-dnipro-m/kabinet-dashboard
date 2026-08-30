# links.py — ссылки на карточки товара
"""Домен Amazon зависит от страны, а не от привычки.

Ссылка вида amazon.es/dp/... для немецкого листинга открывает чужую
витрину или пустую страницу, поэтому домен берётся по коду рынка. Не-
амазоновские каналы ссылки не получают вовсе: у Mirakl карточка живёт по
другому адресу, и подставлять туда ASIN бессмысленно.
"""

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
