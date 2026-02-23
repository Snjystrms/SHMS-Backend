import psycopg2
from app.core.config import settings

def get_db_connection():
    """Returns a new database connection."""
    conn_params = {
        "host": settings.DB_HOST,
        "database": settings.DB_NAME,
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "port": settings.DB_PORT,
    }
    if getattr(settings, "DB_SSLMODE", None):
        conn_params["sslmode"] = settings.DB_SSLMODE
    return psycopg2.connect(**conn_params)

# For dependency injection in FastAPI
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
