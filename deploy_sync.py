"""Новый код после мержа — без ребута Streamlit Cloud (19.10.2026, задача T-9).

Streamlit Cloud после пуша в main подтягивает файлы, но процесс сервера не перезапускает. `app.py` и страницы
Streamlit перечитывает с диска на каждом прогоне — а модули проекта (`i18n`, `auth`, `pbi`, …) остаются в
`sys.modules` такими, какими их импортировали при старте, и кэши `st.cache_data` / `st.cache_resource` живут дальше.
Отсюда «старый модуль рядом с новым»: страница уже новая, а переводы и функции модулей — прежние, новый ключ
перевода печатается самим ключом, пока кто-нибудь не перезапустит приложение руками.

Что делаем: на каждом прогоне читаем номер коммита рабочей копии (`.git/HEAD` → ref → sha, без git и без сети —
два маленьких файла) и сравниваем с номером, при котором процесс загрузил модули. Номер другой → сбросить оба кэша
и выгрузить модули проекта из `sys.modules`; `app.py` идёт дальше и импортирует их заново уже с диска, вместе со
свежим `i18n`.

Первый прогон процесса — особый случай: номера «при загрузке» ещё нет. Выгружаем модули, только если какой-то файл
проекта НОВЕЕ самого процесса (время старта — из `/proc` на Linux, где живёт Streamlit Cloud): это ровно мерж,
который принёс сам `deploy_sync` — процесс старый, файлы новые. Обычный старт процесса ничего не выгружает: модули
только что импортированы из тех же файлов, а тестовые подмены (`db.connection.get_connection` в проверках) не
теряются. На macOS `/proc` нет — первый прогон не выгружает ничего.

Звать `sync()` НАДО первой строкой `app.py`, до импорта модулей проекта: модуль, импортированный раньше, `app.py`
держал бы ссылкой на старый объект до конца прогона. Сам этот модуль импортирует только стандартную библиотеку и
streamlit — его выгружать нельзя, и он себя не выгружает.
"""
import os
import sys
import time

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
_FALLBACK_EVERY_S = 30          # без .git отпечаток кода считается не чаще раза в 30 с
_fallback = {"at": 0.0, "value": None}


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def current_commit():
    """sha коммита рабочей копии из `.git` (обычная ветка, отделённая голова, packed-refs); нет `.git` — None."""
    git = os.path.join(ROOT, ".git")
    if os.path.isfile(git):                       # worktree: в .git лежит «gitdir: <путь>»
        line = _read(git) or ""
        if line.startswith("gitdir:"):
            git = os.path.normpath(os.path.join(ROOT, line[len("gitdir:"):].strip()))
    head = _read(os.path.join(git, "HEAD"))
    if not head:
        return None
    if not head.startswith("ref:"):
        return head                               # отделённая голова: в HEAD сам sha
    ref = head[len("ref:"):].strip()
    sha = _read(os.path.join(git, ref))
    if sha:
        return sha
    common = _read(os.path.join(git, "commondir"))  # у worktree ветки лежат в общей папке
    base = os.path.normpath(os.path.join(git, common)) if common else git
    sha = _read(os.path.join(base, ref))
    if sha:
        return sha
    for line in (_read(os.path.join(base, "packed-refs")) or "").splitlines():
        parts = line.split(" ")
        if len(parts) == 2 and parts[1] == ref:
            return parts[0]
    return None


def _code_fingerprint():
    """Запасной отпечаток, если `.git` нет: время изменения и размер .py файлов проекта."""
    now = time.monotonic()
    if _fallback["value"] is not None and now - _fallback["at"] < _FALLBACK_EVERY_S:
        return _fallback["value"]
    parts = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__")) and d not in ("nb", "sql", "scratchpad", "docs", "exports")]
        for name in files:
            if name.endswith(".py"):
                p = os.path.join(base, name)
                try:
                    s = os.stat(p)
                    parts.append(f"{p}:{s.st_mtime_ns}:{s.st_size}")
                except OSError:
                    pass
    _fallback.update(at=now, value="fp:" + str(hash("|".join(sorted(parts)))))
    return _fallback["value"]


def version():
    """Что сейчас загружено: короткий sha или «отпечаток кода»."""
    v = current_commit() or _code_fingerprint()
    return v[:7] if not v.startswith("fp:") else v


def _process_started_at():
    """Время старта процесса (Linux: каталог /proc/<pid> создаётся при старте); где /proc нет — None."""
    try:
        return os.stat(f"/proc/{os.getpid()}").st_mtime
    except OSError:
        return None


def _project_newer_than(ts):
    """Есть ли загруженный модуль проекта, чей файл изменён позже ts."""
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None) or ""
        if name.startswith("__") or not f or "site-packages" in f or not os.path.abspath(f).startswith(ROOT + os.sep):
            continue
        try:
            if os.stat(f).st_mtime > ts:
                return True
        except OSError:
            pass
    return False


@st.cache_resource(show_spinner=False)
def _loaded():
    """Номер кода, при котором процесс загрузил модули. Живёт в cache_resource — один на процесс, общий для сессий."""
    return {"commit": None}


def _purge_project_modules():
    me = __name__
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None) or ""
        # __main__ — это сам исполняемый скрипт (app.py или страница): Streamlit держит его в sys.modules, и выгрузка
        # роняла прогон KeyError '__main__' (поймано локальной пробой 19.10.2026)
        if name.startswith("__") or name == me:
            continue
        if f and os.path.abspath(f).startswith(ROOT + os.sep) and "site-packages" not in f:
            sys.modules.pop(name, None)


def sync():
    """Первой строкой app.py. Коммит сменился (или первый прогон процесса) — сброс кэшей и выгрузка модулей проекта.
    Возвращает True, если сброс был в этом прогоне."""
    now = current_commit() or _code_fingerprint()
    box = _loaded()
    if box.get("commit") == now:
        return False
    if box.get("commit") is None:
        # первый прогон процесса: запомнить номер; выгружать — только если файлы проекта новее процесса
        started = _process_started_at()
        if started is None or not _project_newer_than(started):
            box["commit"] = now
            return False
    st.cache_data.clear()
    st.cache_resource.clear()       # вместе с ним уходит и box — заводим заново
    _purge_project_modules()
    _loaded()["commit"] = now
    print(f"[deploy_sync] код {now[:12]}: кэши сброшены, модули проекта перечитаются", flush=True)
    return True
