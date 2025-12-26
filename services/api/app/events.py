from __future__ import annotations

import json
from typing import Any, Iterator

import redis

from app.settings import get_settings


def get_redis() -> redis.Redis:
    settings = get_settings()
    # RQ requires bytes (decode_responses=False).
    # We will manually decode strings for SSE events.
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


def iter_sse_events(run_id: str, last_id: str = "0-0") -> Iterator[tuple[str, dict[str, Any], str]]:
    r = get_redis()
    key = stream_key(run_id)

    # Ensure stream exists so SSE clients can connect before first event.
    # Do NOT trim the stream here; artifacts/events must remain queryable.
    if not r.exists(key):
        r.xadd(key, {"type": "ready", "payload": "{}"})

    while True:
        # Pass bytes keys/args to xread
        entries = r.xread({key: last_id}, block=10_000, count=50)
        if not entries:
            continue
        for _stream, messages in entries:
            for msg_id, fields in messages:
                # msg_id is bytes, fields keys/values are bytes
                last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                
                # Decode field keys/values
                fields_str = {
                    k.decode() if isinstance(k, bytes) else k: 
                    v.decode() if isinstance(v, bytes) else v 
                    for k, v in fields.items()
                }
                
                event_type = fields_str.get("type", "message")
                payload_raw = fields_str.get("payload", "{}")
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    payload = {"raw": payload_raw}
                yield event_type, payload, last_id
