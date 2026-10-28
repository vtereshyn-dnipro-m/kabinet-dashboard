"""Строки Worten (`nb/worten_rows.py`): цена для покупателя — цена канала WRT_PT_ONLINE по сроку скидки; данные
покупателя не доходят до сырья. Формы — по пробе 28.10.2026 на живом API (только чтение), личные значения выдуманы."""
import datetime as dt
import json
import os
import sys
from decimal import Decimal

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import worten_rows as wr  # noqa: E402

AT = dt.datetime(2026, 10, 28, 14, 0, tzinfo=dt.timezone.utc)
OFFER = {"offer_id": 441114647, "shop_sku": "41324000", "product_sku": "ffffffff-0000-4000-a000-000077e010d1",
         "price": 39.0, "quantity": 10, "active": True, "currency_iso_code": "EUR", "product_description": "длинное описание",
         "all_prices": [
             {"channel_code": None, "price": 39.0, "unit_origin_price": 39.0, "unit_discount_price": None},
             {"channel_code": "WRT_PT_ONLINE", "price": 31.99, "unit_origin_price": 39.0, "unit_discount_price": 31.99,
              "discount_start_date": "2026-10-19T23:00:00Z", "discount_end_date": "2026-11-16T23:59:59Z"}]}
PII = ("Joana", "Silva", "Rua das Flores 12", "Coimbra", "+351911222333", "joana@example.pt", "CUST-77", "TRK-PT-9",
       "https://track/9", "https://img/p.jpg", "Empresa Lda")
ORDER = {
    "order_id": "83958861-A", "commercial_id": "83958861", "order_state": "RECEIVED",
    "channel": {"code": "WRT_PT_ONLINE", "label": "Worten Online PT"},
    "created_date": "2026-10-21T19:17:24Z", "last_updated_date": "2026-10-23T19:53:32Z", "currency_iso_code": "EUR",
    "price": 65.99, "shipping_price": 0.0, "total_price": 65.99, "total_commission": 9.9, "order_tax_mode": "TAX_INCLUDED",
    "customer_notification_email": PII[5], "shipping_tracking": PII[7], "shipping_tracking_url": PII[8],
    "customer": {"customer_id": PII[6], "firstname": PII[0], "lastname": PII[1],
                 "shipping_address": {"firstname": PII[0], "lastname": PII[1], "street_1": PII[2], "city": PII[3],
                                      "phone": PII[4], "company": PII[10], "zip_code": "3100-095", "country": "PT"},
                 "billing_address": {"street_1": PII[2], "phone": PII[4]}},
    "order_lines": [{"order_line_id": "83958861-A-1", "order_line_state": "RECEIVED", "offer_id": 1, "offer_sku": "80625040",
                     "product_title": "Máquina De Solda", "quantity": 1, "price_unit": 65.99, "price": 65.99,
                     "total_price": 65.99, "commission_fee": 9.9, "commission_vat": 0.0,
                     "taxes": [{"amount": 12.34, "code": "orderline-items-tax"}],
                     "product_medias": [{"media_url": PII[9]}]}],
}


def test_offer_buyer_price_is_channel_promo():
    r = wr.offer_row(18499, OFFER, AT)
    assert (r["price"], r["promo_active"], r["origin_price"], r["base_price"]) == (
        Decimal("31.99"), True, Decimal("39.00"), Decimal("39.00"))
    assert r["channel_code"] == "WRT_PT_ONLINE" and r["shop_sku"] == "41324000"
    assert "product_description" not in json.loads(r["raw_json"])


def test_offer_promo_expired_or_future():
    after = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc)
    assert wr.offer_row(18499, OFFER, after)["price"] == Decimal("39.00")
    before = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    assert wr.offer_row(18499, OFFER, before)["promo_active"] is False


def test_offer_without_channel_and_unparsed_date():
    o = {**OFFER, "all_prices": [{"channel_code": None, "unit_origin_price": 45.99, "unit_discount_price": 41.99,
                                  "discount_start_date": "не дата"}]}
    r = wr.offer_row(18499, o, AT)
    assert r["price"] == Decimal("45.99") and r["promo_active"] is False and r["channel_code"] is None
    assert wr.offer_row(18499, {"offer_id": 1, "price": 10}, AT)["price"] == Decimal("10.00")


def test_order_has_no_buyer_data():
    head, lines = wr.order_rows(18499, ORDER, AT)
    blob = json.dumps([head, lines], default=str, ensure_ascii=False)
    for v in PII:
        assert v not in blob, v
    assert json.loads(head["raw_json"])["shipping_address"] == {"zip_code": "3100-095", "country": "PT"}
    assert (head["postal_code"], head["country"], head["total_price"], head["total_commission"]) == (
        "3100-095", "PT", Decimal("65.99"), Decimal("9.90"))
    assert head["created_at"] == dt.datetime(2026, 10, 21, 19, 17, 24, tzinfo=dt.timezone.utc)
    (l,) = lines
    assert (l["shop_sku"], l["quantity"], l["tax_amount"], l["commission_fee"]) == ("80625040", 1, Decimal("12.34"), Decimal("9.90"))


def test_windows_and_iso():
    a = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    w = list(wr.windows(a, a + dt.timedelta(days=10), 7))
    assert len(w) == 2 and w[-1][1] == a + dt.timedelta(days=10)
    assert wr.iso(a) == "2026-10-01T00:00:00Z"
