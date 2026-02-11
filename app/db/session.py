import psycopg2
from app.core.config import settings

def get_db_connection():
    """Returns a new database connection."""
    return psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT
    )

# For dependency injection in FastAPI
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
