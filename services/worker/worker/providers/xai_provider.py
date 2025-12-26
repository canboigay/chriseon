from __future__ import annotations

import json
from typing import Any

from xai_sdk import Client
from xai_sdk.chat import system, user


def generate(
    model: str,
    instructions: str,
    user_input: str,
    api_key: str,
    tools: list[dict[str, Any]] | None = None,
    tool_context: str | None = None,
    max_output_tokens: int | None = None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]] | None]:
    """
    Generate response with optional tool calling support.
    
    Returns:
        (output_text, usage_dict, tool_calls or None)
    """
    # Note: xAI SDK may not support function calling yet
    # This is a basic implementation that ignores tools for now
    client = Client(api_key=api_key)
    
    full_input = user_input
    if tool_context:
        full_input = f"{user_input}\n\n--- Tool Results from Previous Iteration ---\n{tool_context}"
    
    chat = client.chat.create(
        model=model,
        messages=[system(instructions)],
    )
    chat.append(user(full_input))
    resp = chat.sample()

    usage: dict[str, Any] = {}
    if getattr(resp, "usage", None) is not None:
        usage = getattr(resp.usage, "model_dump", lambda: {})() or {}

    # xAI doesn't support tool calling in SDK yet, return None
    return (resp.content or "").strip(), usage, None
