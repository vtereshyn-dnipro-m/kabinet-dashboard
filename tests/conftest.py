"""Общие настройки автопроверок (CI, GitHub Actions — .github/workflows/ci.yml).

Здесь — только проверки БЕЗ доступа к Databricks и Lakebase: в GitHub нет и не будет секретов (репозиторий
публичный). Проверки на живой базе — `scratchpad/smoke_*.py` и другие из `scratchpad/README.md`, их гоняют локально.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
