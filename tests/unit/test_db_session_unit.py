import psycopg2

from app.db import session


class _FakeCursor:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query):
        if self.should_fail:
            raise psycopg2.OperationalError("SSL connection has been closed unexpectedly")


class _FakeConn:
    def __init__(self, *, closed=0, should_fail=False):
        self.closed = closed
        self.should_fail = should_fail
        self.rollback_calls = 0

    def cursor(self):
        return _FakeCursor(should_fail=self.should_fail)

    def rollback(self):
        self.rollback_calls += 1


class _FakePool:
    def __init__(self, conns):
        self.conns = list(conns)
        self.put_calls = []

    def getconn(self):
        return self.conns.pop(0)

    def putconn(self, conn, close=False):
        self.put_calls.append((conn, close))


def test_get_db_connection_retries_dead_pooled_connection(monkeypatch):
    stale_conn = _FakeConn(should_fail=True)
    healthy_conn = _FakeConn()
    fake_pool = _FakePool([stale_conn, healthy_conn])
    monkeypatch.setattr(session, "_get_pool", lambda: fake_pool)

    conn = session.get_db_connection()

    assert conn._conn is healthy_conn
    assert fake_pool.put_calls == [(stale_conn, True)]


def test_pooled_connection_close_discards_closed_connection():
    conn = _FakeConn(closed=1)
    fake_pool = _FakePool([])
    wrapped = session._PooledConnection(conn, fake_pool)

    wrapped.close()

    assert fake_pool.put_calls == [(conn, True)]
