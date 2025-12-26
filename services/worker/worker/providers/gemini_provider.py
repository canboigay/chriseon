from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types


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
    Generate response with optional tool calling support.
    
    Returns:
        (output_text, usage_dict, tool_calls or None)
    """
    client = genai.Client(api_key=api_key)
    
    # Build full prompt
    full_input = f"{instructions}\n\nUser query:\n{user_input}"
    if tool_context:
        full_input += f"\n\n--- Tool Results from Previous Iteration ---\n{tool_context}"
    
    # Convert OpenAI tool format to Gemini format
    gemini_tools = None
    if tools:
        function_declarations = []
        for t in tools:
            func_def = t["function"]
            # Gemini expects slightly different schema format
            function_declarations.append(
                types.FunctionDeclaration(
                    name=func_def["name"],
                    description=func_def["description"],
                    parameters=func_def["parameters"],
                )
            )
        gemini_tools = types.Tool(function_declarations=function_declarations)
    
    # google-genai expects tools inside GenerateContentConfig (not as a top-level kwarg)
    config = None
    if gemini_tools or max_output_tokens is not None:
        config = types.GenerateContentConfig(
            tools=[gemini_tools] if gemini_tools else None,
            max_output_tokens=int(max_output_tokens) if max_output_tokens is not None else None,
        )

    kwargs = {"model": model, "contents": full_input}
    if config is not None:
        kwargs["config"] = config

    # Enable streaming if callback provided
    if stream_callback:
        output_text = ""
        for chunk in client.models.generate_content_stream(**kwargs):
            if hasattr(chunk, 'text') and chunk.text:
                output_text += chunk.text
                stream_callback(chunk.text)
        return output_text, {}, None
    
    # Non-streaming path
    resp = client.models.generate_content(**kwargs)
    
    # Extract text and tool calls
    text_parts = []
    tool_calls = []
    
    if hasattr(resp, "candidates") and resp.candidates:
        candidate = resp.candidates[0]
        if hasattr(candidate, "content") and candidate.content:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    # Convert proto to dict
                    args_dict = {}
                    if hasattr(fc, "args") and fc.args:
                        args_dict = dict(fc.args)
                    
                    tool_calls.append({
                        "id": f"call_{fc.name}",  # Gemini doesn't provide IDs
                        "name": fc.name,
                        "arguments": args_dict,
                    })
    
    output_text = "".join(text_parts).strip() if text_parts else (resp.text or "").strip()
    
    return output_text, {}, tool_calls if tool_calls else None
