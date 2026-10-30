"""auth._load_user: обрыв связи с базой повторяется, после повторов — DbUnavailable, а не «строки нет»; прочие ошибки
не повторяются; человек без прочитанной карточки — «Просмотр» без стран и не запоминается на сеанс. Без базы:
чтение карточки подменено."""
import types

import psycopg2
import pytest

import auth


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    cached = auth._load_user          # тест может подменить саму функцию — чистим кеш настоящей
    cached.clear()
    monkeypatch.setattr(auth.time, "sleep", lambda s: None)
    yield
    cached.clear()


def _reader(results):
    calls = []

    def read(email):
        calls.append(email)
        r = results[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r
    return read, calls


def test_retry_after_wakeup(monkeypatch):
    row = {"role": "admin", "is_active": True, "access_until": None, "expired": False, "countries": []}
    read, calls = _reader([psycopg2.OperationalError("server closed the connection unexpectedly"),
                           psycopg2.InterfaceError("connection already closed"), row])
    monkeypatch.setattr(auth, "_read_user", read)
    assert auth._load_user("a@dniprom.com") == row
    assert len(calls) == 3


def test_no_row_is_none_not_error(monkeypatch):
    read, calls = _reader([None])
    monkeypatch.setattr(auth, "_read_user", read)
    assert auth._load_user("new@dniprom.com") is None
    assert len(calls) == 1


def test_db_down_after_all_retries(monkeypatch):
    n = len(auth._RETRY_PAUSES) + 1
    read, calls = _reader([psycopg2.OperationalError("could not connect")] * n)
    monkeypatch.setattr(auth, "_read_user", read)
    with pytest.raises(auth.DbUnavailable):
        auth._load_user("a@dniprom.com")
    assert len(calls) == n


def test_other_errors_not_retried(monkeypatch):
    read, calls = _reader([psycopg2.ProgrammingError("relation does not exist")])
    monkeypatch.setattr(auth, "_read_user", read)
    with pytest.raises(psycopg2.ProgrammingError):
        auth._load_user("a@dniprom.com")
    assert len(calls) == 1


def test_from_login_db_down_is_safe_viewer(monkeypatch):
    monkeypatch.setattr(auth, "_logged_in", lambda: True)
    monkeypatch.setattr(auth.st, "user", types.SimpleNamespace(email="A@dniprom.com", name="A"), raising=False)

    def down(email):
        raise auth.DbUnavailable("could not connect")
    monkeypatch.setattr(auth, "_load_user", down)
    u = auth._from_login()
    assert u.db_down and u.role == auth.VIEWER and u.countries == set() and not u.known
    assert not ({"ES"} <= u.countries)


def test_db_down_user_not_kept_for_session(monkeypatch):
    state = {}
    monkeypatch.setattr(auth.st, "session_state", state, raising=False)
    monkeypatch.setattr(auth, "_qa_user_from_url", lambda: None)
    monkeypatch.setattr(auth, "mode", lambda: auth.MODE_ON)
    monkeypatch.setattr(auth, "_from_login", lambda: auth.User(email="a@dniprom.com", logged_in=True, db_down=True))
    assert auth.current().db_down
    assert "_auth_user" not in state
    monkeypatch.setattr(auth, "_from_login", lambda: auth.User(email="a@dniprom.com", role=auth.ADMIN, logged_in=True))
    assert auth.current().role == auth.ADMIN and state["_auth_user"].role == auth.ADMIN
