"""Журнал «доехал ли мерж без ребута» — kabinet_data.app_deploy_log (19.10.2026, задача T-11).

`deploy_sync` после мержа выгружает модули проекта, и `app.py` импортирует их заново. Этот модуль — обычный модуль
проекта, поэтому его импорт САМ является событием: он случается при старте процесса и при каждом перечитывании.
Различаем по возрасту процесса в момент импорта: процесс живёт дольше `_START_WINDOW_S` — модули перечитаны в живом
процессе (`reload`, сработал `deploy_sync`); моложе — процесс только что запущен (`start`: первый запуск, ребут или
перезапуск самим Streamlit Cloud после сна). По одной подписи «Версия кода» эти случаи не различить — по журналу можно.

Почему не в самом `deploy_sync`: он себя не перезагружает, и новая функция в нём после мержа не появилась бы в
работающем процессе до ребута — `app.py` вызвал бы её и упал. Здесь такого нет: модуль новый, импортируется заново.

Пишет одну строку на импорт, не на каждый прогон. Нет таблицы, нет прав, база недоступна — событие остаётся в памяти,
следующая попытка не раньше чем через минуту; на работу страниц это не влияет.
"""
import os
import time

_START_WINDOW_S = 120          # процесс моложе двух минут в момент импорта — это старт, а не перечитывание
_RETRY_S = 60
_IMPORTED_AT = time.time()
_event = {"written": False, "last_try": 0.0}


def _process_age(now):
    try:
        import deploy_sync                     # время старта процесса считает он (из /proc/self/stat)
        started = deploy_sync._process_started_at()
    except Exception:
        started = None
    return (now - started) if started else None, started


def report(get_connection, app):
    """Записать событие этого импорта в kabinet_data.app_deploy_log (один раз). Звать в app.py после импорта
    db.connection. Ошибки не наружу: журнал не должен ломать страницу."""
    now = time.time()
    if _event["written"] or now - _event["last_try"] < _RETRY_S:
        return
    _event["last_try"] = now
    try:
        import deploy_sync
        commit = deploy_sync.current_commit() or ""
    except Exception:
        commit = ""
    age, started = _process_age(_IMPORTED_AT)
    kind = "unknown" if age is None else ("reload" if age > _START_WINDOW_S else "start")
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO kabinet_data.app_deploy_log
                                   (app, kind, commit_sha, imported_at, process_started_at, pid)
                               VALUES (%s, %s, %s, to_timestamp(%s), to_timestamp(%s), %s)""",
                            (app, kind, commit[:40] or None, _IMPORTED_AT, started, os.getpid()))
            conn.commit()
        finally:
            conn.close()
        _event["written"] = True
    except Exception as e:
        print(f"[deploy_log] не записано: {type(e).__name__}", flush=True)
