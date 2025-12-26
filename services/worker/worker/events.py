from __future__ import annotations

import json
from typing import Any

import redis

from worker.settings import get_settings


def get_redis() -> redis.Redis:
    settings = get_settings()
    # For RQ compatibility we must NOT enable decode_responses, since RQ
    # expects to work with raw bytes in many codepaths (e.g. intermediate_queue).
    # Using decode_responses=True caused strings to be returned where RQ
    # expects bytes and calls .decode(), crashing the worker.
    return redis.Redis.from_url(settings.redis_url, decode_responses=False)


def stream_key(run_id: str) -> str:
    return f"run:{run_id}:events"


def publish_event(run_id: str, event_type: str, payload: dict[str, Any]) -> str:
    r = get_redis()
    return r.xadd(
        stream_key(run_id),
        {
            "type": event_type,
            "payload": json.dumps(payload, separators=(",", ":")),
        },
    )
