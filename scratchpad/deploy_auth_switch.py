# -*- coding: utf-8 -*-
"""Выложить рубильник входа из репозитория в Databricks и сверить побайтно.

Ноутбуки в этом репозитории обычно не версионируются — живут в Databricks. Рубильник
исключение по решению владельца 30.09.2026: аварийный инструмент должен быть под
версиями, иначе после чьей-нибудь правки не узнать, каким он был. Отсюда и этот
скрипт — чтобы «в репозитории» и «в Databricks» не разъезжались молча.

    python scratchpad/deploy_auth_switch.py
"""
import base64
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ExportFormat, ImportFormat, Language

ПУТЬ = "/Shared/Kabinet - Рубильник входа"
ИСХОДНИК = "nb/auth_switch.py"

w = WorkspaceClient()
src = open(ИСХОДНИК, encoding="utf-8").read()
w.workspace.import_(path=ПУТЬ, format=ImportFormat.SOURCE, language=Language.PYTHON,
                    content=base64.b64encode(src.encode()).decode(), overwrite=True)
живой = base64.b64decode(w.workspace.export(path=ПУТЬ, format=ExportFormat.SOURCE).content).decode()
print("выложен:", ПУТЬ)
print("совпадает с репозиторием:", живой.strip() == src.strip())
