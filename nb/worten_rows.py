# Worten (Mirakl) → строки сырья `dnipro_m.worten.raw_*` (28.10.2026). Чистые функции без сети и без Spark: их
# импортирует `Kabinet - Worten Loader` и проверяют тесты CI (tests/test_worten_rows.py).
#
# Офферы. У оффера Worten цена задана по каналам (`all_prices`): верхнее поле `price` и `applicable_pricing` — цена без
# канала, а покупатель Worten Online PT видит цену канала WRT_PT_ONLINE (проба 28.10.2026: 41324000 — 39,00 без канала,
# 31,99 в канале по скидке 19.10–16.11). Цена для покупателя — цена канала, со скидкой, только если она действует на
# момент снимка; канала нет — цена без канала по тому же правилу.
#
# Заказы. raw_json — БЕЛЫЙ СПИСОК полей (ORDER_KEEP, LINE_KEEP): имя, фамилия, customer_id, оба адреса (улица, город,
# телефон, компания), email уведомлений, трек-номер и ссылка на него, картинки товара в сырьё не попадают. Из адреса
# доставки — только индекс и страна (география продаж), как у TikTok.
#
# Деньги у Mirakl — числа, время — ISO-строки UTC («2026-10-21T19:17:24Z»). Пусто — NULL, не ноль.
# Источник кода — nb/worten_rows.py в kabinet-dashboard.
import datetime as dt
import json
from decimal import Decimal, InvalidOperation

CHANNEL = "WRT_PT_ONLINE"
OFFER_KEEP = frozenset((
    "offer_id", "shop_sku", "product_sku", "product_title", "product_brand", "category_code", "category_label",
    "active", "state_code", "quantity", "price", "all_prices", "channels", "currency_iso_code", "leadtime_to_ship",
    "logistic_class", "inactivity_reasons", "min_shipping_price", "min_shipping_zone", "msrp",
))
ORDER_KEEP = frozenset((
    "order_id", "commercial_id", "order_state", "order_state_reason_code", "order_state_reason_label", "channel",
    "created_date", "last_updated_date", "acceptance_decision_date", "customer_debited_date", "delivery_date",
    "shipping_deadline", "currency_iso_code", "price", "shipping_price", "total_price", "total_commission",
    "order_tax_mode", "order_taxes", "payment_type", "payment_workflow", "shipping_type_code", "shipping_type_label",
    "shipping_zone_code", "shipping_carrier_code", "fully_refunded", "has_incident", "has_invoice", "leadtime_to_ship",
    "order_lines", "order_refunds", "promotions",
))
LINE_KEEP = frozenset((
    "order_line_id", "order_line_index", "order_line_state", "order_line_state_reason_code", "offer_id", "offer_sku",
    "product_shop_sku", "product_sku", "product_title", "category_code", "quantity", "price_unit", "price",
    "shipping_price", "total_price", "commission_fee", "commission_vat", "commission_rate_vat", "taxes",
    "shipping_taxes", "created_date", "debited_date", "shipped_date", "received_date", "refunds", "cancelations",
    "promotions",
))
ADDRESS_KEEP = ("zip_code", "country", "country_iso_code")


def money(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def ts(v):
    """ISO-строка Mirakl → datetime UTC с поясом; пусто или не разобралось — None."""
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        d = dt.datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _keep(d, keys):
    return {k: v for k, v in d.items() if k in keys} if isinstance(d, dict) else {}


def channel_pricing(offer, channel=CHANNEL):
    """Запись all_prices для канала; нет — запись без канала (channel_code пуст); нет и её — None."""
    prices = [p for p in (offer.get("all_prices") or []) if isinstance(p, dict)]
    for p in prices:
        if p.get("channel_code") == channel:
            return p
    return next((p for p in prices if not p.get("channel_code")), None)


def buyer_price(pricing, offer_price, now):
    """(цена для покупателя на момент now, действует ли скидка, обычная цена). Скидка — unit_discount_price, если
    начало не в будущем и конец не в прошлом, а даты, если есть, разобрались; иначе — unit_origin_price (или price)."""
    if not pricing:
        p = money(offer_price)
        return p, False, p
    origin = money(pricing.get("unit_origin_price")) or money(pricing.get("price")) or money(offer_price)
    disc = money(pricing.get("unit_discount_price"))
    a_raw, b_raw = pricing.get("discount_start_date"), pricing.get("discount_end_date")
    a, b = ts(a_raw), ts(b_raw)
    unparsed = (a_raw and a is None) or (b_raw and b is None)
    if disc and disc > 0 and not unparsed and (a is None or a <= now) and (b is None or now < b):
        return disc, True, origin
    return origin, False, origin


def offer_row(shop_id, offer, loaded_at, now=None):
    now = now or loaded_at
    pr = channel_pricing(offer)
    price, on, origin = buyer_price(pr, offer.get("price"), now)
    return {
        "shop_id": str(shop_id), "offer_id": str(offer.get("offer_id")), "shop_sku": offer.get("shop_sku"),
        "product_sku": offer.get("product_sku"), "product_title": offer.get("product_title"),
        "category_code": offer.get("category_code"), "active": offer.get("active"),
        "state_code": offer.get("state_code"), "quantity": offer.get("quantity"),
        "channel_code": (pr or {}).get("channel_code"), "price": price, "origin_price": origin,
        "discount_price": money((pr or {}).get("unit_discount_price")),
        "discount_start": ts((pr or {}).get("discount_start_date")),
        "discount_end": ts((pr or {}).get("discount_end_date")), "promo_active": on,
        "base_price": money(offer.get("price")), "currency": offer.get("currency_iso_code"),
        "raw_json": _j(_keep(offer, OFFER_KEEP)), "loaded_at": loaded_at,
    }


def strip_order(order):
    o = _keep(order, ORDER_KEEP)
    addr = ((order.get("customer") or {}).get("shipping_address") if isinstance(order.get("customer"), dict) else None)
    o["shipping_address"] = ({k: addr.get(k) for k in ADDRESS_KEEP if addr.get(k) not in (None, "")}
                             if isinstance(addr, dict) else None)
    o["order_lines"] = [_keep(li, LINE_KEEP) for li in (order.get("order_lines") or []) if isinstance(li, dict)]
    return o


def _tax_sum(taxes):
    vals = [money(t.get("amount")) for t in (taxes or []) if isinstance(t, dict)]
    vals = [v for v in vals if v is not None]
    return sum(vals, Decimal("0.00")) if vals else None


def order_rows(shop_id, order, loaded_at):
    """(строка raw_orders, [строки raw_order_lines]) из заказа OR11."""
    o = strip_order(order)
    addr = o.get("shipping_address") or {}
    lines = o["order_lines"]
    head = {
        "shop_id": str(shop_id), "order_id": o.get("order_id"), "commercial_id": o.get("commercial_id"),
        "order_state": o.get("order_state"), "channel_code": (o.get("channel") or {}).get("code"),
        "created_at": ts(o.get("created_date")), "updated_at": ts(o.get("last_updated_date")),
        "currency": o.get("currency_iso_code"), "price": money(o.get("price")),
        "shipping_price": money(o.get("shipping_price")), "total_price": money(o.get("total_price")),
        "total_commission": money(o.get("total_commission")), "order_tax_mode": o.get("order_tax_mode"),
        "fully_refunded": o.get("fully_refunded"), "has_incident": o.get("has_incident"),
        "postal_code": addr.get("zip_code"), "country": addr.get("country"),
        "lines_count": len(lines), "raw_json": _j(o), "loaded_at": loaded_at,
    }
    out = []
    for li in lines:
        out.append({
            "shop_id": str(shop_id), "order_id": o.get("order_id"), "order_line_id": li.get("order_line_id"),
            "order_line_state": li.get("order_line_state"), "offer_id": str(li.get("offer_id")) if li.get("offer_id") is not None else None,
            "shop_sku": li.get("offer_sku") or li.get("product_shop_sku"), "product_title": li.get("product_title"),
            "quantity": li.get("quantity"), "price_unit": money(li.get("price_unit")), "price": money(li.get("price")),
            "shipping_price": money(li.get("shipping_price")), "total_price": money(li.get("total_price")),
            "commission_fee": money(li.get("commission_fee")), "commission_vat": money(li.get("commission_vat")),
            "tax_amount": _tax_sum(li.get("taxes")), "shipped_at": ts(li.get("shipped_date")),
            "received_at": ts(li.get("received_date")), "raw_json": _j(li), "loaded_at": loaded_at,
        })
    return head, out


def windows(start, end, days):
    """[start, end) кусками по `days` суток — datetime."""
    step = dt.timedelta(days=days)
    t = start
    while t < end:
        yield t, min(t + step, end)
        t += step


def iso(d):
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
