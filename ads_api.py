"""Amazon Ads API: чтение состояния кампании и две правки — пауза и ставка группы.

Ключи — только из `st.secrets["amazon_ads"]` (client_id, client_secret, refresh_token,
profile_id), в коде их нет. Вызовы делаются из обработчика кнопки и больше ниоткуда:
ни расписаний, ни фоновых задач у этого модуля нет.

Ставки в SP и SD живут у группы объявлений (`defaultBid`), у кампании ставки нет вовсе;
в SB группы своей ставки не имеют (там ставки у ключевых слов), поэтому для SB доступна
только пауза — `bid_supported()` про это и отвечает.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import streamlit as st

HOST = "advertising-api-eu.amazon.com"          # рынки Европы; AMC у нас только ES
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
_TOKEN_TTL_S = 50 * 60                          # access token живёт час
TIMEOUT_S = 60

# Тип рекламы из AMC → путь и заголовки. Три семейства эндпоинтов, три диалекта:
# SP/SB говорят JSON с версией в Content-Type, SD — обычным JSON и состояниями в нижнем регистре
PRODUCTS = {
    "sponsored_products": {
        "camp_list": ("/sp/campaigns/list", "application/vnd.spCampaign.v3+json"),
        "camp_update": ("/sp/campaigns", "application/vnd.spCampaign.v3+json"),
        "group_list": ("/sp/adGroups/list", "application/vnd.spAdGroup.v3+json"),
        "group_update": ("/sp/adGroups", "application/vnd.spAdGroup.v3+json"),
        "states": {"paused": "PAUSED", "enabled": "ENABLED"},
    },
    "sponsored_brands": {
        "camp_list": ("/sb/v4/campaigns/list", "application/vnd.sbcampaignresource.v4+json"),
        "camp_update": ("/sb/v4/campaigns", "application/vnd.sbcampaignresource.v4+json"),
        "group_list": None,                     # у групп SB нет своей ставки
        "group_update": None,
        "states": {"paused": "PAUSED", "enabled": "ENABLED"},
    },
    "sponsored_display": {
        "camp_list": ("/sd/campaigns", None),
        "camp_update": ("/sd/campaigns", None),
        "group_list": ("/sd/adGroups", None),
        "group_update": ("/sd/adGroups", None),
        "states": {"paused": "paused", "enabled": "enabled"},
    },
}


class AdsError(RuntimeError):
    """Ошибка вызова: текст уходит человеку на экран и в журнал, а не в лог."""


def configured() -> bool:
    try:
        s = st.secrets["amazon_ads"]
        return all(s.get(k) for k in ("client_id", "client_secret", "refresh_token", "profile_id"))
    except Exception:
        return False


def profile_id() -> str:
    return str(st.secrets["amazon_ads"]["profile_id"])


def bid_supported(ad_product: str) -> bool:
    return bool(PRODUCTS.get(ad_product, {}).get("group_update"))


@st.cache_resource(show_spinner=False)
def _token_box() -> dict:
    # cache_resource, а не cache_data: страницы зовут st.cache_data.clear() после каждого
    # сохранения, и токен вылетал бы вместе с данными
    return {"token": None, "at": 0.0}


def _access_token(force: bool = False) -> str:
    box = _token_box()
    if force or not box["token"] or time.time() - box["at"] > _TOKEN_TTL_S:
        s = st.secrets["amazon_ads"]
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token", "refresh_token": s["refresh_token"],
            "client_id": s["client_id"], "client_secret": s["client_secret"]}).encode()
        req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=TIMEOUT_S).read())
        except urllib.error.HTTPError as e:
            raise AdsError(f"LWA {e.code}: {e.read()[:200].decode(errors='replace')}") from e
        box["token"], box["at"] = resp["access_token"], time.time()
    return box["token"]


def _call(path: str, method: str = "GET", payload=None, ctype=None, params=None, retry=True):
    url = f"https://{HOST}{path}" + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + _access_token())
    req.add_header("Amazon-Advertising-API-ClientId", st.secrets["amazon_ads"]["client_id"])
    req.add_header("Amazon-Advertising-API-Scope", profile_id())
    req.add_header("Accept", ctype or "application/json")
    if data is not None:
        req.add_header("Content-Type", ctype or "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_S)
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        if e.code == 401 and retry:                 # токен протух раньше срока
            _access_token(force=True)
            return _call(path, method, payload, ctype, params, retry=False)
        try:
            return e.code, json.loads(raw or b"{}")
        except Exception:
            return e.code, {"raw": raw[:500].decode(errors="replace")}
    except urllib.error.URLError as e:
        raise AdsError(str(e.reason)) from e


# ── чтение ────────────────────────────────────────────────────────────────

def campaign_state(campaign_id: str, ad_product: str) -> str:
    """Состояние кампании сейчас. Берём перед каждым действием: в кабинете Amazon
    его могли поменять руками, и «было» в журнале должно быть настоящим, а не с экрана."""
    cfg = PRODUCTS[ad_product]
    path, ctype = cfg["camp_list"]
    if ad_product == "sponsored_display":
        st_, r = _call(path, params={"campaignIdFilter": str(campaign_id)})
        rows = r if isinstance(r, list) else []
        return str(rows[0].get("state", "")) if rows else ""
    st_, r = _call(path, "POST", {"campaignIdFilter": {"include": [str(campaign_id)]}, "maxResults": 10}, ctype)
    rows = (r or {}).get("campaigns", []) if isinstance(r, dict) else []
    return str(rows[0].get("state", "")) if rows else ""


def ad_groups(campaign_id: str, ad_product: str) -> list:
    """Группы кампании со ставками. Для SB — пусто: ставки там не на группе."""
    cfg = PRODUCTS[ad_product]
    if not cfg["group_list"]:
        return []
    path, ctype = cfg["group_list"]
    if ad_product == "sponsored_display":
        st_, r = _call(path, params={"campaignIdFilter": str(campaign_id)})
        rows = r if isinstance(r, list) else []
    else:
        st_, r = _call(path, "POST", {"campaignIdFilter": {"include": [str(campaign_id)]}, "maxResults": 500}, ctype)
        rows = (r or {}).get("adGroups", []) if isinstance(r, dict) else []
    out = []
    for g in rows:
        out.append({"adGroupId": str(g.get("adGroupId")), "name": g.get("name"),
                    "state": str(g.get("state", "")),
                    "defaultBid": None if g.get("defaultBid") is None else float(g["defaultBid"])})
    return sorted(out, key=lambda x: (x["defaultBid"] is None, -(x["defaultBid"] or 0)))


def snapshot(campaign_id: str, ad_product: str) -> dict:
    """Состояние «до» одним объектом — то, что кладётся в журнал и чем откатывают."""
    return {"campaign_state": campaign_state(campaign_id, ad_product),
            "ad_groups": ad_groups(campaign_id, ad_product)}


# ── запись ────────────────────────────────────────────────────────────────

def _verdict(status: int, body) -> tuple:
    """Ответы трёх семейств выглядят по-разному; сводим к «ok / partial / error» и тексту."""
    txt = json.dumps(body, ensure_ascii=False)[:1500]
    if status >= 400:
        return "error", txt
    errors = []
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, dict) and v.get("error"):
                errors += v["error"]
    elif isinstance(body, list):
        errors = [x for x in body if isinstance(x, dict) and (x.get("code") not in (None, "SUCCESS"))]
    if errors:
        return ("error" if status == 207 and not _has_success(body) else "partial"), txt
    return "ok", txt


def _has_success(body) -> bool:
    if isinstance(body, dict):
        return any(isinstance(v, dict) and v.get("success") for v in body.values())
    if isinstance(body, list):
        return any(isinstance(x, dict) and x.get("code") in (None, "SUCCESS") for x in body)
    return False


def set_campaign_state(campaign_id: str, ad_product: str, state_key: str) -> tuple:
    """state_key — 'paused' или 'enabled'; регистр и слово подставляем по семейству."""
    cfg = PRODUCTS[ad_product]
    path, ctype = cfg["camp_update"]
    value = cfg["states"][state_key]
    if ad_product == "sponsored_display":
        status, body = _call(path, "PUT", [{"campaignId": int(campaign_id), "state": value}])
    else:
        status, body = _call(path, "PUT", {"campaigns": [{"campaignId": str(campaign_id), "state": value}]}, ctype)
    verdict, txt = _verdict(status, body)
    return verdict, txt, body


def set_ad_group_bids(ad_product: str, bids: list) -> tuple:
    """bids — [(adGroupId, новая ставка)]. Пишем одним запросом: частичный успех
    Amazon вернёт по каждой группе, и он попадёт в журнал как есть."""
    cfg = PRODUCTS[ad_product]
    if not cfg["group_update"] or not bids:
        return "ok", "{}", {}
    path, ctype = cfg["group_update"]
    if ad_product == "sponsored_display":
        payload = [{"adGroupId": int(gid), "defaultBid": float(b)} for gid, b in bids]
        status, body = _call(path, "PUT", payload)
    else:
        payload = {"adGroups": [{"adGroupId": str(gid), "defaultBid": float(b)} for gid, b in bids]}
        status, body = _call(path, "PUT", payload, ctype)
    verdict, txt = _verdict(status, body)
    return verdict, txt, body


def lowered(bid: float, pct: float, floor: float) -> float:
    """Новая ставка: минус процент, не ниже минимальной у Amazon, два знака."""
    return max(round(float(bid) * (1 - pct / 100.0), 2), float(floor))
