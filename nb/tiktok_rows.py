# TikTok Shop → строки сырья `dnipro_m.tiktok.raw_*` (22.10.2026). Чистые функции без сети и без Spark: их импортирует
# загрузчик (`Kabinet - TikTok Shop Loader`) и проверяют тесты CI (`tests/test_tiktok_rows.py`).
#
# Сырьё — «ответ источника как есть» (AGENTS.md, «Слои данных»): типизированные колонки для ключей, статусов, времени
# и денег, плюс `raw_json` — ответ целиком. С одним исключением: ПЕРСОНАЛЬНЫЕ ДАННЫЕ ПОКУПАТЕЛЯ в сырьё не попадают
# (PII, GDPR) — имя, адрес, телефон, email, ник, аватар, налоговый номер, переписка, id пользователя срезаются ДО
# записи и в raw_json, и в колонках. Из адреса остаются только индекс и код региона — для географии продаж.
# Для повторных покупок вместо user_id пишется buyer_hash = sha256(соль + user_id) (решение владельца 22.10.2026);
# соль — секрет tiktok-shop/buyer-salt, её значение задаёт владелец и НЕ МЕНЯЕТ: другая соль — другие хеши, и
# покупатель «до» и «после» смены перестаёт узнаваться.
#
# Деньги у TikTok — строки ("12.50"), время — unix-секунды (UTC). Пустая строка — NULL, не ноль.
# Источник кода — nb/tiktok_rows.py в kabinet-dashboard.
import datetime as dt
import hashlib
import json
from decimal import Decimal, InvalidOperation

ORDER_PII = ("buyer_email", "buyer_nickname", "buyer_avatar", "buyer_message", "cpf", "cpf_name", "user_id",
             "consultation_id")
ADDRESS_KEEP = ("postal_code", "region_code")


def money(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def ts(v):
    if v in (None, "", 0):
        return None
    return dt.datetime.fromtimestamp(int(v), tz=dt.timezone.utc).replace(tzinfo=None)


def strip_order_pii(order):
    """Копия заказа без персональных данных покупателя."""
    o = {k: v for k, v in order.items() if k not in ORDER_PII}
    addr = order.get("recipient_address")
    if isinstance(addr, dict):
        o["recipient_address"] = {k: addr.get(k) for k in ADDRESS_KEEP if addr.get(k) is not None}
    return o


def buyer_hash(salt, user_id):
    """sha256(соль + user_id), hex; без user_id — None. Соль обязательна: без неё хеш подбирается по id."""
    if not salt:
        raise ValueError("нет соли tiktok-shop/buyer-salt — buyer_hash без соли не пишем")
    if user_id in (None, ""):
        return None
    return hashlib.sha256((salt + str(user_id)).encode("utf-8")).hexdigest()


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def order_rows(shop, order, loaded_at, salt):
    """(строка raw_orders, [строки raw_order_lines]) из заказа поиска 202309."""
    o = strip_order_pii(order)
    p = o.get("payment") or {}
    lines = o.get("line_items") or []
    head = {
        "shop_id": shop["id"], "region": shop.get("region"), "order_id": o["id"], "status": o.get("status"),
        "create_time": ts(o.get("create_time")), "update_time": ts(o.get("update_time")),
        "paid_time": ts(o.get("paid_time")), "cancel_time": ts(o.get("cancel_time")),
        "delivery_time": ts(o.get("delivery_time")), "currency": p.get("currency"),
        "total_amount": money(p.get("total_amount")), "sub_total": money(p.get("sub_total")),
        "original_total_product_price": money(p.get("original_total_product_price")),
        "shipping_fee": money(p.get("shipping_fee")), "seller_discount": money(p.get("seller_discount")),
        "platform_discount": money(p.get("platform_discount")), "tax": money(p.get("tax")),
        "fulfillment_type": o.get("fulfillment_type"), "delivery_type": o.get("delivery_type"),
        "payment_method_name": o.get("payment_method_name"), "cancel_reason": o.get("cancel_reason"),
        "cancellation_initiator": o.get("cancellation_initiator"), "is_sample_order": o.get("is_sample_order"),
        "postal_code": (o.get("recipient_address") or {}).get("postal_code"),
        "buyer_hash": buyer_hash(salt, order.get("user_id")),
        "line_items_count": len(lines), "raw_json": _j(o), "loaded_at": loaded_at,
    }
    out = []
    for li in lines:
        out.append({
            "shop_id": shop["id"], "region": shop.get("region"), "order_id": o["id"], "line_item_id": li.get("id"),
            "sku_id": li.get("sku_id"), "seller_sku": li.get("seller_sku"), "product_id": li.get("product_id"),
            "product_name": li.get("product_name"), "sku_name": li.get("sku_name"), "currency": li.get("currency"),
            "original_price": money(li.get("original_price")), "sale_price": money(li.get("sale_price")),
            "seller_discount": money(li.get("seller_discount")), "platform_discount": money(li.get("platform_discount")),
            "item_tax": _j(li.get("item_tax")) if li.get("item_tax") is not None else None,
            "display_status": li.get("display_status"), "cancel_reason": li.get("cancel_reason"),
            "is_gift": li.get("is_gift"), "package_id": li.get("package_id"), "raw_json": _j(li), "loaded_at": loaded_at,
        })
    return head, out


def product_rows(shop, product, loaded_at):
    """(строка raw_products, [строки raw_product_skus]) из товара поиска 202502."""
    skus = product.get("skus") or []
    head = {
        "shop_id": shop["id"], "region": shop.get("region"), "product_id": product["id"], "title": product.get("title"),
        "status": product.get("status"), "create_time": ts(product.get("create_time")),
        "update_time": ts(product.get("update_time")), "listing_quality_tier": product.get("listing_quality_tier"),
        "skus_count": len(skus), "raw_json": _j(product), "loaded_at": loaded_at,
    }
    out = []
    for s in skus:
        price = s.get("price") or {}
        inv = s.get("inventory") or []
        out.append({
            "shop_id": shop["id"], "region": shop.get("region"), "product_id": product["id"], "sku_id": s.get("id"),
            "seller_sku": s.get("seller_sku"), "currency": price.get("currency"),
            "sale_price": money(price.get("sale_price")), "tax_exclusive_price": money(price.get("tax_exclusive_price")),
            "inventory_quantity": sum(int(i.get("quantity") or 0) for i in inv) if inv else None,
            "raw_json": _j(s), "loaded_at": loaded_at,
        })
    return head, out


def statement_row(shop, st, loaded_at):
    return {
        "shop_id": shop["id"], "region": shop.get("region"), "statement_id": st["id"],
        "statement_time": ts(st.get("statement_time")), "payment_status": st.get("payment_status"),
        "payment_id": st.get("payment_id"), "payment_time": ts(st.get("payment_time")), "currency": st.get("currency"),
        "revenue_amount": money(st.get("revenue_amount")), "fee_amount": money(st.get("fee_amount")),
        "adjustment_amount": money(st.get("adjustment_amount")), "shipping_cost_amount": money(st.get("shipping_cost_amount")),
        "net_sales_amount": money(st.get("net_sales_amount")), "settlement_amount": money(st.get("settlement_amount")),
        "raw_json": _j(st), "loaded_at": loaded_at,
    }


def transaction_row(shop, statement_id, currency, tr, loaded_at):
    return {
        "shop_id": shop["id"], "region": shop.get("region"), "statement_id": statement_id, "transaction_id": tr.get("id"),
        "type": tr.get("type"), "order_id": tr.get("order_id"), "order_create_time": ts(tr.get("order_create_time")),
        "adjustment_id": tr.get("adjustment_id"), "currency": currency,
        "revenue_amount": money(tr.get("revenue_amount")), "shipping_cost_amount": money(tr.get("shipping_cost_amount")),
        "fee_tax_amount": money(tr.get("fee_tax_amount")), "adjustment_amount": money(tr.get("adjustment_amount")),
        "settlement_amount": money(tr.get("settlement_amount")), "raw_json": _j(tr), "loaded_at": loaded_at,
    }


def windows(start, end, days):
    """[start, end) кусками по `days` суток — unix-секунды."""
    step = days * 86400
    t = start
    while t < end:
        yield t, min(t + step, end)
        t += step
