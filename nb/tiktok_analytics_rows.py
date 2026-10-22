# TikTok Shop, аналитика (группа 1, 22.10.2026) → строки сырья `dnipro_m.tiktok.raw_analytics_*`. Чистые функции без
# сети и без Spark: их импортирует `Kabinet - TikTok Shop Analytics Loader` и проверяют тесты CI.
#
# Аналитика TikTok — агрегаты по дням (дата — в часовом поясе магазина), деньги — {"amount": "12.50", "currency": "EUR"}.
# Типизированные колонки — для ключей и главных метрик, остальное — в raw_json.
#
# Креаторы (видео, эфиры) — деловые партнёры, не покупатели (решение владельца 22.10.2026, вариант а): храним
# `creator_id` и публичный ник `user_name` (плюс тип автора и страну). Отображаемое имя `nick_name` (бывает с настоящим
# именем) и `open_id` (тот же id ещё раз) в сырьё не пишутся — ни в колонки, ни в raw_json.
# Источник кода — nb/tiktok_analytics_rows.py в kabinet-dashboard.
import datetime as dt
import json
from decimal import Decimal, InvalidOperation

CREATOR_KEEP = ("creator_id", "user_name", "author_type", "creator_country")


def num(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def money(m):
    """{"amount", "currency"} → (Decimal(2), валюта); пусто — (None, None)."""
    if not isinstance(m, dict):
        return None, None
    a = num(m.get("amount"))
    return (a.quantize(Decimal("0.01")) if a is not None else None), m.get("currency")


def amt(m):
    return money(m)[0]


def integer(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def day(s):
    return dt.date.fromisoformat(str(s)[:10]) if s else None


def strip_creator(creator):
    """Креатор без отображаемого имени и open_id; creator_id берётся из open_id, если своего нет (у эфиров)."""
    if not isinstance(creator, dict):
        return None
    out = {k: creator.get(k) for k in CREATOR_KEEP if creator.get(k) is not None}
    if "creator_id" not in out and creator.get("open_id"):
        out["creator_id"] = creator["open_id"]
    return out


def _clean(obj):
    """Копия ответа с креатором без лишнего (на любом уровне вложенности)."""
    if isinstance(obj, dict):
        return {k: (strip_creator(v) if k == "creator" else _clean(v)) for k, v in obj.items() if k not in ("nick_name", "open_id")}
    if isinstance(obj, list):
        return [_clean(x) for x in obj]
    return obj


def _j(x):
    return json.dumps(_clean(x), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _base(shop, loaded_at):
    return {"shop_id": shop["id"], "region": shop.get("region"), "loaded_at": loaded_at}


def shop_day_row(shop, interval, loaded_at):
    s, t = interval.get("sales") or {}, interval.get("traffic") or {}
    return {**_base(shop, loaded_at), "date": day(interval.get("start_date")), "currency": money(s.get("gmv"))[1],
            "gmv": amt(s.get("gmv")), "gmv_with_tax": amt(s.get("gmv_with_tax")),
            "gmv_with_tiktok_co_funding": amt(s.get("gmv_with_tiktok_co_funding")), "tax": amt(s.get("tax")),
            "shipping_fees": amt(s.get("shipping_fees")), "refunds": amt(s.get("refunds")),
            "orders_count": integer(s.get("orders_count")), "sku_orders_count": integer(s.get("sku_orders_count")),
            "items_sold": integer(s.get("items_sold")), "customers_count": integer(s.get("customers_count")),
            "cancellations_and_returns": integer(s.get("cancellations_and_returns")),
            "video_gmv": amt(s.get("video_gmv")), "live_gmv": amt(s.get("live_gmv")),
            "creator_video_gmv": amt(s.get("creator_video_gmv")), "seller_video_gmv": amt(s.get("seller_video_gmv")),
            "product_card_attributed_gmv": amt(s.get("product_card_attributed_gmv")),
            "avg_page_views": num(t.get("avg_page_views")), "avg_visitors": num(t.get("avg_visitors")),
            "product_impressions": integer(t.get("product_impressions")), "product_clicks": integer(t.get("product_clicks")),
            "raw_json": _j(interval)}


def product_day_row(shop, date, p, loaded_at):
    tp = p.get("total_performance") or {}
    return {**_base(shop, loaded_at), "date": date, "product_id": str(p.get("id")), "currency": money(tp.get("gmv"))[1],
            "gmv": amt(tp.get("gmv")), "gmv_incl_tax": amt(tp.get("gmv_incl_tax")), "orders": integer(tp.get("orders")),
            "sku_orders": integer(tp.get("sku_orders")), "items_sold": integer(tp.get("items_sold")),
            "product_impressions": integer(tp.get("product_impressions")), "product_clicks": integer(tp.get("product_clicks")),
            "add_cart_count": integer(tp.get("add_cart_count")), "refunds": amt(tp.get("refunds")),
            "refunded_items": integer(tp.get("refunded_items")),
            "affiliate_gmv": amt((p.get("affiliate_total_performance") or {}).get("attributed_gmv")),
            "seller_card_gmv": amt((p.get("seller_product_card_performance") or {}).get("attributed_gmv")),
            "shop_tab_gmv": amt((p.get("shop_tab_performance") or {}).get("shop_tab_gmv")),
            "raw_json": _j(p)}


def sku_day_row(shop, date, s, loaded_at):
    return {**_base(shop, loaded_at), "date": date, "sku_id": str(s.get("id")), "product_id": str(s.get("product_id")),
            "currency": money(s.get("gmv"))[1], "gmv": amt(s.get("gmv")), "sku_orders": integer(s.get("sku_orders")),
            "units_sold": integer(s.get("units_sold")), "raw_json": _j(s)}


def video_day_row(shop, date, v, loaded_at):
    cr = strip_creator(v.get("creator")) or {}
    return {**_base(shop, loaded_at), "date": date, "video_id": str(v.get("id")), "creator_id": cr.get("creator_id"),
            "creator_user_name": cr.get("user_name"), "author_type": cr.get("author_type"), "title": v.get("title"),
            "video_post_time_local": v.get("video_post_time"), "duration_s": integer(v.get("duration")),
            "currency": money(v.get("gmv"))[1], "gmv": amt(v.get("gmv")), "attributed_gmv": amt(v.get("attributed_gmv")),
            "indirect_gmv": amt(v.get("indirect_gmv")), "items_sold": integer(v.get("items_sold")),
            "sku_orders": integer(v.get("sku_orders")), "views": integer(v.get("views")), "likes": integer(v.get("likes")),
            "comments": integer(v.get("comments")), "shares": integer(v.get("shares")),
            "new_followers": integer(v.get("new_followers")), "product_impressions": integer(v.get("product_impressions")),
            "product_clicks": integer(v.get("product_clicks")), "raw_json": _j(v)}


def video_product_day_row(shop, date, video_id, p, loaded_at):
    return {**_base(shop, loaded_at), "date": date, "video_id": str(video_id), "product_id": str(p.get("id")),
            "currency": money(p.get("gmv"))[1], "gmv": amt(p.get("gmv")), "units_sold": integer(p.get("units_sold")),
            "customers": integer(p.get("customers")), "product_impressions": integer(p.get("product_impressions")),
            "product_clicks": integer(p.get("product_clicks")), "raw_json": _j(p)}


def live_row(shop, account_type, s, loaded_at):
    cr = strip_creator(s.get("creator")) or {}
    sp, tr, ip = s.get("sales_performance") or {}, s.get("traffic") or {}, s.get("interaction_performance") or {}
    return {**_base(shop, loaded_at), "live_id": str(s.get("id")), "account_type": account_type,
            "creator_id": cr.get("creator_id"), "creator_user_name": cr.get("user_name"), "author_type": cr.get("author_type"),
            "title": s.get("title"), "start_time_local": s.get("start_time"), "end_time_local": s.get("end_time"),
            "currency": money(sp.get("live_gmv"))[1], "live_gmv": amt(sp.get("live_gmv")),
            "live_attributed_gmv": amt(sp.get("live_attributed_gmv")),
            "live_attributed_items_sold": integer(sp.get("live_attributed_items_sold")),
            "products_sold": integer(sp.get("products_sold")), "viewers": integer(tr.get("viewers")),
            "views": integer(tr.get("views")), "avg_viewing_duration_s": integer(tr.get("avg_viewing_duration")),
            "product_impressions": integer(tr.get("product_impressions")), "product_clicks": integer(tr.get("product_clicks")),
            "likes": integer(ip.get("likes")), "comments": integer(ip.get("comments")), "shares": integer(ip.get("shares")),
            "raw_json": _j(s)}


def live_product_row(shop, live_id, p, loaded_at):
    gmv = p.get("gmv") or p.get("live_gmv") or p.get("attributed_gmv")
    return {**_base(shop, loaded_at), "live_id": str(live_id), "product_id": str(p.get("id") or p.get("product_id")),
            "currency": money(gmv)[1], "gmv": amt(gmv), "units_sold": integer(p.get("units_sold") or p.get("items_sold")),
            "raw_json": _j(p)}


def days(start, end):
    """[start, end) по дням — date."""
    d = start
    while d < end:
        yield d
        d += dt.timedelta(days=1)
