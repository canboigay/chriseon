from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic


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
    client = Anthropic(api_key=api_key)
    
    # Build full prompt with tool context
    full_input = f"{instructions}\n\nUser query:\n{user_input}"
    if tool_context:
        full_input += f"\n\n--- Tool Results from Previous Iteration ---\n{tool_context}"
    
    # Convert OpenAI tool format to Anthropic format
    anthropic_tools = None
    if tools:
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]
    
    kwargs = {
        "model": model,
        "max_tokens": int(max_output_tokens or 4096),
        "messages": [{"role": "user", "content": full_input}],
    }
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools
    
    msg = client.messages.create(**kwargs)
    
    # Extract text and tool calls
    text_parts = []
    tool_calls = []
    
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
        elif getattr(block, "type", None) == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "arguments": block.input,
            })
    
    usage: dict[str, Any] = {}
    if getattr(msg, "usage", None) is not None:
        usage = getattr(msg.usage, "model_dump", lambda: {})() or {}
    
    return (
        "".join(text_parts).strip(),
        usage,
        tool_calls if tool_calls else None,
    )
