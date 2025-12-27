from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
import multiprocessing as mp
import os

from worker.context import extract_and_fetch_context
from worker.db import session_scope
from worker.events import publish_event
from worker.key_resolver import resolve_key
from worker.models import Artifact, Run, Score
from worker.scoring import compute_score

logger = logging.getLogger(__name__)


def _parse_model_ref(model_ref: str) -> tuple[str, str]:
    # expected: "provider:model"
    if ":" not in model_ref:
        raise ValueError("invalid model ref")
    provider, model = model_ref.split(":", 1)
    return provider, model


def _provider_generate(
    provider: str,
    model: str,
    instructions: str,
    user_input: str,
    api_key: str,
    tools: list | None = None,
    tool_context: str | None = None,
    max_output_tokens: int | None = None,
    stream_callback=None,
):
    """Core provider generation logic (no multiprocessing).

    Returns (text, usage, tool_calls).
    """
    if provider == "openai":
        from worker.providers import openai_provider

        return openai_provider.generate(
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
            stream_callback=stream_callback,
        )
    if provider == "anthropic":
        from worker.providers import anthropic_provider

        return anthropic_provider.generate(
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
            stream_callback=stream_callback,
        )
    if provider == "gemini":
        from worker.providers import gemini_provider

        return gemini_provider.generate(
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
            stream_callback=stream_callback,
        )
    if provider == "xai":
        from worker.providers import xai_provider

        return xai_provider.generate(
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
            stream_callback=stream_callback,
        )
    if provider == "deepseek":
        from worker.providers import deepseek_provider

        return deepseek_provider.generate(
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
            stream_callback=stream_callback,
        )

    raise ValueError(f"unsupported provider: {provider}")


# Feature flag: allow disabling subprocess isolation if it is unstable on a given env.
# Default to using subprocess isolation because running provider SDKs inside the RQ work-horse
# can segfault on macOS.
_DISABLE_PROVIDER_SUBPROCESS = os.getenv("CHRISEON_DISABLE_PROVIDER_SUBPROCESS", "0") == "1"


def _provider_generate_subprocess(
    q: "mp.Queue",
    provider: str,
    model: str,
    instructions: str,
    user_input: str,
    api_key: str,
    tools: list | None = None,
    tool_context: str | None = None,
    max_output_tokens: int | None = None,
):
    """Run provider generation in a separate process.

    This protects the main RQ work-horse process from segfaults in provider SDKs
    (common on macOS with certain binary deps).
    """
    try:
        text, usage, tool_calls = _provider_generate(
            provider,
            model,
            instructions,
            user_input,
            api_key,
            tools=tools,
            tool_context=tool_context,
            max_output_tokens=max_output_tokens,
        )
        q.put({"ok": True, "text": text, "usage": usage or {}, "tool_calls": tool_calls})
    except Exception as e:
        q.put({"ok": False, "error": str(e)})


def _generate_with_timeout(
    provider: str,
    model: str,
    instructions: str,
    user_input: str,
    api_key: str,
    timeout_s: int,
    tools: list | None = None,
    tool_context: str | None = None,
    max_output_tokens: int | None = None,
    stream_callback=None,
) -> tuple[str, dict, str | None, list | None]:
    """Return (text, usage, error, tool_calls).

    If subprocess isolation is disabled, run inline in the current process.
    """

    # Inline path: simpler and more robust on some environments.
    if _DISABLE_PROVIDER_SUBPROCESS:
        try:
            text, usage, tool_calls = _provider_generate(
                provider,
                model,
                instructions,
                user_input,
                api_key,
                tools=tools,
                tool_context=tool_context,
                max_output_tokens=max_output_tokens,
                stream_callback=stream_callback,
            )
            return str(text or ""), dict(usage or {}), None, tool_calls
        except Exception as e:
            logger.error(
                "Provider error in inline mode",
                extra={"provider": provider, "model": model, "exception": str(e)},
                exc_info=True,
            )
            return "", {}, str(e), None

    # Subprocess path (original behavior)
    ctx = mp.get_context("spawn")
    q: "mp.Queue" = ctx.Queue(maxsize=1)
    p = ctx.Process(
        target=_provider_generate_subprocess,
        args=(
            q,
            provider,
            model,
            instructions,
            user_input,
            api_key,
            tools,
            tool_context,
            max_output_tokens,
        ),
        daemon=True,
    )
    p.start()
    p.join(timeout=timeout_s)

    if p.is_alive():
        p.terminate()
        p.join(timeout=2)
        return "", {}, f"timeout after {timeout_s}s", None

    # Process exited. If it crashed before writing to queue, treat as crash.
    try:
        res = q.get_nowait()
    except Exception as e:
        code = p.exitcode
        logger.error(
            "Provider process crashed",
            extra={
                "provider": provider,
                "model": model,
                "exitcode": code,
                "exception": str(e),
            },
            exc_info=True,
        )
        return "", {}, f"provider process exited unexpectedly (exitcode={code})", None

    if res.get("ok"):
        return (
            str(res.get("text") or ""),
            dict(res.get("usage") or {}),
            None,
            res.get("tool_calls"),
        )

    return "", {}, str(res.get("error") or "unknown error"), None


def execute_run(run_id: str, credential_mode: dict | None = None):
    credential_mode = credential_mode or {}

    try:
        run_uuid = uuid.UUID(run_id)
    except Exception:
        return

    publish_event(run_id, "run.started", {"run_id": run_id})

    with session_scope() as session:
        run = session.get(Run, run_uuid)
        if run is None:
            publish_event(run_id, "run.error", {"run_id": run_id, "error": "run not found"})
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        session.commit()

        # 1) Fetch external context if URLs are present
        augmented_query = run.query
        try:
            augmented_query, sources = extract_and_fetch_context(run.query)
            if sources:
                publish_event(run_id, "run.context_fetched", {"sources": sources})
        except Exception as e:
            print(f"Context fetch failed: {e}")
            # fall back to original query on error

        instructions = run.header_prompt.get("instructions") or "You are a precise, professional assistant."

        selected = run.selected_models or {}
        stage_prompts = run.stage_prompts or {}
        output_length = (run.output_length or "standard").strip().lower()

        # Output length control (bounded)
        length_hint_map = {
            "brief": "Keep it brief: ~5–8 sentences. Prioritize the highest-signal points.",
            "standard": "Standard length: clear, complete, and structured without being exhaustive.",
            "comprehensive": "Comprehensive (bounded): aim for ~800–1200 words with clear headings and actionable detail.",
        }
        length_hint = length_hint_map.get(output_length, length_hint_map["standard"])

        # Best-effort max output token caps (provider dependent)
        max_tokens_map = {
            "brief": 350,
            "standard": 900,
            "comprehensive": 1600,
        }
        max_output_tokens = max_tokens_map.get(output_length, max_tokens_map["standard"])

        # Sequential refinement pipeline:
        # Pass 1 (A): Draft - initial response
        # Pass 2 (B): Refine - analyze and improve A's output
        # Pass 3 (C): Validate - check B's output against original prompt, produce final
        
        # Track previous artifacts for chaining
        artifact_a: Artifact | None = None
        artifact_b: Artifact | None = None
        
        items = [
            (1, "a", "draft", selected.get("a")),
            (2, "b", "refine", selected.get("b")),
            (3, "c", "synthesis", selected.get("c")),
        ]

        for pass_index, slot, role, model_ref in items:
            if not model_ref:
                continue

            provider, model = _parse_model_ref(model_ref)
            provider = provider.strip().lower()

            requested_mode = credential_mode.get(provider)
            mode_used, api_key = resolve_key(session, provider, requested_mode)

            publish_event(
                run_id,
                "artifact.planned",
                {
                    "run_id": run_id,
                    "pass_index": pass_index,
                    "slot": slot,
                    "provider": provider,
                    "model": model,
                    "credential_mode": mode_used,
                },
            )

            art = Artifact(
                run_id=run_uuid,
                pass_index=pass_index,
                model_id=f"{provider}:{model}",
                role=role,
                input_refs={"slot": slot},
                output_text="",
                usage={},
            )
            session.add(art)
            session.commit()
            session.refresh(art)

            if not api_key:
                art.error = f"No API key available for provider={provider} (mode={mode_used})"
                session.commit()
                publish_event(
                    run_id,
                    "artifact.error",
                    {"run_id": run_id, "artifact_id": str(art.id), "error": art.error},
                )
                continue

            publish_event(
                run_id,
                "artifact.started",
                {
                    "run_id": run_id,
                    "artifact_id": str(art.id),
                    "pass_index": pass_index,
                    "model_id": art.model_id,
                },
            )

            started = time.monotonic()
            try:
                # Import tools for this pass
                from worker.tools import AVAILABLE_TOOLS, execute_tool, format_tool_result
                
                # Build the prompt based on role in pipeline
                if role == "draft":
                    # Pass 1: Initial draft
                    base_prompt = augmented_query
                    system_instructions = (
                        f"{instructions}\n\n{length_hint}\n\n"
                        "You have access to tools that can help you research and gather data. "
                        "Use them when needed to provide accurate responses."
                    )
                elif role == "refine":
                    # Pass 2: Refine the draft
                    if artifact_a and artifact_a.output_text:
                        base_prompt = (
                            f"Original request: {run.query}\n\n"
                            f"Initial draft to improve:\n{artifact_a.output_text}\n\n"
                            "Please analyze the above draft and provide an improved, refined version. "
                            "Address gaps, improve clarity, and ensure correctness."
                        )
                    else:
                        base_prompt = augmented_query
                    system_instructions = f"{instructions}\n\n{length_hint}"
                elif role == "synthesis":
                    # Pass 3: Validate and create final version
                    if artifact_b and artifact_b.output_text:
                        base_prompt = (
                            f"Original request: {run.query}\n\n"
                            f"Refined response to validate:\n{artifact_b.output_text}\n\n"
                            "Please review the above response against the original request. "
                            "Verify it is accurate, complete, and well-structured. Provide the final, polished version."
                        )
                    else:
                        base_prompt = augmented_query
                    system_instructions = f"{instructions}\n\n{length_hint}"
                else:
                    base_prompt = augmented_query
                    system_instructions = f"{instructions}\n\n{length_hint}"

                # Append per-stage user prompt additions (non-destructive)
                extra = (stage_prompts.get(slot) or "").strip()
                if extra:
                    # Soft cap to avoid runaway prompts
                    extra = extra[:4000]
                    base_prompt = (
                        f"{base_prompt}\n\n"
                        f"--- Additional instructions for stage {slot.upper()} (append-only) ---\n"
                        f"{extra}\n"
                        f"--- End additional instructions ---"
                    )
                
                # Tool calling loop: Allow up to 3 iterations for tool use
                max_tool_iterations = 3
                current_prompt = base_prompt
                tool_context_accumulated = ""
                combined_usage = {}
                
                # Create streaming callback to publish chunks and track progress
                streaming_state = {"total_chunks": 0, "approx_tokens": 0}
                
                def stream_chunk(chunk: str):
                    streaming_state["total_chunks"] += 1
                    # Rough approximation: ~4 chars per token
                    streaming_state["approx_tokens"] = len("".join([chunk])) // 4
                    
                    publish_event(
                        run_id,
                        "artifact.chunk",
                        {
                            "run_id": run_id,
                            "artifact_id": str(art.id),
                            "pass_index": pass_index,
                            "chunk": chunk,
                        },
                    )
                    
                    # Publish progress update every 10 chunks
                    if streaming_state["total_chunks"] % 10 == 0:
                        publish_event(
                            run_id,
                            "artifact.progress",
                            {
                                "run_id": run_id,
                                "artifact_id": str(art.id),
                                "pass_index": pass_index,
                                "chunks_received": streaming_state["total_chunks"],
                                "approx_tokens": streaming_state["approx_tokens"],
                            },
                        )
                
                for iteration in range(max_tool_iterations):
                    # Only stream on first iteration (subsequent iterations are tool calls)
                    callback = stream_chunk if iteration == 0 else None
                    
                    text, usage, gen_err, tool_calls = _generate_with_timeout(
                        provider=provider,
                        model=model,
                        instructions=system_instructions,
                        user_input=current_prompt,
                        api_key=api_key,
                        timeout_s=45,
                        tools=AVAILABLE_TOOLS,
                        tool_context=tool_context_accumulated if tool_context_accumulated else None,
                        max_output_tokens=max_output_tokens,
                        stream_callback=callback,
                    )
                    
                    # Accumulate usage
                    if usage:
                        for k, v in usage.items():
                            combined_usage[k] = combined_usage.get(k, 0) + v
                    
                    if gen_err:
                        raise RuntimeError(gen_err)
                    
                    # If no tool calls, we're done
                    if not tool_calls:
                        break
                    
                    # Execute tools and accumulate results
                    tool_results = []
                    for tc in tool_calls:
                        tool_name = tc["name"]
                        tool_args = tc["arguments"]
                        
                        logger.info(
                            f"Executing tool: {tool_name}({tool_args})",
                            extra={"run_id": run_id, "artifact_id": str(art.id), "iteration": iteration}
                        )
                        
                        result = execute_tool(tool_name, tool_args)
                        formatted = format_tool_result(tool_name, result)
                        tool_results.append(formatted)
                    
                    # Build tool context for next iteration
                    new_context = "\n\n".join(tool_results)
                    tool_context_accumulated += f"\n\n{new_context}" if tool_context_accumulated else new_context
                    
                    # Model should continue with tool results
                    # Keep the same base prompt but the provider will inject tool context
                    # The final text from this iteration becomes the response if no more tool calls
                
                # Use the final text and combined usage
                usage = combined_usage

                art.output_text = text
                art.usage = usage or {}
                art.latency_ms = int((time.monotonic() - started) * 1000)
                session.commit()

                publish_event(
                    run_id,
                    "artifact.created",
                    {
                        "run_id": run_id,
                        "artifact_id": str(art.id),
                        "pass_index": pass_index,
                        "model_id": art.model_id,
                        "latency_ms": art.latency_ms,
                        "credential_mode": mode_used,
                        "output_tokens": usage.get("output_tokens", 0) if usage else 0,
                        "input_tokens": usage.get("input_tokens", 0) if usage else 0,
                    },
                )

                publish_event(
                    run_id,
                    "score.started",
                    {"run_id": run_id, "artifact_id": str(art.id), "pass_index": pass_index},
                )

                score_res = compute_score(instructions=instructions, output_text=art.output_text)
                score = Score(
                    run_id=run_uuid,
                    artifact_id=art.id,
                    data=score_res.data,
                    total=score_res.total,
                )
                session.add(score)
                session.commit()

                publish_event(
                    run_id,
                    "score.created",
                    {
                        "run_id": run_id,
                        "artifact_id": str(art.id),
                        "pass_index": pass_index,
                        "total": score_res.total,
                        "data": score_res.data,
                    },
                )
            except Exception as e:
                art.error = str(e)
                art.latency_ms = int((time.monotonic() - started) * 1000)
                session.commit()
                publish_event(
                    run_id,
                    "artifact.error",
                    {"run_id": run_id, "artifact_id": str(art.id), "error": art.error},
                )
            
            # Store artifact for next pass in chain
            if role == "draft":
                artifact_a = art
            elif role == "refine":
                artifact_b = art

        run.status = "completed"
        run.ended_at = datetime.now(timezone.utc)
        session.commit()

    publish_event(run_id, "run.completed", {"run_id": run_id})
