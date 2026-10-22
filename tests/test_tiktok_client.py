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
])
def test_not_allowed(method, path):
    with pytest.raises(PermissionError):
        tt.check_allowed(method, path)


def test_as_unix():
    assert tt.as_unix(1800000000) == 1800000000
    assert tt.as_unix(3600, now=1700000000) == 1700003600


def test_explain_auth_error():
    assert "СЕКРЕТ НЕВЕРНЫЙ" in tt.explain_auth_error(36004004, "Invalid app_secret")
    assert "код авторизации" in tt.explain_auth_error(36004009, "auth_code is expired")


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
