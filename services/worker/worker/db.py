from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from worker.settings import get_settings


def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@contextmanager
def session_scope():
    engine = get_engine()
    with Session(engine) as session:
        yield session
