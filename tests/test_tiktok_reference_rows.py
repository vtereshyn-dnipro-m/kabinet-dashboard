"""Строки справочников TikTok Shop (`nb/tiktok_reference_rows.py`, шаг 1 из групп 2–5): логистика и категории.

Главное — адрес и контакт склада не попадают ни в колонки, ни в raw_json; опечатка TikTok «is_requried» читается;
лист цепочки категорий выбирается верно. Формы ответов — по пробе 26.10.2026 на живом API (только чтение).
"""
import datetime as dt
import json
import os
import sys

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import tiktok_reference_rows as rr  # noqa: E402

SHOP = {"id": "7494566066277090388", "region": "ES"}
AT = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)

WAREHOUSE = {
    "id": "7628307551415093014", "name": "Almacén", "type": "SALES_WAREHOUSE", "sub_type": "DOMESTIC_WAREHOUSE",
    "effect_status": "ENABLED", "is_default": True, "entity_id": "7628307551415027478",
    "address": {"address_line1": "Calle Falsa 1", "address_line2": "Nave 2", "city": "Madrid", "contact_person": "Ana",
                "distict": "Arroyomolinos", "full_address": "Calle Falsa 1, Madrid", "phone_number": "+34600000000",
                "postal_code": "28939", "region": "The Kingdom of Spain", "region_code": "ES",
                "state": "Community of Madrid", "town": ""},
}


def test_warehouse_without_address_and_contact():
    r = rr.warehouse_row(SHOP, WAREHOUSE, AT)
    assert r["warehouse_id"] == "7628307551415093014" and r["is_default"] is True
    assert r["region_code"] == "ES" and r["state"] == "Community of Madrid"
    raw = r["raw_json"]
    for leak in ("Calle Falsa", "Nave 2", "+34600000000", "Ana", "28939", "Arroyomolinos", "full_address", "phone_number"):
        assert leak not in raw, leak
    assert json.loads(raw)["address"] == {"region": "The Kingdom of Spain", "region_code": "ES", "state": "Community of Madrid"}


def test_warehouse_without_address_at_all():
    r = rr.warehouse_row(SHOP, {"id": "1", "type": "RETURN_WAREHOUSE"}, AT)
    assert r["region_code"] is None and "address" not in json.loads(r["raw_json"])


def test_delivery_option_and_provider():
    d = rr.delivery_option_row(SHOP, "w1", {"id": "7357984593359669025", "name": "Shipped by seller",
                                            "type": "SEND_BY_SELLER", "platform": ["TIKTOK_SHOP", "TOKOPEDIA"]}, AT)
    assert d["delivery_option_id"] == "7357984593359669025" and d["platforms"] == "TIKTOK_SHOP,TOKOPEDIA"
    p = rr.shipping_provider_row(SHOP, "7357984593359669025", {"id": "7038794894311163650", "name": "CTT Express"}, AT)
    assert (p["provider_id"], p["name"]) == ("7038794894311163650", "CTT Express")


def test_category_row():
    c = rr.category_row(SHOP, "es-ES", {"id": "600001", "is_leaf": False, "local_name": "Productos para el hogar",
                                        "parent_id": "0", "permission_statuses": ["AVAILABLE", "INVITE_ONLY"]}, AT)
    assert c["category_id"] == "600001" and c["is_leaf"] is False and c["permission_statuses"] == "AVAILABLE,INVITE_ONLY"


def test_leaf_of_chain():
    chain = [{"id": "604579", "is_leaf": False, "local_name": "Herramientas y hardware", "parent_id": "0"},
             {"id": "979848", "is_leaf": True, "local_name": "Destornilladores", "parent_id": "604579"}]
    assert rr.leaf_of(chain) == "979848"
    assert rr.leaf_of([{"id": "1"}, {"id": "2"}]) == "2"            # без is_leaf — последний
    assert rr.leaf_of([]) is None and rr.leaf_of(None) is None
    r = rr.product_category_row(SHOP, "1729826745796302932", chain, AT)
    assert r["category_id"] == "979848" and r["category_path"] == "Herramientas y hardware > Destornilladores"


def test_attribute_reads_tiktok_typo():
    a = rr.attribute_row(SHOP, "979848", {"id": "104359", "name": "Material", "type": "PRODUCT_PROPERTY",
                                          "is_requried": True, "is_customizable": True, "is_multiple_selection": False,
                                          "values": [{"id": "1"}, {"id": "2"}]}, AT)
    assert a["is_required"] is True and a["values_count"] == 2
    b = rr.attribute_row(SHOP, "979848", {"id": "1", "is_required": False}, AT)
    assert b["is_required"] is False and b["values_count"] == 0


def test_rules_row():
    r = rr.rules_row(SHOP, "979848", {"cod": {"is_supported": False}, "epr": {"is_required": False},
                                      "manufacturer": {"is_required": True}, "package_dimension": {"is_required": True},
                                      "responsible_person": {"is_required": True},
                                      "size_chart": {"is_required": False, "is_supported": False},
                                      "product_certifications": [{"id": "1", "is_required": True}, {"id": "2", "is_required": False}]}, AT)
    assert (r["cod_supported"], r["epr_required"], r["manufacturer_required"]) == (False, False, True)
    assert (r["responsible_person_required"], r["package_dimension_required"], r["size_chart_required"]) == (True, True, False)
    assert (r["certifications_count"], r["required_certifications_count"]) == (2, 1)
    e = rr.rules_row(SHOP, "1", None, AT)
    assert e["cod_supported"] is None and e["certifications_count"] == 0


def test_has_keys():
    assert rr.has_keys({"a": 1, "b": "x"}, ("a", "b")) and not rr.has_keys({"a": None}, ("a",))
