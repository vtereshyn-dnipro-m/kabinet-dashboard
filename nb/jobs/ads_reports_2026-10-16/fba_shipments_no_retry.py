"""FBA Shipments Loader без автоповторов джобы (16.10.2026, решение владельца): на 429 createReport ноутбук больше не ждёт
и не повторяет, и повтор всей джобы через 10 минут снова занял бы квоту аккаунта. Запуск ПОСЛЕ мержа, профилем владельца:
    python3 fba_shipments_no_retry.py            (проба — показать, что изменится)
    python3 fba_shipments_no_retry.py --apply    (применить)
Настройки берутся ЖИВЫЕ из Jobs API, меняется только max_retries у задачи load — чужие правки не откатываются.
"""
import json, subprocess, sys

JOB_ID = 821057250140489
live = json.loads(subprocess.check_output(["databricks", "jobs", "get", str(JOB_ID), "-o", "json"]))["settings"]
tasks = live["tasks"]
for t in tasks:
    if t["task_key"] == "load":
        print(f"load: max_retries {t.get('max_retries')} → 0")
        t["max_retries"] = 0
        t.pop("min_retry_interval_millis", None)
if "--apply" in sys.argv:
    subprocess.check_call(["databricks", "jobs", "update", "--json",
                           json.dumps({"job_id": JOB_ID, "new_settings": {"tasks": tasks}})])
    print("применено")
