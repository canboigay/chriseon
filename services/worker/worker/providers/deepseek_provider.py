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
    stream_callback: Any | None = None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]] | None]:
    """
    Generate response using DeepSeek API (OpenAI-compatible).
    
    Args:
        stream_callback: Optional callback function(chunk: str) called for each streamed chunk
    
    Returns:
        (output_text, usage_dict, tool_calls or None)
    """
    # DeepSeek uses OpenAI-compatible API at api.deepseek.com
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )
    
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

    # Best-effort output cap
    if max_output_tokens is not None:
        kwargs["max_tokens"] = int(max_output_tokens)

    # Enable streaming if callback provided
    if stream_callback:
        kwargs["stream"] = True
        output_text = ""
        tool_calls = None
        
        for chunk in client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                output_text += delta.content
                stream_callback(delta.content)
        
        # Note: streaming doesn't return usage or tool_calls reliably
        return output_text, {}, tool_calls
    
    # Non-streaming path
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
