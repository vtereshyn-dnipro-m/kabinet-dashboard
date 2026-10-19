"""Каждый модуль приложения импортируется без базы и без секретов.

Страницы (`home.py`, `pages/`) и `app.py` не импортируются: это скрипты Streamlit, при импорте они рисуют экран и
ходят в базу — их покрывает `test_syntax.py`, а прогон на живой базе — `scratchpad/smoke_full.py` локально.
Ловит то, чего компиляция не видит: опечатку в имени при импорте, модуль, который при загрузке лезет в базу или
в `st.secrets`, циклический импорт.
"""
import importlib
import os

import pytest

from conftest import ROOT

NOT_MODULES = {"app", "home"}           # скрипты Streamlit, а не модули


def _modules():
    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".py") and name[:-3] not in NOT_MODULES:
            yield name[:-3]
    for name in sorted(os.listdir(os.path.join(ROOT, "db"))):
        if name.endswith(".py") and name != "__init__.py":
            yield "db." + name[:-3]


@pytest.mark.parametrize("module", list(_modules()))
def test_imports(module):
    importlib.import_module(module)
