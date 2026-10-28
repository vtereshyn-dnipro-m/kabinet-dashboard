"""Клиент Worten (`nb/worten_client.py`): только три GET белого списка, ключ не попадает в ошибки, 429 — пауза и
повтор, постраничный обход по total_count."""
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import worten_client as wc  # noqa: E402

KEY = "secret-worten-key-123"


class R:
    def __init__(self, code, data=None, headers=None, text=""):
        self.status_code, self._data, self.headers, self.text = code, data, headers or {}, text

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


def client(monkeypatch, responses, calls=None, sleeps=None):
    it = iter(responses)

    def fake(method, url, **kw):
        if calls is not None:
            calls.append((method, url, kw))
        return next(it)
    monkeypatch.setattr(wc, "_http", fake)
    return wc.WortenClient(lambda k: KEY, "https://marketplace.worten.pt", 18499,
                           sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/account"), ("GET", "/api/offers"), ("GET", "/api/orders")])
def test_allowed(method, path):
    wc.check_allowed(method, path)


@pytest.mark.parametrize("method,path", [
    ("PUT", "/api/orders/1/accept"), ("PUT", "/api/orders/1/tracking"), ("POST", "/api/offers"),
    ("PUT", "/api/orders"), ("GET", "/api/orders/1/documents"), ("POST", "/api/orders/async-export"),
    ("DELETE", "/api/offers"), ("GET", "/api/orders/"), ("GET", "/api/offers?x=1")])
def test_not_allowed(method, path):
    with pytest.raises(PermissionError):
        wc.check_allowed(method, path)


def test_every_allowed_is_get():
    assert all(m == "GET" for m, _ in wc.ALLOWED)


def test_auth_header_and_shop(monkeypatch):
    calls = []
    c = client(monkeypatch, [R(200, {"shop_id": 18499})], calls)
    assert c.account()["shop_id"] == 18499
    method, url, kw = calls[0]
    assert (method, url) == ("GET", "https://marketplace.worten.pt/api/account")
    assert kw["headers"]["Authorization"] == KEY and kw["params"]["shop_id"] == "18499"


def test_error_has_no_key(monkeypatch):
    c = client(monkeypatch, [R(401, {"message": "Unauthorized"}, text="Unauthorized")])
    with pytest.raises(wc.WortenError) as e:
        c.call("/api/offers")
    assert KEY not in str(e.value) and "401" in str(e.value)


def test_network_error_without_url(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError(f"https://marketplace.worten.pt/api/offers?shop_id=18499 {KEY}")
    monkeypatch.setattr(wc.requests, "request", boom)
    c = wc.WortenClient(lambda k: KEY, "https://marketplace.worten.pt", 18499)
    with pytest.raises(wc.WortenError) as e:
        c.call("/api/offers")
    assert KEY not in str(e.value) and "worten.pt" not in str(e.value)


def test_429_retry_after(monkeypatch):
    sleeps = []
    c = client(monkeypatch, [R(429, {}, {"Retry-After": "7"}), R(200, {"offers": [], "total_count": 0})], sleeps=sleeps)
    assert c.call("/api/offers") == {"offers": [], "total_count": 0}
    assert sleeps == [7.0]


def test_pages_by_total_count(monkeypatch):
    calls = []
    c = client(monkeypatch, [R(200, {"offers": [{"offer_id": i} for i in range(2)], "total_count": 3}),
                             R(200, {"offers": [{"offer_id": 2}], "total_count": 3})], calls)
    got = [o["offer_id"] for o in c.pages("/api/offers", "offers", page_max=2)]
    assert got == [0, 1, 2] and [k["params"]["offset"] for _, _, k in calls] == [0, 2]


def test_no_key_refuses():
    with pytest.raises(RuntimeError):
        wc.WortenClient(lambda k: None, "https://x", 1)
