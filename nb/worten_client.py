# Worten Marketplace (Mirakl) — клиент Кабинета (28.10.2026, решение владельца: «подключи Worten по API тем же путём,
# что TikTok»; docs/worten.md).
#
# Обычный Python-модуль, не ноутбук: его импортирует ноутбук `Kabinet - Worten Loader` и тесты CI. В Databricks лежит
# рядом с ним файлом рабочей области (`worten_client.py`).
#
# Что здесь и почему так:
# - Только чтение. Клиент вызывает только пути из ALLOWED — три GET Mirakl Seller API: A01 магазин, OF21 офферы, OR11
#   заказы. Любой другой путь или метод (принять заказ OR21, трекинг, правка оффера) — ошибка ДО запроса.
# - Авторизация Mirakl — ключ в заголовке `Authorization` (без «Bearer»), магазин — параметром `shop_id`. Ключ — из
#   скоупа `worten` (`api-key`), его кладёт владелец; адрес API и магазин не секрет — в reorder_params / параметрах.
# - Ключ не попадает в вывод и в тексты ошибок: сетевые ошибки перехватываются и поднимаются без URL и заголовков,
#   raise_for_status() не вызывается.
# - 429 — пауза по `Retry-After` (не больше RETRY_MAX_WAIT_S) и повтор, не больше RETRIES_429 раз.
# - Постранично: `max` (до 100) и `offset`, пока не набрано `total_count` или страница не пришла пустой.
# Источник кода — nb/worten_client.py в kabinet-dashboard.
import logging
import re
import time

import requests

SCOPE = "worten"
ALLOWED = (
    ("GET", "/api/account"),
    ("GET", "/api/offers"),
    ("GET", "/api/orders"),
)
TIMEOUT_S = 60
RETRIES_429 = 4
RETRY_MAX_WAIT_S = 120
PAGE_MAX = 100

# urllib3 на уровне DEBUG пишет полный URL запроса — не ниже WARNING
logging.getLogger("urllib3").setLevel(logging.WARNING)


class WortenError(Exception):
    """Ошибка API без секретов: путь, HTTP и короткий текст ответа."""

    def __init__(self, path, http, message=""):
        self.path, self.http, self.message = path, http, message or ""
        super().__init__(f"{path}: HTTP {http}, {self.message[:300]}")


def check_allowed(method, path):
    if not isinstance(path, str) or (method, path) not in ALLOWED:
        raise PermissionError(f"{method} {path} — не в белом списке клиента Worten (только чтение)")


def _http(method, url, **kw):
    try:
        return requests.request(method, url, timeout=TIMEOUT_S, **kw)
    except requests.RequestException as e:          # без URL: в нём параметры, в заголовках — ключ
        raise WortenError(re.sub(r"https?://[^/]+", "", url), "сеть", type(e).__name__) from None


class WortenClient:
    """get_secret(key) -> str | None — доступ к скоупу; base_url и shop_id — из настроек."""

    def __init__(self, get_secret, base_url, shop_id, sleep=time.sleep):
        self._key = get_secret("api-key")
        if not self._key:
            raise RuntimeError("в скоупе worten нет api-key — ключ кладёт владелец (docs/worten.md)")
        self.base_url, self.shop_id, self._sleep = base_url.rstrip("/"), str(shop_id), sleep

    @classmethod
    def from_databricks(cls, dbutils, base_url, shop_id, **kw):
        return cls(lambda k: dbutils.secrets.get(SCOPE, k), base_url, shop_id, **kw)

    def call(self, path, params=None):
        check_allowed("GET", path)
        q = {"shop_id": self.shop_id, **{k: v for k, v in (params or {}).items() if v is not None}}
        for attempt in range(RETRIES_429 + 1):
            r = _http("GET", self.base_url + path, params=q,
                      headers={"Authorization": self._key, "Accept": "application/json"})
            if r.status_code == 429 and attempt < RETRIES_429:
                try:
                    wait = min(float(r.headers.get("Retry-After") or 0) or 5 * 2 ** attempt, RETRY_MAX_WAIT_S)
                except ValueError:
                    wait = 5 * 2 ** attempt
                self._sleep(wait)
                continue
            break
        if r.status_code != 200:
            raise WortenError(path, r.status_code, (r.text or "")[:200])
        try:
            return r.json()
        except ValueError:
            raise WortenError(path, r.status_code, "ответ не JSON") from None

    def pages(self, path, list_key, params=None, page_max=PAGE_MAX):
        """Все страницы списка: offset += max, пока не набран total_count или страница не пустая."""
        offset, seen = 0, 0
        while True:
            data = self.call(path, {**(params or {}), "max": page_max, "offset": offset})
            items = data.get(list_key) or []
            for it in items:
                yield it
            seen += len(items)
            total = data.get("total_count")
            if not items or (total is not None and seen >= int(total)):
                return
            offset += page_max

    def account(self):
        return self.call("/api/account")
