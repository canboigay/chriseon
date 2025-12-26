from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


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
    client = OpenAI(api_key=api_key)
    
    # Build full prompt with tool context if provided
    full_input = user_input
    if tool_context:
        full_input = f"{user_input}\n\n--- Tool Results from Previous Iteration ---\n{tool_context}"
    
    # Use chat completions API for tool support
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": full_input},
    ]
    
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    # Best-effort output cap (API may ignore/rename depending on model)
    if max_output_tokens is not None:
        kwargs["max_tokens"] = int(max_output_tokens)

    resp = client.chat.completions.create(**kwargs)
    
    message = resp.choices[0].message
    
    # Extract tool calls if any
    tool_calls = None
    if message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in message.tool_calls
        ]
    
    output_text = message.content or ""
    
    usage: dict[str, Any] = {}
    if resp.usage:
        usage = resp.usage.model_dump()
    
    return output_text, usage, tool_calls
