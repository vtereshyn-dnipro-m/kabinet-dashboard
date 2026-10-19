"""Проверки прав, которым не нужна база: `scratchpad/auth_gate.py` (кого пускаем на вход, срок доступа) и
`scratchpad/pages_vis_test.py` (видимость страниц по матрице, QA-агент). Скрипты печатают «расхождений: N» и
возвращают 0 даже при расхождениях — поэтому успех здесь определяется по итоговой строке, а не по коду возврата.
"""
import os
import re
import subprocess
import sys

import pytest

from conftest import ROOT


@pytest.mark.parametrize("script", ["scratchpad/auth_gate.py", "scratchpad/pages_vis_test.py"])
def test_auth_script(script):
    env = dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.environ.get("PYTHONPATH", ""))
    r = subprocess.run([sys.executable, os.path.join(ROOT, script)], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-2000:]
    found = re.findall(r"расхождений:\s*(\d+)", out)
    assert found, "нет итоговой строки «расхождений: N»:\n" + out[-2000:]
    assert found[-1] == "0", out[-2000:]
