"""Строки аналитики TikTok Shop (`nb/tiktok_analytics_rows.py`): деньги, даты, ключи; у креаторов — только id и
публичный ник, отображаемое имя и open_id не доходят до таблиц."""
import datetime as dt
import json
import os
import sys
from decimal import Decimal

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import tiktok_analytics_rows as ar  # noqa: E402
import tiktok_client as tt  # noqa: E402

SHOP = {"id": "111", "region": "ES"}
AT = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc)
CREATOR = {"author_type": "AFFILIATE_ACCOUNTS", "creator_country": "es", "creator_id": "CID", "nick_name": "Juan Pérez",
           "open_id": "CID", "user_name": "juanp"}


def test_shop_day():
    iv = {"start_date": "2026-10-21", "end_date": "2026-10-22",
          "sales": {"gmv": {"amount": "138.29", "currency": "EUR"}, "orders_count": 4, "items_sold": 4},
          "traffic": {"avg_page_views": "12.5", "product_impressions": 1000}}
    r = ar.shop_day_row(SHOP, iv, AT)
    assert r["date"] == dt.date(2026, 10, 21) and r["gmv"] == Decimal("138.29") and r["currency"] == "EUR"
    assert r["orders_count"] == 4 and r["avg_page_views"] == Decimal("12.5") and r["refunds"] is None


def test_video_creator_without_display_name():
    v = {"id": "V1", "creator": CREATOR, "title": "t", "gmv": {"amount": "559.00", "currency": "EUR"}, "items_sold": 14,
         "products": [{"id": "P1", "name": "Taladro"}], "username": "juanp"}
    r = ar.video_day_row(SHOP, dt.date(2026, 10, 1), v, AT)
    assert (r["creator_id"], r["creator_user_name"]) == ("CID", "juanp")
    blob = json.dumps(r, default=str, ensure_ascii=False)
    assert "Juan Pérez" not in blob and "nick_name" not in blob and "open_id" not in blob
    assert r["gmv"] == Decimal("559.00") and r["video_id"] == "V1"


def test_live_creator_without_open_id():
    s = {"id": 77, "creator": {k: v for k, v in CREATOR.items() if k != "creator_id"},
         "sales_performance": {"live_gmv": {"amount": "0.00", "currency": "EUR"}, "products_sold": 0},
         "traffic": {"viewers": 1408}, "interaction_performance": {"likes": 5}}
    r = ar.live_row(SHOP, "AFFILIATE_ACCOUNTS", s, AT)
    assert r["creator_id"] is None and r["creator_user_name"] == "juanp" and r["live_id"] == "77" and r["viewers"] == 1408
    assert "Juan Pérez" not in r["raw_json"] and "CID" not in r["raw_json"] and "open_id" not in r["raw_json"]


def test_live_product_sales_block():
    p = {"id": "P1", "name": "Taladro", "sales": {"direct_gmv": {"amount": "40.63", "currency": "EUR"}, "items_sold": 0}}
    r = ar.live_product_row(SHOP, "L1", p, AT)
    assert r["gmv"] == Decimal("40.63") and r["currency"] == "EUR" and r["units_sold"] == 0


def test_missing_id_is_none_not_text():
    r = ar.sku_day_row(SHOP, dt.date(2026, 10, 1), {"gmv": None}, AT)
    assert r["sku_id"] is None and not ar.has_keys(r, ("shop_id", "date", "sku_id"))


def test_sku_ids_as_text():
    r = ar.sku_day_row(SHOP, dt.date(2026, 10, 1), {"id": 1729928381816281172, "product_id": 1729928379622332500,
                                                    "gmv": {"amount": "649.62", "currency": "EUR"}, "units_sold": 14}, AT)
    assert r["sku_id"] == "1729928381816281172" and r["product_id"] == "1729928379622332500"


def test_days():
    assert list(ar.days(dt.date(2026, 10, 1), dt.date(2026, 10, 3))) == [dt.date(2026, 10, 1), dt.date(2026, 10, 2)]


def test_analytics_paths_allowed_get_only():
    for p in ("/analytics/202609/shop/performance", "/analytics/202605/shop_products/performance",
              "/analytics/202509/shop_skus/performance", "/analytics/202605/shop_videos/performance",
              "/analytics/202509/shop_videos/7682142355729763606/products/performance",
              "/analytics/202609/shop_lives/performance", "/analytics/202512/shop/7695147908141959958/products_performance"):
        tt.check_allowed("GET", p)
        try:
            tt.check_allowed("POST", p)
            raise AssertionError(f"POST {p} пропущен")
        except PermissionError:
            pass
