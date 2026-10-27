"""Строки возвратов и отмен TikTok Shop (`nb/tiktok_rows.py`, шаг 2): адрес склада возврата, трек-номер, перевозчик,
доля покупателя за обратную доставку и картинки не попадают ни в колонки, ни в raw_json; строка — позиция; деньги и
время приводятся верно. Формы ответов — по пробам 27.10.2026 на живом API (только чтение), значения выдуманы."""
import datetime as dt
import json
import os
import sys
from decimal import Decimal

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import tiktok_rows as tr  # noqa: E402

SHOP = {"id": "111", "region": "ES"}
AT = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.timezone.utc)
LEAKS = ("Calle Falsa 9", "TRK-RET-777", "Seur Devoluciones", "7185068232208811777", "4.50", "https://img/p.png",
         "thumb.png", "brand_new_field_value")

RETURN = {
    "return_id": "R1", "order_id": "O1", "combined_return_id": "0", "is_combined_return": False,
    "return_type": "RETURN_AND_REFUND", "return_status": "BUYER_SHIPPED_ITEM", "role": "BUYER",
    "return_reason": "ecom_order_delivered_refund_and_return_reason_defective_uk",
    "return_reason_text": "Product is defective or doesn't work", "return_method": "PLATFORM_SHIPPED",
    "handover_method": "DROP_OFF", "shipment_type": "PLATFORM", "create_time": 1792951410, "update_time": 1793038079,
    "refund_amount": {"currency": "EUR", "refund_shipping_fee": "0", "refund_subtotal": "50.99", "refund_tax": "0",
                      "refund_total": "50.99"},
    "discount_amount": [{"currency": "EUR", "product_platform_discount": "0", "product_seller_discount": "19",
                         "shipping_fee_platform_discount": "0", "shipping_fee_seller_discount": "0"}],
    "shipping_fee_amount": [{"currency": "EUR", "buyer_paid_return_shipping_fee": "4.50",
                             "platform_paid_return_shipping_fee": "0", "seller_paid_return_shipping_fee": "3.99"}],
    "return_provider_id": "7185068232208811777", "return_provider_name": "Seur Devoluciones",
    "return_tracking_number": "TRK-RET-777", "return_warehouse_address": {"full_address": "Calle Falsa 9, Madrid"},
    "seller_next_action_response": [{"action": "SELLER_RESPOND_RECEIVE_PACKAGE", "deadline": 1795623314}],
    "brand_new_field": "brand_new_field_value",
    "return_line_items": [
        {"return_line_item_id": "RL1", "order_line_item_id": "OL1", "sku_id": "S1", "seller_sku": "48304000",
         "product_name": "Soldadora Inverter i120", "sku_name": "Predeterminado",
         "product_image": {"url": "https://img/p.png", "thumb_urls": ["thumb.png"], "height": 200, "width": 200},
         "refund_amount": {"currency": "EUR", "refund_subtotal": "50.99", "refund_total": "50.99"}},
        {"return_line_item_id": "RL2", "order_line_item_id": "OL2", "sku_id": "S2", "seller_sku": "41324000",
         "refund_amount": {"currency": "EUR", "refund_subtotal": "", "refund_total": ""}},
    ],
}
CANCEL = {
    "cancel_id": "C1", "order_id": "O2", "cancel_type": "CANCEL", "cancel_status": "CANCELLATION_REQUEST_COMPLETE",
    "cancel_reason": "system_cancel_unpaid_time_out", "cancel_reason_text": "Customer overdue to pay", "role": "SYSTEM",
    "should_replenish_stock": True, "create_time": 1787135384, "update_time": 1787135384,
    "refund_amount": {"currency": "EUR", "refund_total": "0"}, "brand_new_field": "brand_new_field_value",
    "cancel_line_items": [{"cancel_line_item_id": "CL1", "order_line_item_id": "OL9", "sku_id": "S9",
                           "seller_sku": "78060000", "product_name": "Amoladora DGA-201BC", "sku_name": "4Ah",
                           "product_image": {"url": "https://img/p.png"}, "refund_amount": {"refund_total": "0"}}],
}


def test_return_has_no_address_tracking_carrier_buyer_fee_images():
    rows = tr.return_rows(SHOP, RETURN, AT)
    blob = json.dumps(rows, default=str, ensure_ascii=False)
    for value in LEAKS:
        assert value not in blob, value
    raw = json.loads(rows[0]["raw_json"])
    assert raw["shipping_fee_amount"] == [{"currency": "EUR", "platform_paid_return_shipping_fee": "0",
                                           "seller_paid_return_shipping_fee": "3.99"}]
    for k in ("return_warehouse_address", "return_tracking_number", "return_provider_name", "return_provider_id"):
        assert k not in raw
    assert all("product_image" not in li for li in raw["return_line_items"])


def test_return_row_per_line_and_values():
    rows = tr.return_rows(SHOP, RETURN, AT)
    assert [r["return_line_item_id"] for r in rows] == ["RL1", "RL2"]
    r = rows[0]
    assert (r["shop_id"], r["return_id"], r["order_id"], r["order_line_item_id"]) == ("111", "R1", "O1", "OL1")
    assert r["seller_sku"] == "48304000" and r["return_status"] == "BUYER_SHIPPED_ITEM" and r["lines_count"] == 2
    assert r["refund_total"] == Decimal("50.99") and r["return_refund_total"] == Decimal("50.99")
    assert r["product_seller_discount"] == Decimal("19.00") and r["seller_paid_return_shipping_fee"] == Decimal("3.99")
    assert r["create_time"] == dt.datetime(2026, 10, 25, 18, 3, 30, tzinfo=dt.timezone.utc)
    assert rows[1]["refund_total"] is None and rows[1]["currency"] == "EUR"       # пустая строка — NULL, не ноль


def test_return_without_lines_is_one_row():
    rows = tr.return_rows(SHOP, {"return_id": "R9", "order_id": "O9", "return_status": "X"}, AT)
    assert len(rows) == 1 and rows[0]["return_line_item_id"] == tr.NO_LINE and rows[0]["lines_count"] == 0
    assert rows[0]["refund_total"] is None and rows[0]["seller_paid_return_shipping_fee"] is None


def test_lines_without_id_do_not_collapse():
    rows = tr.return_rows(SHOP, {"return_id": "R8", "return_line_items": [{"seller_sku": "A"}, {"seller_sku": "B"},
                                                                         {"return_line_item_id": "RL3"}]}, AT)
    assert [r["return_line_item_id"] for r in rows] == ["#1", "#2", "RL3"]


def test_cancellation_rows():
    rows = tr.cancellation_rows(SHOP, CANCEL, AT)
    assert len(rows) == 1
    r = rows[0]
    assert (r["cancel_id"], r["cancel_line_item_id"], r["order_id"], r["seller_sku"]) == ("C1", "CL1", "O2", "78060000")
    assert r["should_replenish_stock"] is True and r["cancel_refund_total"] == Decimal("0.00") and r["currency"] == "EUR"
    blob = json.dumps(rows, default=str, ensure_ascii=False)
    assert "https://img/p.png" not in blob and "brand_new_field_value" not in blob
    none = tr.cancellation_rows(SHOP, {"cancel_id": "C2"}, AT)
    assert none[0]["cancel_line_item_id"] == tr.NO_LINE and none[0]["should_replenish_stock"] is None
