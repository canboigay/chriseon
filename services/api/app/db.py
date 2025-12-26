from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.settings import get_settings


def get_engine():
    settings = get_settings()
    # Ensure we use psycopg (not psycopg2) driver
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(db_url, pool_pre_ping=True)


@contextmanager
def session_scope():
    engine = get_engine()
    with Session(engine) as session:
        yield session
