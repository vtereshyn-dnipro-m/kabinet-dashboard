"""Версия данных входит в ключ кеша страниц (T-16, 21.10.2026).

Загрузчики страниц принимают отметку последней записи (`data_version(...)`), чтобы после записи в таблицу все страницы
перечитали её сразу, а не по своему TTL. Аргументы с «_» в начале Streamlit в ключ `st.cache_data` не берёт
(`streamlit/runtime/caching/cache_utils.py`), и до 21.10.2026 параметр назывался `_v` — версия не меняла ничего, кеш
жил по TTL 5–10 минут. Первая проверка ловит возврат к имени с подчёркиванием, вторая — что сам Streamlit по-прежнему
пересчитывает функцию на новой версии.
"""
import ast
import os

import pytest

from conftest import ROOT

PAGES = ["home.py"] + sorted(
    os.path.join("pages", n) for n in os.listdir(os.path.join(ROOT, "pages")) if n.endswith(".py"))


def _cached_functions(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "cache_data":
                yield node


@pytest.mark.parametrize("path", PAGES)
def test_version_param_is_hashed(path):
    bad = []
    for fn in _cached_functions(path):
        args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
        bad += [f"{fn.name}({a.arg})" for a in args if a.arg.startswith("_v")]
    assert not bad, f"{path}: версия с «_» в имени не входит в ключ кеша — {', '.join(bad)}; назвать `ver`"


def test_streamlit_rehashes_on_new_version():
    import streamlit as st

    calls = []

    @st.cache_data(ttl=600)
    def load(days, ver=""):
        calls.append(ver)
        return len(calls)

    load.clear()
    assert load(30, "v1") == 1
    assert load(30, "v1") == 1          # та же версия — из кеша
    assert load(30, "v2") == 2          # новая запись в таблицу — пересчёт без ожидания TTL
    load.clear()
