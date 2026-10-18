"""Каждый .py репозитория компилируется — приложение, ноутбуки `nb/`, проверочные скрипты.

Ловит то, что уже дважды уезжало в прод: страница с повторным `help=` («Остатки», PR #195) и ноутбук с обратной
косой чертой внутри выражения f-строки (T-7, 19.10.2026: на Python до 3.12 это SyntaxError). CI гоняет на 3.11 —
это версия serverless-окружения Databricks, и она строже 3.12 к f-строкам.
"""
import os

import pytest

from conftest import ROOT

SKIP_DIRS = {".git", ".github", "__pycache__", ".venv", "exports", ".claude", "mcp_servers"}


def _files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.relpath(os.path.join(base, name), ROOT)


@pytest.mark.parametrize("path", list(_files()))
def test_compiles(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        source = f.read()
    compile(source, path, "exec")
