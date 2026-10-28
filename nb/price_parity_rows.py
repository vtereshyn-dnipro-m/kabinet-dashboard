# Паритет цен (28.10.2026, T-37, вариант 3 — решение владельца): чистые функции без сети и без Spark. Их импортирует
# ноутбук `Kabinet - Price Parity` (nb/price_parity.py) и проверяют тесты CI (tests/test_price_parity_rows.py).
#
# Что решает модуль:
# - цена Leroy Merlin и Carrefour (Mirakl) — по сроку скидки на момент сборки: скидка берётся, только если акция идёт
#   сейчас; закончившаяся скидка не берётся (27.10.2026 Carrefour показал скидку, кончившуюся 25.10, — 48,99 € при цене
#   129 €). Прежняя формула coalesce(discount_price, price) срок не проверяла;
# - пауза между акциями: сейчас скидки нет, но недавно была (срок кончился недавно или скидка была в истории снимков).
#   Цена в паузе показывается как есть (это цена для покупателя), но строка не считается выбросом из-за неё — пауза
#   перечисляется в promo_pause_channels (27.10.2026: акция LM кончилась в полночь, новая появилась только 28.10 утром);
# - разброс и выбросы — внутри страны, как прежде (Amazon ES против LM, MM, CF в Испании; Amazon FR против MM FR).
# Источник кода — nb/price_parity_rows.py в kabinet-dashboard.
import datetime as dt
import re

PCOLS = ["amz_es", "amz_fr", "amz_de", "amz_it", "amz_gb", "mm_es", "mm_fr", "lm_es", "cf_es"]
EUR = [c for c in PCOLS if c != "amz_gb"]
COUNTRY = {"ES": ["amz_es", "lm_es", "mm_es", "cf_es"], "FR": ["amz_fr", "mm_fr"]}
OUTLIER_PCT = 20          # по умолчанию для тестов; в джобе — reorder_params.parity_outlier_pct (как в прежней ячейке, 20)


def norm_sku(s):
    """Ключ варианта: снимаем только технические хвосты (amzn.gr., -FBA/-FBM, замыкающие _ и -). Без 5+ цифр — не SKU."""
    s = re.sub(r"^amzn\.gr\.", "", str(s).strip()).rstrip("_-")
    s = re.sub(r"-(FBA|FBM)(-[A-Za-z0-9_-]*)?$", "", s).rstrip("_-")
    return s if re.search(r"[0-9]{5,}", s) else None


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _ts(v):
    """datetime с поясом или None; наивное время считаем UTC."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    return None


def _ts_any(v):
    """datetime или строка ISO (SP-API отдаёт даты скидки строкой) → datetime с поясом; иначе None."""
    if isinstance(v, str) and v.strip():
        try:
            return _ts(dt.datetime.fromisoformat(v.strip().replace("Z", "+00:00")))
        except ValueError:
            return None
    return _ts(v)


def amazon_price(status, our_price, discounted_price, discount_start, discount_end, now):
    """Цена Amazon для паритета — наша цена из SP-API Listings Items (снимок дня, все рынки разом), по правилам Plan
    Matrix (решение владельца 14.10.2026): только листинг в продаже (BUYABLE), меньшая из our_price и скидки, если
    скидка действует сейчас. Не в продаже — None: цены для покупателя нет (28.10.2026: 81123011 в ES — DISCOVERABLE)."""
    if "BUYABLE" not in str(status or "").upper().split(","):
        return None
    p = _f(our_price)
    if p is None or p <= 0:
        return None
    if promo_active(discounted_price, _ts_any(discount_start), _ts_any(discount_end), now):
        p = min(p, _f(discounted_price))
    return p


def promo_active(discount_price, discount_start, discount_end, now):
    """Скидка действует сейчас: цена скидки есть, начало не в будущем, конец не в прошлом (пустые даты — без ограничения)."""
    if _f(discount_price) is None or _f(discount_price) <= 0:
        return False
    a, b = _ts(discount_start), _ts(discount_end)
    return (a is None or a <= now) and (b is None or now < b)


def mirakl_price(price, origin_price, discount_price, discount_start, discount_end, now):
    """(цена для покупателя на момент now, действует ли скидка). Без действующей скидки — обычная цена: origin_price,
    а если её нет — price (у Mirakl price без акции равен обычной цене)."""
    if promo_active(discount_price, discount_start, discount_end, now):
        return _f(discount_price), True
    regular = _f(origin_price) if _f(origin_price) and _f(origin_price) > 0 else _f(price)
    return regular, False


def in_pause(active_now, discount_end, now, recent_promo, pause_days):
    """Пауза между акциями: скидки сейчас нет, но она была недавно — срок скидки кончился меньше pause_days назад
    (Carrefour держит поля скидки после конца) или скидка была в истории снимков за pause_days (Leroy Merlin в паузе
    поля скидки очищает, поэтому нужен признак recent_promo из истории)."""
    if active_now:
        return False
    b = _ts(discount_end)
    ended_recently = b is not None and b <= now and (now - b) <= dt.timedelta(days=pause_days)
    return bool(ended_recently or recent_promo)


def pick_offers(rows, run_window_s):
    """Офферы канала для паритета: только из последней загрузки (loaded_at не раньше максимума минус run_window_s) и по
    одному на norm_sku — самый свежий. Загрузчики офферов делают upsert и не удаляют пропавшие из API офферы: такая
    строка остаётся «активной» со старой ценой и старой скидкой (28.10.2026: LM «41500000» от 29.09 рядом с живым
    «41500000_»), и без отбора она давала ложную паузу и случайную цену по порядку строк. rows — кортежи
    (sku, price, origin_price, discount_price, discount_start, discount_end, loaded_at)."""
    rows = [r for r in rows if _ts(r[6]) is not None]
    if not rows:
        return {}
    last = max(_ts(r[6]) for r in rows)
    best = {}
    for r in rows:
        la = _ts(r[6])
        if (last - la).total_seconds() > run_window_s:
            continue
        ns = norm_sku(r[0])
        if ns and (ns not in best or la > _ts(best[ns][6])):
            best[ns] = r
    return best


def parity_row(ns, d, paused, outlier_pct=OUTLIER_PCT):
    """Строка price_parity из цен варианта d ({колонка: цена, 't': название}) и множества колонок в паузе. Разброс —
    по странам, без цен в паузе; выбросы — каналы дороже минимума страны больше чем на outlier_pct %."""
    p = {c: d.get(c) for c in PCOLS}
    eur = [p[c] for c in EUR if p.get(c)]
    allp = [p[c] for c in PCOLS if p.get(c)]
    if len(allp) < 2:
        return None
    dev, out = None, []
    for country, cols in COUNTRY.items():
        cp = {c: p[c] for c in cols if p.get(c) and c not in paused}
        if len(cp) < 2:
            continue
        cmn = min(cp.values())
        cdev = round((max(cp.values()) - cmn) / cmn * 100, 1)
        dev = cdev if dev is None else max(dev, cdev)
        for c, v in cp.items():
            if (v - cmn) / cmn > outlier_pct / 100:
                out.append(f"{c}:{v}€(+{round((v - cmn) / cmn * 100)}% к {country})")
    return {
        "norm_sku": ns, "product_name": d.get("t"),
        **{c: p.get(c) for c in PCOLS},
        "min_price": min(eur) if eur else None, "max_price": max(eur) if eur else None,
        "max_deviation_pct": dev, "channels_count": len(allp),
        "outlier_channels": "; ".join(out) if out else None,
        "promo_pause_channels": ", ".join(sorted(c for c in paused if p.get(c))) or None,
    }
