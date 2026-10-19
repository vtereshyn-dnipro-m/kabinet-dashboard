"""deploy_log: вид события — «reload» (модули перечитаны в живом процессе) или «start» (процесс запущен заново);
пишется один раз; при сбое записи — повтор не чаще раза в минуту, страница не падает. Без базы: соединение подменено.

Три случая из проверки PR #333: повторный импорт — всегда reload; первый импорт при файлах новее процесса (мерж,
принёсший механизм) — reload; первый импорт при файлах старше процесса (перезапуск, первый посетитель пришёл через
часы) — start."""
import importlib
import sys
import time

import deploy_log
import deploy_sync


class _Cur:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, args):
        self.log.append(args)


class _Conn:
    def __init__(self, log, fail=False):
        self.log, self.fail = log, fail

    def cursor(self):
        if self.fail:
            raise RuntimeError("нет таблицы")
        return _Cur(self.log)

    def commit(self):
        pass

    def close(self):
        pass


def _import(monkeypatch, *, nth, newer, started=1_700_000_000.0):
    """Импорт deploy_log так, будто это его nth-й импорт в процессе (0 — первый)."""
    monkeypatch.setattr(sys, "_kabinet_deploy_log_imports", nth, raising=False)
    monkeypatch.setattr(deploy_sync, "_process_started_at", lambda: started)
    monkeypatch.setattr(deploy_sync, "_project_newer_than", lambda ts: newer)
    monkeypatch.setattr(deploy_sync, "current_commit", lambda: "abc1234def")
    return importlib.reload(deploy_log)


def _kind(mod):
    rows = []
    mod.report(lambda: _Conn(rows), "kabinet")
    return rows[0][1]


def test_repeat_import_is_reload(monkeypatch):
    assert _kind(_import(monkeypatch, nth=1, newer=False)) == "reload"


def test_first_import_after_merge_is_reload(monkeypatch):
    assert _kind(_import(monkeypatch, nth=0, newer=True)) == "reload"


def test_first_import_after_restart_is_start(monkeypatch):
    # процесс перезапущен ночью, первый посетитель утром: файлы старше процесса — это старт, а не перечитывание
    assert _kind(_import(monkeypatch, nth=0, newer=False)) == "start"


def test_unknown_without_proc(monkeypatch):
    assert _kind(_import(monkeypatch, nth=0, newer=False, started=None)) == "unknown"


def test_counter_survives_in_sys(monkeypatch):
    monkeypatch.setattr(sys, "_kabinet_deploy_log_imports", 0, raising=False)
    importlib.reload(deploy_log)
    importlib.reload(deploy_log)
    assert sys._kabinet_deploy_log_imports == 2


def test_written_once(monkeypatch):
    rows = []
    mod = _import(monkeypatch, nth=1, newer=False)
    for _ in range(5):
        mod.report(lambda: _Conn(rows), "kabinet")
    assert len(rows) == 1
    assert rows[0][0] == "kabinet" and rows[0][2] == "abc1234def"


def test_failure_is_quiet_and_throttled(monkeypatch):
    rows, calls = [], []
    mod = _import(monkeypatch, nth=1, newer=False)

    def factory():
        calls.append(1)
        return _Conn(rows, fail=True)

    mod.report(factory, "kabinet")                   # таблицы нет — не падает
    mod.report(factory, "kabinet")                   # сразу же — без новой попытки
    assert len(calls) == 1 and not rows
    mod._event["last_try"] = time.time() - 61        # прошла минута — пробует снова
    mod.report(lambda: _Conn(rows), "kabinet")
    assert len(rows) == 1
