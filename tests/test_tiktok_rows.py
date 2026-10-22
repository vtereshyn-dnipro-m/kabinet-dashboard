"""Строки сырья TikTok Shop (`nb/tiktok_rows.py`): персональные данные покупателя не доходят до таблиц, деньги и время
приводятся верно, ключи на месте."""
import datetime as dt
import json
import os
import sys
from decimal import Decimal

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import tiktok_rows as tr  # noqa: E402

SHOP = {"id": "111", "region": "ES"}
SALT = "test-salt"
AT = dt.datetime(2026, 10, 22, 12, 0)
PII = ("Juan Pérez", "+34600111222", "juan@example.com", "juanito", "Calle Mayor 1", "X1234567", "secret note", "U-777")

ORDER = {
    "id": "O1", "status": "COMPLETED", "create_time": 1760000000, "update_time": 1760003600, "paid_time": 1760000100,
    "buyer_email": PII[2], "buyer_nickname": PII[3], "buyer_avatar": "https://img/a.png", "buyer_message": PII[6],
    "cpf": PII[5], "cpf_name": PII[0], "user_id": PII[7],
    "recipient_address": {"name": PII[0], "phone_number": PII[1], "full_address": PII[4], "address_line1": PII[4],
                          "first_name": "Juan", "last_name": "Pérez", "postal_code": "28001", "region_code": "ES"},
    "payment": {"currency": "EUR", "total_amount": "59.90", "sub_total": "54.90", "shipping_fee": "5.00",
                "seller_discount": "", "platform_discount": "0"},
    "line_items": [{"id": "L1", "sku_id": "S1", "seller_sku": "19420000", "product_id": "P1", "sale_price": "54.90",
                    "original_price": "59.90", "currency": "EUR", "display_status": "COMPLETED"}],
}


def test_order_has_no_pii_anywhere():
    head, lines = tr.order_rows(SHOP, ORDER, AT, SALT)
    blob = json.dumps([head, lines], default=str, ensure_ascii=False)
    for value in PII + ("Juan", "Pérez", "img/a.png"):
        assert value not in blob, value
    assert json.loads(head["raw_json"])["recipient_address"] == {"postal_code": "28001", "region_code": "ES"}
    assert head["postal_code"] == "28001"


def test_order_values():
    head, lines = tr.order_rows(SHOP, ORDER, AT, SALT)
    assert (head["shop_id"], head["region"], head["order_id"]) == ("111", "ES", "O1")
    assert head["total_amount"] == Decimal("59.90") and head["seller_discount"] is None
    assert head["platform_discount"] == Decimal("0.00")
    assert head["create_time"] == dt.datetime(2025, 10, 9, 8, 53, 20)          # UTC без пояса
    assert head["line_items_count"] == 1
    assert lines[0]["line_item_id"] == "L1" and lines[0]["seller_sku"] == "19420000"
    assert lines[0]["sale_price"] == Decimal("54.90")


def test_original_order_not_mutated():
    before = json.dumps(ORDER, sort_keys=True)
    tr.order_rows(SHOP, ORDER, AT, SALT)
    assert json.dumps(ORDER, sort_keys=True) == before


def test_product_rows():
    p = {"id": "P1", "title": "Taladro", "status": "ACTIVATE", "update_time": 1760000000,
         "skus": [{"id": "S1", "seller_sku": "19420000", "price": {"currency": "EUR", "sale_price": "54.90"},
                   "inventory": [{"quantity": 3, "warehouse_id": "W1"}, {"quantity": 2, "warehouse_id": "W2"}]},
                  {"id": "S2", "seller_sku": "19420001", "price": {}, "inventory": []}]}
    head, skus = tr.product_rows(SHOP, p, AT)
    assert head["skus_count"] == 2 and skus[0]["inventory_quantity"] == 5 and skus[1]["inventory_quantity"] is None
    assert skus[0]["sale_price"] == Decimal("54.90") and skus[1]["sale_price"] is None


def test_finance_rows():
    st = tr.statement_row(SHOP, {"id": "ST1", "statement_time": 1760000000, "currency": "EUR",
                                 "settlement_amount": "100.10", "payment_status": "PAID"}, AT)
    assert st["settlement_amount"] == Decimal("100.10") and st["payment_status"] == "PAID"
    t = tr.transaction_row(SHOP, "ST1", "EUR", {"id": "T1", "type": "ORDER", "order_id": "O1",
                                                "settlement_amount": "-3.20"}, AT)
    assert (t["statement_id"], t["transaction_id"], t["order_id"]) == ("ST1", "T1", "O1")
    assert t["settlement_amount"] == Decimal("-3.20") and t["currency"] == "EUR"


def test_windows():
    assert list(tr.windows(0, 10 * 86400, 7)) == [(0, 7 * 86400), (7 * 86400, 10 * 86400)]
    assert list(tr.windows(5, 5, 7)) == []


def test_buyer_hash():
    import hashlib
    import pytest
    head, _ = tr.order_rows(SHOP, ORDER, AT, SALT)
    assert head["buyer_hash"] == hashlib.sha256(("test-salt" + "U-777").encode()).hexdigest()
    assert tr.order_rows(SHOP, {**ORDER, "user_id": None}, AT, SALT)[0]["buyer_hash"] is None
    assert tr.buyer_hash("other-salt", "U-777") != head["buyer_hash"]
    with pytest.raises(ValueError):
        tr.order_rows(SHOP, ORDER, AT, "")
