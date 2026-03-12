from typing import Optional

import psycopg2
from psycopg2 import pool
from app.core.config import settings

# Connection pool: min 2, max 10. Reuses connections for faster requests.
_db_pool: Optional[pool.ThreadedConnectionPool] = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _db_pool
    if _db_pool is None:
        conn_params = {
            "host": settings.DB_HOST,
            "database": settings.DB_NAME,
            "user": settings.DB_USER,
            "password": settings.DB_PASSWORD,
            "port": settings.DB_PORT,
        }
        if getattr(settings, "DB_SSLMODE", None):
            conn_params["sslmode"] = settings.DB_SSLMODE
        _db_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            **conn_params,
        )
    return _db_pool


class _PooledConnection:
    """Wrapper so conn.close() returns to pool instead of closing."""

    def __init__(self, conn, pool_obj: pool.ThreadedConnectionPool):
        self._conn = conn
        self._pool = pool_obj

    def close(self):
        self._pool.putconn(self._conn)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    """Returns a connection from the pool. Call close() to return it."""
    p = _get_pool()
    conn = p.getconn()
    return _PooledConnection(conn, p)


# For dependency injection in FastAPI
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
