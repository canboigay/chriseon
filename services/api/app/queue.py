from __future__ import annotations

from rq import Queue

from app.events import get_redis


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=get_redis())
