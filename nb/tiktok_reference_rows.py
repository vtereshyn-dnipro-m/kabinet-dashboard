# TikTok Shop, справочники (группа D: логистика и категории, 26.10.2026) → строки сырья `dnipro_m.tiktok.raw_*`.
# Чистые функции без сети и без Spark: их импортирует `Kabinet - TikTok Shop Reference Loader` и проверяют тесты CI.
#
# Только справочники магазина, данных покупателей здесь нет. Адрес склада и контакт склада — данные компании, но в
# сырьё они не нужны и не пишутся: из адреса остаются регион и страна, остальное вырезается и из колонок, и из raw_json.
# Типизированные колонки — для ключей и главного, остальное — в raw_json.
# Источник кода — nb/tiktok_reference_rows.py в kabinet-dashboard.
import json

# из адреса склада — только это; улица, дом, индекс, город, район, телефон, контакт, полный адрес не пишутся
ADDRESS_KEEP = ("region", "region_code", "state")


def _addr(a):
    if not isinstance(a, dict):
        return None
    return {k: a.get(k) for k in ADDRESS_KEEP if a.get(k) not in (None, "")}


def _j(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _bool(v):
    return None if v is None else bool(v)


def _base(shop, loaded_at):
    return {"shop_id": shop["id"], "region": shop.get("region"), "loaded_at": loaded_at}


def warehouse_row(shop, w, loaded_at):
    a = _addr(w.get("address"))
    clean = {k: v for k, v in w.items() if k != "address"}
    if a:
        clean["address"] = a
    return {**_base(shop, loaded_at), "warehouse_id": w.get("id"), "name": w.get("name"), "type": w.get("type"),
            "sub_type": w.get("sub_type"), "effect_status": w.get("effect_status"), "is_default": _bool(w.get("is_default")),
            "region_code": (a or {}).get("region_code"), "state": (a or {}).get("state"), "raw_json": _j(clean)}


def delivery_option_row(shop, warehouse_id, d, loaded_at):
    return {**_base(shop, loaded_at), "warehouse_id": warehouse_id, "delivery_option_id": d.get("id"),
            "name": d.get("name"), "type": d.get("type"),
            "platforms": ",".join(d.get("platform") or []) or None, "raw_json": _j(d)}


def shipping_provider_row(shop, delivery_option_id, p, loaded_at):
    return {**_base(shop, loaded_at), "delivery_option_id": delivery_option_id, "provider_id": p.get("id"),
            "name": p.get("name"), "raw_json": _j(p)}


def category_row(shop, locale, c, loaded_at):
    return {**_base(shop, loaded_at), "locale": locale, "category_id": c.get("id"), "parent_id": c.get("parent_id"),
            "local_name": c.get("local_name"), "is_leaf": _bool(c.get("is_leaf")),
            "permission_statuses": ",".join(c.get("permission_statuses") or []) or None}


def leaf_of(chain):
    """Лист цепочки категорий товара: элемент с is_leaf, иначе последний; пусто — None."""
    chain = [x for x in (chain or []) if isinstance(x, dict) and x.get("id")]
    if not chain:
        return None
    return next((x["id"] for x in chain if x.get("is_leaf")), chain[-1]["id"])


def product_category_row(shop, product_id, chain, loaded_at):
    chain = [x for x in (chain or []) if isinstance(x, dict)]
    return {**_base(shop, loaded_at), "product_id": product_id, "category_id": leaf_of(chain),
            "category_path": " > ".join(x.get("local_name") or "" for x in chain) or None,
            "category_chain_json": _j(chain)}


def attribute_row(shop, category_id, a, loaded_at):
    # TikTok пишет поле с опечаткой — «is_requried»; читаем оба написания
    req = a.get("is_required", a.get("is_requried"))
    return {**_base(shop, loaded_at), "category_id": category_id, "attribute_id": a.get("id"), "name": a.get("name"),
            "type": a.get("type"), "is_required": _bool(req), "is_customizable": _bool(a.get("is_customizable")),
            "is_multiple_selection": _bool(a.get("is_multiple_selection")), "values_count": len(a.get("values") or []),
            "raw_json": _j(a)}


def rules_row(shop, category_id, r, loaded_at):
    r = r or {}
    certs = r.get("product_certifications") or []

    def flag(k, sub="is_required"):
        v = r.get(k)
        return _bool(v.get(sub)) if isinstance(v, dict) and sub in v else None

    return {**_base(shop, loaded_at), "category_id": category_id,
            "cod_supported": flag("cod", "is_supported"), "epr_required": flag("epr"),
            "manufacturer_required": flag("manufacturer"), "responsible_person_required": flag("responsible_person"),
            "package_dimension_required": flag("package_dimension"), "size_chart_required": flag("size_chart"),
            "certifications_count": len(certs),
            "required_certifications_count": sum(1 for c in certs if isinstance(c, dict) and c.get("is_required")),
            "raw_json": _j(r)}


def has_keys(row, keys):
    return all(row.get(k) is not None for k in keys)
