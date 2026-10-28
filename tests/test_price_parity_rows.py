"""Паритет цен (`nb/price_parity_rows.py`, T-37, вариант 3): цена LM и CF по сроку скидки на момент сборки, пауза между
акциями не делает строку выбросом. Случаи — по живым данным 26–28.10.2026 (SKU 48261000)."""
import datetime as dt
import os
import sys

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "nb"))
import price_parity_rows as pp  # noqa: E402

UTC = dt.timezone.utc
T27 = dt.datetime(2026, 10, 27, 9, 46, tzinfo=UTC)      # сборка 27.10 12:46 Киев
T28 = dt.datetime(2026, 10, 28, 9, 48, tzinfo=UTC)


def test_lm_promo_active_28_10():
    # 28.10: price = discount = 57,99, origin 129, акция 27.10 07:30 – 16.11 21:00 UTC
    p, on = pp.mirakl_price(57.99, 129.0, 57.99, dt.datetime(2026, 10, 27, 7, 30, tzinfo=UTC),
                            dt.datetime(2026, 11, 16, 21, 0, tzinfo=UTC), T28)
    assert (p, on) == (57.99, True)


def test_lm_pause_27_10_fields_cleared():
    # 27.10 06:01 UTC: акция кончилась 26.10 21:00, полей скидки нет, price = origin = 129
    p, on = pp.mirakl_price(129.0, 129.0, None, None, None, T27)
    assert (p, on) == (129.0, False)
    # поля очищены — пауза видна только по истории снимков
    assert pp.in_pause(on, None, T27, recent_promo=True, pause_days=7) is True
    assert pp.in_pause(on, None, T27, recent_promo=False, pause_days=7) is False


def test_cf_expired_discount_not_taken_27_10():
    # 27.10: Carrefour держит скидку 48,99 со сроком до 25.10 21:00 — прежняя формула брала её; цена для покупателя 129
    end = dt.datetime(2026, 10, 25, 21, 0, tzinfo=UTC)
    p, on = pp.mirakl_price(129.0, 129.0, 48.99, dt.datetime(2026, 10, 15, 21, 0, tzinfo=UTC), end, T27)
    assert (p, on) == (129.0, False)
    assert pp.in_pause(on, end, T27, recent_promo=False, pause_days=7) is True
    assert pp.in_pause(on, end, T27 + dt.timedelta(days=10), recent_promo=False, pause_days=7) is False


def test_future_discount_not_taken_and_no_origin_falls_back_to_price():
    start = T27 + dt.timedelta(hours=3)
    assert pp.mirakl_price(129.0, None, 57.99, start, None, T27) == (129.0, False)
    assert pp.mirakl_price(57.99, None, None, None, None, T27) == (57.99, False)
    assert pp.mirakl_price("57.99", "129", "", None, None, T27) == (129.0, False)


def test_naive_dates_are_utc():
    end = dt.datetime(2026, 10, 30, 0, 0)          # без пояса
    assert pp.promo_active(50.0, None, end, T27) is True


def test_pause_does_not_make_outlier():
    d = {"t": "DGA-203SBC", "amz_es": 63.98, "mm_es": 48.99, "lm_es": 129.0, "cf_es": 129.0}
    r = pp.parity_row("48261000", d, paused={"lm_es", "cf_es"})
    assert r["outlier_channels"] is None or "lm_es" not in r["outlier_channels"]
    assert r["max_deviation_pct"] == round((63.98 - 48.99) / 48.99 * 100, 1)
    assert r["promo_pause_channels"] == "cf_es, lm_es"
    assert r["lm_es"] == 129.0 and r["channels_count"] == 4
    plain = pp.parity_row("48261000", d, paused=set())
    assert "lm_es:129.0€" in plain["outlier_channels"] and plain["promo_pause_channels"] is None


def test_row_needs_two_channels_and_country_split():
    assert pp.parity_row("1", {"amz_de": 10.0}, set()) is None
    r = pp.parity_row("2", {"amz_de": 150.0, "amz_es": 40.0}, set())
    assert r["max_deviation_pct"] is None and r["outlier_channels"] is None   # DE и ES — разные страны


def test_norm_sku():
    assert pp.norm_sku("amzn.gr.41324000-FBA-x1_") == "41324000"
    assert pp.norm_sku("S5_78626000") == "S5_78626000"
    assert pp.norm_sku("ABC") is None
