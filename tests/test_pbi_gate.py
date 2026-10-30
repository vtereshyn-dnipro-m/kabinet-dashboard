"""pbi: строки площадок из GATED (Worten) страницы показывают только при флаге = 1 — условие стоит во всех четырёх
запросах к реплике, безопасно к пустой площадке и читает флаг сам. Без базы."""
import re

import pbi


def test_gate_in_every_replica_query():
    for name in ("DAILY_SQL", "SKU_SQL", "ORDERS_SQL", "COUNTRY_SQL"):
        sql = getattr(pbi, name)
        assert "pbi_marketplace IS DISTINCT FROM 'Worten'" in sql, name
        assert "key = 'worten_overview_enabled'" in sql, name


def test_gate_is_null_safe_and_defaults_hidden():
    g = pbi._gate()
    assert "NOT (" not in g                      # «NOT (x = …)» с пустой площадкой дал бы NULL и потерял строку
    assert re.search(r"COALESCE\(\(SELECT value FROM kabinet_data\.reorder_params WHERE key = 'worten_overview_enabled'\), 0\) = 1", g)


def test_market_filter_placeholder_still_works():
    sql = pbi.DAILY_SQL.format(mk=pbi._mk(("ES",)))
    assert "marketplace = ANY(%(mk)s)" in sql and "{mk}" not in sql
    assert "{mk}" not in pbi.ORDERS_SQL.format(mk="")
