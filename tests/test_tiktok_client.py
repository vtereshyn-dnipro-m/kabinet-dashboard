"""Клиент TikTok Shop (`nb/tiktok_client.py`): подпись, белый список путей, токены, секреты не утекают в ошибки.

Без сети: requests подменяется. Подпись проверяется по правилам TikTok Shop API 202309+ (путь + отсортированные
«ключ значение» без sign/access_token + тело, обёртка секретом, HMAC-SHA256); на живом API её подтверждает проверочный
запрос в ноутбуке обмена.
"""
import hashlib
import hmac
import json
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import tiktok_client as tt  # noqa: E402

SECRET = "s3cr3t-value"


def test_sign_matches_rules():
    params = {"timestamp": 1700000000, "app_key": "k", "shop_cipher": "C", "sign": "x", "access_token": "t"}
    body = '{"a":1}'
    base = "/order/202309/orders/search" + "app_keykshop_cipherCtimestamp1700000000" + body
    want = hmac.new(SECRET.encode(), (SECRET + base + SECRET).encode(), hashlib.sha256).hexdigest()
    assert tt.sign("/order/202309/orders/search", params, SECRET, body) == want


def test_sign_ignores_sign_and_token_and_order():
    a = tt.sign("/p", {"b": 2, "a": 1}, SECRET)
    b = tt.sign("/p", {"a": 1, "b": 2, "sign": "zzz", "access_token": "tok"}, SECRET)
    assert a == b


@pytest.mark.parametrize("method,path", [
    ("GET", "/authorization/202309/shops"),
    ("POST", "/order/202309/orders/search"),
    ("POST", "/product/202502/products/search"),
    ("GET", "/product/202309/products/1729"),
    ("GET", "/finance/202501/statements/77/statement_transactions"),
    ("GET", "/logistics/202309/warehouses"),
    ("GET", "/logistics/202309/warehouses/7628307551415093014/delivery_options"),
    ("GET", "/logistics/202309/delivery_options/7357984593359669025/shipping_providers"),
    ("GET", "/product/202309/categories"),
    ("GET", "/product/202309/categories/979848/attributes"),
    ("GET", "/product/202309/categories/979848/rules"),
])
def test_allowed(method, path):
    tt.check_allowed(method, path)


@pytest.mark.parametrize("method,path", [
    ("POST", "/product/202309/products/1/inventory/update"),
    ("POST", "/product/202309/products/1/prices/update"),
    ("PUT", "/product/202509/products/1"),
    ("POST", "/finance/202309/statements"),
    ("GET", "/product/202309/products/1/extra"),
    ("DELETE", "/order/202309/orders/search"),
    ("GET", "/product/202309/products/.."),
    ("GET", "/product/202309/products/1%2Finventory%2Fupdate"),
    ("GET", "/product/202309/products/1?x=1"),
    ("POST", "/order/202309/orders/search\n"),
    ("GET", "/finance/202501/statements//statement_transactions"),
    # логистика и категории — только чтение: запись в логистику и категории и пути вне шаблона не проходят
    ("POST", "/logistics/202309/warehouses"),
    ("POST", "/product/202309/categories/recommend"),
    ("GET", "/product/202309/categories/979848/attributes/1"),
    ("GET", "/logistics/202309/warehouses/../delivery_options"),
    ("POST", "/fulfillment/202309/packages/1/ship"),
    ("GET", "/fulfillment/202309/orders/1/tracking"),
])
def test_not_allowed(method, path):
    with pytest.raises(PermissionError):
        tt.check_allowed(method, path)


def test_as_unix():
    assert tt.as_unix(1800000000) == 1800000000
    assert tt.as_unix(3600, now=1700000000) == 1700003600


def test_explain_auth_error():
    # коды — условные: распознавание идёт по тексту сообщения, коды TikTok в документации не сверены
    assert "СЕКРЕТ НЕВЕРНЫЙ" in tt.explain_auth_error(None, "Invalid app_secret")
    assert "СЕКРЕТ НЕВЕРНЫЙ" in tt.explain_auth_error(None, "app_secret invalid for this auth_code")  # секрет — первым
    assert "код авторизации" in tt.explain_auth_error(None, "auth_code is expired")
    assert "СЕКРЕТ НЕВЕРНЫЙ" in tt.explain_auth_error(None, "something unexpected")         # обмен: секрет — подозреваемый
    assert "СЕКРЕТ" not in tt.explain_auth_error(None, "something unexpected", step="refresh")


@pytest.mark.parametrize("msg,hit", [
    ("access_token is expired", True), ("Invalid access token", True),
    ("page_token is invalid", False), ("Invalid credentials", False), ("Invalid sign", False),
])
def test_token_hint(msg, hit):
    assert bool(tt._TOKEN_HINT.search(msg)) is hit


def test_sign_rejects_non_scalars():
    with pytest.raises(ValueError):
        tt.sign("/p", {"ids": ["1", "2"]}, SECRET)


def test_none_query_dropped(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET, "access-token": "AT", "access-expires": "2000000000"}
    calls = []
    c = _client(store, monkeypatch, [_Resp(200, {"code": 0, "data": {}})], calls)
    c.call("GET", "/finance/202309/statements", {"shop_cipher": "C", "page_token": None})
    assert "page_token" not in calls[0][2]["params"]


def test_401_without_token_message_does_not_refresh(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET, "access-token": "AT", "access-expires": "2000000000",
             "refresh-token": "RT1"}
    c = _client(store, monkeypatch, [_Resp(401, {"code": 105001, "message": "Invalid credentials"})])
    with pytest.raises(tt.TikTokError):
        c.call("GET", "/authorization/202309/shops")
    assert store["refresh-token"] == "RT1"


class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._p = status, payload

    def json(self):
        return self._p


def _client(store, monkeypatch, responses, calls=None):
    seq = iter(responses)

    def fake(method, url, **kw):
        if calls is not None:
            calls.append((method, url, kw))
        return next(seq)
    monkeypatch.setattr(tt.requests, "request", fake)
    return tt.TikTokClient(store.get, store.__setitem__, log=lambda *a: None, sleep=lambda s: None)


def _tokens(at="AT2", rt="RT2"):
    return {"code": 0, "data": {"access_token": at, "refresh_token": rt, "access_token_expire_in": 2000000000,
                                "refresh_token_expire_in": 2100000000, "seller_name": "S", "seller_base_region": "ES"}}


def test_exchange_saves_tokens_and_returns_no_tokens(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET}
    c = _client(store, monkeypatch, [_Resp(200, _tokens("AT1", "RT1"))])
    out = c.exchange_auth_code("CODE")
    assert store["access-token"] == "AT1" and store["refresh-token"] == "RT1"
    assert store["access-expires"] == 2000000000 and store["refresh-expires"] == 2100000000
    assert "AT1" not in json.dumps(out) and "RT1" not in json.dumps(out)


def test_auth_error_has_no_secret(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET}
    c = _client(store, monkeypatch, [_Resp(200, {"code": 36004004, "message": "invalid app_secret"})])
    with pytest.raises(tt.TikTokError) as e:
        c.exchange_auth_code("CODE")
    assert "СЕКРЕТ НЕВЕРНЫЙ" in str(e.value) and SECRET not in str(e.value) and "CODE" not in str(e.value)


def test_network_error_has_no_url(monkeypatch):
    def boom(method, url, **kw):
        raise tt.requests.ConnectionError(f"failed {url}?app_secret={SECRET}&auth_code=CODE")
    monkeypatch.setattr(tt.requests, "request", boom)
    c = tt.TikTokClient({"app-key": "K", "app-secret": SECRET}.get, lambda k, v: None, log=lambda *a: None)
    with pytest.raises(ConnectionError) as e:
        c.exchange_auth_code("CODE")
    assert SECRET not in str(e.value) and "CODE" not in str(e.value)
    assert e.value.__context__ is None and e.value.__cause__ is None     # исходной ошибки с URL в цепочке нет


def test_expiring_access_refreshes_and_rotates_refresh(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET, "access-token": "AT1", "refresh-token": "RT1",
             "access-expires": "1", "refresh-expires": "2100000000"}
    calls = []
    c = _client(store, monkeypatch, [_Resp(200, _tokens()), _Resp(200, {"code": 0, "data": {"shops": [{"id": "1"}]}})],
                calls)
    assert c.get_authorized_shops() == [{"id": "1"}]
    assert store["refresh-token"] == "RT2" and store["access-token"] == "AT2"
    assert calls[1][2]["headers"]["x-tts-access-token"] == "AT2"
    assert "access_token" not in calls[1][2]["params"]


def test_refresh_token_save_failure_is_loud(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET, "refresh-token": "RT1", "access-expires": "1"}

    def put(k, v):
        raise IOError("scope write denied")
    monkeypatch.setattr(tt.requests, "request", lambda *a, **kw: _Resp(200, _tokens()))
    c = tt.TikTokClient(store.get, put, log=lambda *a: None, sleep=lambda s: None)
    with pytest.raises(tt.TokenSaveError):
        c.get_authorized_shops()


def test_post_body_signed_as_sent(monkeypatch):
    store = {"app-key": "K", "app-secret": SECRET, "access-token": "AT", "access-expires": "2000000000"}
    calls = []
    c = _client(store, monkeypatch, [_Resp(200, {"code": 0, "data": {"orders": [], "next_page_token": ""}})], calls)
    list(c.pages("POST", "/order/202309/orders/search", "orders", {"shop_cipher": "C"}, {"update_time_ge": 1}))
    _, _, kw = calls[0]
    sent = kw["data"].decode()
    assert kw["params"]["sign"] == tt.sign("/order/202309/orders/search", kw["params"], SECRET, sent)


def test_write_path_never_sent(monkeypatch):
    calls = []
    c = _client({"app-key": "K", "app-secret": SECRET, "access-token": "AT", "access-expires": "2000000000"},
                monkeypatch, [], calls)
    with pytest.raises(PermissionError):
        c.call("POST", "/product/202309/products/1/prices/update", body={"x": 1})
    assert calls == []
