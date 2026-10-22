# TikTok Shop Partner API — клиент Кабинета (22.10.2026, решение владельца: «TikTok Shop — подключаем, только чтение»).
#
# Обычный Python-модуль, не ноутбук: его импортируют ноутбуки TikTok (обмен кода, загрузчик) и тесты CI. В Databricks
# лежит рядом с ними файлом рабочей области (`tiktok_client.py`) — ноутбук добавляет свою папку в sys.path.
#
# Что здесь и почему так:
# - Только чтение. Клиент вызывает только пути из ALLOWED; любой другой путь или метод — ошибка ДО запроса. POST —
#   ровно два поиска (заказы и товары): у TikTok они есть только как POST, данных не меняют (решение владельца
#   22.10.2026). Всё остальное — GET.
# - Подпись (HMAC-SHA256, правила TikTok Shop API 202309+): из query убираются `sign` и `access_token`, остальное —
#   по ключу, склейка «ключ+значение», спереди путь, сзади тело JSON (если есть), обёртка app_secret с двух сторон,
#   HMAC-SHA256 с ключом app_secret, hex. Токен — в заголовке `x-tts-access-token`, в подпись не входит. Тело
#   сериализуется ОДИН раз: подписывается и уходит та же строка.
# - Токены живут в скоупе `tiktok-shop`: `access-token`, `refresh-token`, `access-expires`, `refresh-expires` (unix,
#   секунды). Access обновляется, когда до конца меньше REFRESH_BEFORE_S, и один раз — на ошибку токена. TikTok при
#   каждом обновлении выдаёт НОВЫЙ refresh-токен: его записываем сразу и с повторами; не записался — прогон падает
#   с TokenSaveError (старый refresh уже может не действовать → повторная авторизация владельцем).
# - Секреты не попадают в вывод и в тексты ошибок. app_secret и auth_code уходят в query запросов авторизации, а
#   исключения requests печатают URL — поэтому сетевые ошибки перехватываются и поднимаются без URL, а
#   raise_for_status() не вызывается. Ответ с токенами не печатается и в ошибку не кладётся.
# - shop_cipher не хранится: каждый прогон берёт его из get_authorized_shops(). Магазинов может быть несколько
#   (позже добавятся страны) — методы принимают магазин параметром.
#
# Источник кода — nb/tiktok_client.py в kabinet-dashboard.
import hashlib
import hmac
import json
import logging
import re
import time

import requests

API = "https://open-api.tiktokglobalshop.com"
AUTH = "https://auth.tiktok-shops.com"
SCOPE = "tiktok-shop"

# urllib3 на уровне DEBUG пишет полный URL запроса (у авторизации в нём app_secret и auth_code) — не ниже WARNING.
logging.getLogger("urllib3").setLevel(logging.WARNING)

ALLOWED = (
    ("GET", "/authorization/202309/shops"),
    ("POST", "/order/202309/orders/search"),
    ("GET", "/order/202507/orders"),
    ("GET", "/order/202407/orders/{order_id}/price_detail"),
    ("POST", "/product/202502/products/search"),
    ("GET", "/product/202309/products/{product_id}"),
    ("GET", "/finance/202309/statements"),
    ("GET", "/finance/202501/statements/{statement_id}/statement_transactions"),
    ("GET", "/finance/202501/orders/{order_id}/statement_transactions"),
)

REFRESH_BEFORE_S = 48 * 3600        # access живёт ~7 суток; обновляем, когда осталось меньше двух
TIMEOUT_S = 60
RETRIES_429 = 4                      # паузы 5, 10, 20, 40 с
SAVE_RETRIES = 3

# Распознавание причин — по тексту сообщения TikTok: коды ошибок авторизации в доступной документации не сверены.
# Нераспознанная причина обмена всё равно называет секрет главным подозреваемым (explain_auth_error).
_SECRET_HINT = re.compile(r"app[_ ]?secret|app[_ ]?key|\bsign(ature)?\b", re.I)
_CODE_HINT = re.compile(r"auth[_ ]?code|authori[sz]ation code", re.I)
# Только ошибка САМОГО access-токена: не page_token, не «Invalid credentials» без слова access, не любой HTTP 401.
_TOKEN_HINT = re.compile(r"access[_ ]?token\b.*\b(expired|invalid)|\b(expired|invalid)\b.*access[_ ]?token", re.I)


class TikTokError(Exception):
    """Ошибка API без секретов: путь, HTTP, код и сообщение TikTok, request_id."""

    def __init__(self, path, http, code=None, message="", request_id=None):
        self.path, self.http, self.code, self.message, self.request_id = path, http, code, message or "", request_id
        super().__init__(f"{path}: HTTP {http}, code={code}, {self.message[:300]} (request_id={request_id})")


class TokenSaveError(Exception):
    pass


def sign(path, params, app_secret, body=""):
    """Подпись запроса. body — та же строка, что уходит в запрос ("" для GET). Значения query — только скаляры:
    None и списки requests отправляет иначе, чем они подписались бы, поэтому они отклоняются (None — убирает call)."""
    q = {k: v for k, v in params.items() if k not in ("sign", "access_token")}
    bad = [k for k, v in q.items() if v is None or isinstance(v, (list, tuple, dict, set))]
    if bad:
        raise ValueError(f"query: значения {bad} — не скаляры, подпись не совпала бы с запросом")
    base = path + "".join(f"{k}{q[k]}" for k in sorted(q)) + (body or "")
    return hmac.new(app_secret.encode(), (app_secret + base + app_secret).encode(), hashlib.sha256).hexdigest()


def _template_re(template):
    # id в пути — только буквы, цифры, «_» и «-»: «..», «%2F», «?», перевод строки в id не пройдут
    return re.compile(re.sub(r"\\\{[a-z_]+\\\}", "[A-Za-z0-9_-]+", re.escape(template)))


_ALLOWED_RE = [(m, _template_re(t)) for m, t in ALLOWED]


def check_allowed(method, path):
    if not isinstance(path, str) or not any(m == method and rx.fullmatch(path) for m, rx in _ALLOWED_RE):
        raise PermissionError(f"{method} {path} — не в белом списке клиента TikTok (только чтение)")


def as_unix(value, now=None):
    """Срок из ответа TikTok — unix-время; на случай длительности (меньше 10^9) — прибавляем к сейчас."""
    v = int(value)
    return v if v >= 10 ** 9 else int(now if now is not None else time.time()) + v


def explain_auth_error(code, message, step="exchange"):
    """Понятная причина отказа обмена или обновления токена — для владельца, без значений секретов. Секрет
    проверяется ПЕРВЫМ; нераспознанный отказ обмена тоже называет секрет главным подозреваемым."""
    m = message or ""
    tail = f" [TikTok: code={code}, {m[:200]}]"
    if _SECRET_HINT.search(m):
        return "СЕКРЕТ НЕВЕРНЫЙ: TikTok отверг app-key или app-secret из скоупа tiktok-shop — перезаписать их" + tail
    if _CODE_HINT.search(m):
        return ("код авторизации неверный, уже использован или истёк — открыть ссылку авторизации заново и сразу "
                "запустить обмен" + tail)
    if step == "refresh" and re.search(r"refresh", m, re.I):
        return "refresh-токен не принят (истёк или уже заменён) — нужна повторная авторизация" + tail
    if step == "exchange":
        return ("обмен отклонён, причина не распознана. Если код авторизации свежий (получен минуты назад) — "
                "вероятнее всего СЕКРЕТ НЕВЕРНЫЙ: перезаписать app-key и app-secret в скоупе tiktok-shop" + tail)
    return "TikTok отказал" + tail


def _http(method, url, **kw):
    """requests без утечки URL (в нём app_secret и auth_code у запросов авторизации) в текст ошибки. Новая ошибка
    поднимается ПОСЛЕ блока except: так у неё нет __context__ с исходным исключением и его URL."""
    try:
        return requests.request(method, url, timeout=TIMEOUT_S, **kw)
    except requests.RequestException as e:
        kind = type(e).__name__
    raise ConnectionError(f"{method} {url.split('?')[0]}: сеть — {kind}")


def _json(r, path):
    try:
        return r.json()
    except ValueError:
        pass
    raise TikTokError(path, r.status_code, None, "ответ не JSON")


class TikTokClient:
    """get_secret(key) -> str | None, put_secret(key, value) — доступ к скоупу (в Databricks — from_databricks)."""

    def __init__(self, get_secret, put_secret, log=print, sleep=time.sleep):
        self._get, self._put, self._log, self._sleep = get_secret, put_secret, log, sleep
        self.app_key = get_secret("app-key")
        self._app_secret = get_secret("app-secret")
        if not self.app_key or not self._app_secret:
            raise RuntimeError("в скоупе tiktok-shop нет app-key или app-secret")

    @classmethod
    def from_databricks(cls, dbutils, **kw):
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()

        def get(k):
            try:
                return dbutils.secrets.get(SCOPE, k)
            except Exception as e:
                text = str(e)
            # «ключа нет» — нормальный случай (до первого обмена токенов нет); отказ в доступе — не он
            if re.search(r"does not exist|not found|RESOURCE_DOES_NOT_EXIST", text, re.I):
                return None
            raise PermissionError(f"скоуп {SCOPE}, ключ {k}: чтение не удалось — {text[:200]}")

        return cls(get, lambda k, v: ws.secrets.put_secret(SCOPE, k, string_value=str(v)), **kw)

    # ── токены ──────────────────────────────────────────────────────────────────────────────────────────────────
    def _save_tokens(self, d):
        """Записать токены ответа. Первым — refresh: старый после обновления уже может не действовать."""
        now = int(time.time())
        items = [("refresh-token", d["refresh_token"]), ("access-token", d["access_token"]),
                 ("refresh-expires", as_unix(d["refresh_token_expire_in"], now)),
                 ("access-expires", as_unix(d["access_token_expire_in"], now))]
        for key, value in items:
            for attempt in range(1, SAVE_RETRIES + 1):
                try:
                    self._put(key, value)
                    break
                except Exception as e:
                    if attempt == SAVE_RETRIES:
                        raise TokenSaveError(
                            f"не записан {key} в скоуп {SCOPE} ({type(e).__name__}) — если это refresh-token, старый "
                            f"уже может не действовать: нужна повторная авторизация") from None
                    self._sleep(2 * attempt)
        return {"access_expires": items[3][1], "refresh_expires": items[2][1]}

    def _auth_call(self, path, params):
        r = _http("GET", AUTH + path, params={"app_key": self.app_key, "app_secret": self._app_secret, **params})
        j = _json(r, path)
        if r.status_code != 200 or j.get("code") != 0:
            step = "refresh" if path.endswith("/refresh") else "exchange"
            raise TikTokError(path, r.status_code, j.get("code"), explain_auth_error(j.get("code"), j.get("message"), step),
                              j.get("request_id"))
        return j["data"]

    def exchange_auth_code(self, auth_code):
        """Одноразовый код → токены в скоуп. Возвращает только безопасные поля (без токенов)."""
        d = self._auth_call("/api/v2/token/get", {"auth_code": auth_code, "grant_type": "authorized_code"})
        out = self._save_tokens(d)
        out.update({k: d.get(k) for k in ("seller_name", "seller_base_region", "user_type", "granted_scopes")})
        return out

    def refresh(self):
        rt = self._get("refresh-token")
        if not rt:
            raise RuntimeError("в скоупе нет refresh-token — сначала обмен кода (Kabinet - TikTok Auth Exchange)")
        d = self._auth_call("/api/v2/token/refresh", {"refresh_token": rt, "grant_type": "refresh_token"})
        out = self._save_tokens(d)
        self._token = d["access_token"]
        self._log(f"токен обновлён: access до {fmt_ts(out['access_expires'])}, refresh до {fmt_ts(out['refresh_expires'])}")
        return out

    def expiries(self):
        def num(k):
            v = self._get(k)
            return int(v) if v else None
        return {"access_expires": num("access-expires"), "refresh_expires": num("refresh-expires")}

    def _access_token(self):
        if getattr(self, "_token", None):
            return self._token
        exp = self.expiries()["access_expires"]
        if not exp or exp - time.time() < REFRESH_BEFORE_S:
            self.refresh()
            return self._token
        self._token = self._get("access-token")
        if not self._token:
            self.refresh()
        return self._token

    # ── запросы ─────────────────────────────────────────────────────────────────────────────────────────────────
    def call(self, method, path, query=None, body=None, _retried=False):
        check_allowed(method, path)
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        query = {k: v for k, v in (query or {}).items() if v is not None}
        for attempt in range(RETRIES_429 + 1):
            params = {"app_key": self.app_key, "timestamp": int(time.time()), **query}
            params["sign"] = sign(path, params, self._app_secret, raw)
            r = _http(method, API + path, params=params, data=raw.encode() if raw else None,
                      headers={"x-tts-access-token": self._access_token(), "content-type": "application/json"})
            if r.status_code == 429 and attempt < RETRIES_429:
                self._sleep(5 * 2 ** attempt)
                continue
            break
        j = _json(r, path)
        if j.get("code") == 0:
            return j.get("data") or {}
        msg = j.get("message") or ""
        if not _retried and _TOKEN_HINT.search(msg):
            self._token = None
            self.refresh()
            return self.call(method, path, query, body, _retried=True)
        if re.search(r"\bsign(ature)?\b", msg, re.I):
            msg = "СЕКРЕТ НЕВЕРНЫЙ или подпись не сошлась (app-secret в скоупе tiktok-shop): " + msg
        raise TikTokError(path, r.status_code, j.get("code"), msg, j.get("request_id"))

    def pages(self, method, path, list_key, query=None, body=None, page_size=50):
        """Все страницы списка: next_page_token → page_token, пока не пусто."""
        token = None
        while True:
            q = {**(query or {}), "page_size": page_size, **({"page_token": token} if token else {})}
            data = self.call(method, path, q, body)
            for item in data.get(list_key) or []:
                yield item
            token = data.get("next_page_token")
            if not token:
                return

    def get_authorized_shops(self):
        """[{id, name, region, seller_type, cipher, code}] — cipher берётся отсюда каждый прогон, не хранится."""
        return self.call("GET", "/authorization/202309/shops").get("shops") or []


def fmt_ts(ts):
    return time.strftime("%d.%m.%Y %H:%M UTC", time.gmtime(int(ts))) if ts else "—"
