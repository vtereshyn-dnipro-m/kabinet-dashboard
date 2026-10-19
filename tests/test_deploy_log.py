"""deploy_log: импорт модуля — событие «start» (процесс только что запущен) или «reload» (модули перечитаны в живом
процессе); пишется один раз; при сбое записи — повтор не чаще раза в минуту, страница не падает. Без базы: соединение
подменено."""
import importlib
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


def _fresh(monkeypatch, process_age_s):
    mod = importlib.reload(deploy_log)
    monkeypatch.setattr(deploy_sync, "_process_started_at", lambda: mod._IMPORTED_AT - process_age_s)
    monkeypatch.setattr(deploy_sync, "current_commit", lambda: "abc1234def")
    return mod


def test_start_vs_reload(monkeypatch):
    rows = []
    mod = _fresh(monkeypatch, 5)                     # процессу 5 секунд — старт
    mod.report(lambda: _Conn(rows), "kabinet")
    mod = _fresh(monkeypatch, 3600)                  # процессу час — модули перечитаны в живом процессе
    mod.report(lambda: _Conn(rows), "kabinet")
    assert [r[1] for r in rows] == ["start", "reload"]
    assert rows[0][0] == "kabinet" and rows[0][2] == "abc1234def"


def test_written_once(monkeypatch):
    rows = []
    mod = _fresh(monkeypatch, 3600)
    for _ in range(5):
        mod.report(lambda: _Conn(rows), "kabinet")
    assert len(rows) == 1


def test_failure_is_quiet_and_throttled(monkeypatch):
    rows = []
    mod = _fresh(monkeypatch, 3600)
    calls = []

    def factory():
        calls.append(1)
        return _Conn(rows, fail=True)

    mod.report(factory, "kabinet")                   # таблицы нет — не падает
    mod.report(factory, "kabinet")                   # сразу же — без новой попытки
    assert len(calls) == 1 and not rows
    mod._event["last_try"] = time.time() - 61        # прошла минута — пробует снова
    mod.report(lambda: _Conn(rows), "kabinet")
    assert len(rows) == 1


def test_unknown_without_proc(monkeypatch):
    rows = []
    mod = importlib.reload(deploy_log)
    monkeypatch.setattr(deploy_sync, "_process_started_at", lambda: None)
    mod.report(lambda: _Conn(rows), "kabinet")
    assert rows[0][1] == "unknown"
