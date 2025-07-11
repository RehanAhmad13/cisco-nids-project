import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url


def get_tsdb_url() -> str:
    """Return TSDB connection URL from the ``TSDB_URL`` environment variable."""
    url = os.environ.get("TSDB_URL")
    if not url:
        raise RuntimeError("TSDB_URL environment variable not set")
    return url


def get_engine():
    """Return a SQLAlchemy engine using ``TSDB_URL``."""
    return create_engine(get_tsdb_url())


def get_conn():
    """Return a psycopg2 connection using ``TSDB_URL``."""
    url_obj = make_url(get_tsdb_url())
    return psycopg2.connect(
        dbname=url_obj.database,
        user=url_obj.username,
        password=url_obj.password,
        host=url_obj.host,
        port=url_obj.port,
    )
