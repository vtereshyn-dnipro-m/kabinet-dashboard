"""Зависимости входа через Google (`scratchpad/check_login_deps.py`): Authlib, httpx и маршруты входа Streamlit.

Проверка имеет смысл только в ЧИСТОМ окружении по `requirements.txt` — CI именно такой: ставит `requirements.txt` и
pytest, больше ничего. Локально в общем окружении она может пройти «случайно», если нужная библиотека стоит от
чего-то другого. Класс поломки уже доходил до владельца: включение входа падало на отсутствующем httpx.
"""
import os
import subprocess
import sys

from conftest import ROOT


def test_login_dependencies():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scratchpad", "check_login_deps.py")], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
