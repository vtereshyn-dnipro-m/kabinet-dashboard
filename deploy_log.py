"""Журнал «доехал ли мерж без ребута» — kabinet_data.app_deploy_log (19.10.2026, задача T-11).

`deploy_sync` после мержа выгружает модули проекта, и `app.py` импортирует их заново. Этот модуль — обычный модуль
проекта, поэтому его импорт САМ является событием: он случается при первом прогоне процесса и при каждом
перечитывании. По одной подписи «Версия кода» не различить, перечитал ли модули `deploy_sync` или Streamlit Cloud сам
перезапустил процесс — по журналу можно:
- повторный импорт в том же процессе (счётчик в `sys`, который не выгружается) — всегда `reload`;
- первый импорт — `reload`, только если файлы проекта новее старта процесса (это мерж, принёсший сам механизм, —
  `deploy_sync` тогда выгружает модули на первом прогоне), иначе `start`.
Возраст процесса для этого НЕ годится (замечание проверяющего PR #333): Streamlit исполняет `app.py` только при
заходе посетителя, и процесс, перезапущенный ночью, впервые импортирует модули утром — по возрасту это выглядело бы
перечитыванием.

Почему не в самом `deploy_sync`: он себя не перезагружает, и новая функция в нём после мержа не появилась бы в
работающем процессе до ребута — `app.py` вызвал бы её и упал. Здесь такого нет: модуль новый, импортируется заново.

Пишет одну строку на импорт, не на каждый прогон. Нет таблицы, нет прав, база недоступна — событие остаётся в памяти,
следующая попытка не раньше чем через минуту; на работу страниц это не влияет.
"""
import os
import sys
import time

_RETRY_S = 60
_IMPORTED_AT = time.time()
_event = {"written": False, "last_try": 0.0}
# сколько раз модуль импортировался в этом процессе: держим в sys — его deploy_sync не выгружает
_IMPORT_NO = getattr(sys, "_kabinet_deploy_log_imports", 0)
sys._kabinet_deploy_log_imports = _IMPORT_NO + 1


def _classify():
    """(вид события, время старта процесса). Время старта считает deploy_sync (из /proc/self/stat)."""
    try:
        import deploy_sync
        started = deploy_sync._process_started_at()
    except Exception:
        return "unknown", None
    if _IMPORT_NO > 0:
        return "reload", started
    if started is None:
        return "unknown", None
    try:
        newer = deploy_sync._project_newer_than(started)
    except Exception:
        return "unknown", started
    return ("reload" if newer else "start"), started


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
    kind, started = _classify()
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
