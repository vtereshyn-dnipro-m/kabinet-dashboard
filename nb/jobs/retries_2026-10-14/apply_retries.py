"""Автоповтор у наших загрузчиков и реплики (14.10.2026, решение владельца): 2 повтора с паузой 10 минут.

Запуск ПОСЛЕ мержа, профилем владельца:  python3 apply_retries.py            (проба — только показать, что изменится)
                                        python3 apply_retries.py --apply    (сохранить копию «до» и применить)
Настройки берутся ЖИВЫЕ из Jobs API в момент запуска, а не из файла: между мержем и выкладкой джобу могли поменять, и
перезапись старым снимком откатила бы чужую правку. Меняется только тройка полей у задач-ноутбуков из jobs.json;
задачи run_job_task и condition не трогаем — у запускаемой джобы свои повторы, второй слой повторил бы её дважды.
Копия «до» — before/<job_id>.json; откат — `databricks jobs reset` с settings из неё.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "jobs.json")))
APPLY = "--apply" in sys.argv
RETRY = {"max_retries": CFG["max_retries"], "min_retry_interval_millis": CFG["min_retry_interval_millis"],
         "retry_on_timeout": CFG["retry_on_timeout"]}


def cli(*args, payload=None):
    cmd = ["databricks", *args]
    if payload is not None:
        cmd += ["--json", json.dumps(payload)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


os.makedirs(os.path.join(HERE, "before"), exist_ok=True)
changed = 0
for j in CFG["jobs"]:
    live = cli("jobs", "get", str(j["job_id"]), "-o", "json")
    tasks = live["settings"]["tasks"]
    todo = [t for t in tasks if t["task_key"] in j["tasks"] and t.get("notebook_task")
            and any(t.get(k) != v for k, v in RETRY.items())]
    if not todo:
        print(f"  уже так   {j['name']}")
        continue
    print(f"  {'меняю' if APPLY else 'изменится'}  {j['name']}: {', '.join(t['task_key'] for t in todo)}")
    if not APPLY:
        continue
    with open(os.path.join(HERE, "before", f"{j['job_id']}.json"), "w") as f:
        json.dump(live, f, ensure_ascii=False, indent=1)
    for t in tasks:
        if t in todo:
            t.update(RETRY)
    cli("jobs", "update", payload={"job_id": j["job_id"], "new_settings": {"tasks": tasks}})
    back = cli("jobs", "get", str(j["job_id"]), "-o", "json")["settings"]["tasks"]
    bad = [t["task_key"] for t in back if t["task_key"] in j["tasks"] and any(t.get(k) != v for k, v in RETRY.items())]
    if bad:
        raise RuntimeError(f"{j['name']}: после правки повтор не встал у {bad}")
    changed += 1
print(f"{'применено' if APPLY else 'проба'}: {changed if APPLY else 'см. выше'}; исключены: "
      + "; ".join(f"{x['name']} — {x['why']}" for x in CFG["excluded"]))
