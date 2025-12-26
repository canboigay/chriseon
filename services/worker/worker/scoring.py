from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from worker.key_resolver import resolve_key
from worker.providers import xai_provider

logger = logging.getLogger(__name__)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


@dataclass(frozen=True)
class ScoreResult:
    data: dict
    total: float


def compute_score(*, instructions: str, output_text: str, session=None) -> ScoreResult:
    """Compute score using LLM-as-judge (Grok 3 Mini)."""
    text = (output_text or "").strip()
    if not text:
        return ScoreResult(data={"dimensions": {}, "notes": ["empty output"]}, total=0.0)

    # Resolve key for the judge
    # We use 'auto' mode; if session provided, we can look up BYOK, otherwise managed.
    # For simplicity here we rely on managed or env var if session is missing.
    # Ideally pass session from caller, but for now we'll assume managed/env works.
    try:
        from worker.settings import get_settings
        settings = get_settings()
        api_key = settings.xai_api_key
        
        if not api_key:
            # Fallback to heuristic if no key
            return _compute_heuristic_score(instructions, text)

        judge_prompt = f"""You are an impartial expert evaluator.
        
        Analyze the following AI response against the given instructions.
        
        INSTRUCTIONS:
        {instructions}
        
        AI RESPONSE:
        {text}
        
        Score it on these 4 dimensions (0.0 to 1.0):
        1. alignment (Did it follow instructions?)
        2. completeness (Is it thorough enough?)
        3. quality (Is the writing clear and professional?)
        4. accuracy (Does it seem logically sound/factual?)
        
        Return STRICT JSON only:
        {{
          "alignment": 0.8,
          "completeness": 0.7,
          "quality": 0.9,
          "accuracy": 0.8,
          "critique": "Short explanation of the score."
        }}
        """

        out_text, _, _ = xai_provider.generate(
            model="grok-3-mini",  # Cheap, fast judge
            instructions="You are a scoring system that outputs JSON only.",
            user_input=judge_prompt,
            api_key=api_key,
        )

        # Parse JSON
        start = out_text.find("{")
        end = out_text.rfind("}")
        if start != -1 and end != -1:
            json_str = out_text[start : end + 1]
            scores = json.loads(json_str)
            
            # Weighted total
            weights = {"alignment": 0.35, "accuracy": 0.35, "quality": 0.2, "completeness": 0.1}
            total = 0.0
            
            dim_data = {}
            for k in weights:
                val = _clamp01(float(scores.get(k, 0)))
                dim_data[k] = val
                total += val * weights[k]

            return ScoreResult(
                data={
                    "dimensions": dim_data,
                    "notes": [scores.get("critique", "")],
                    "meta": {"words": len(text.split())}
                },
                total=_clamp01(total)
            )

    except Exception as e:
        logger.error(f"LLM scoring failed: {e}")
        return _compute_heuristic_score(instructions, text)

    return _compute_heuristic_score(instructions, text)


def _compute_heuristic_score(instructions: str, text: str) -> ScoreResult:
    """Fallback heuristic scoring."""
    words = len(text.split())
    completeness = _clamp01(words / 150.0)
    alignment = 0.5
    if "brief" in instructions.lower() and words < 100:
        alignment += 0.3
    
    return ScoreResult(
        data={
            "dimensions": {
                "alignment": alignment,
                "completeness": completeness,
                "quality": 0.5,
                "accuracy": None
            },
            "meta": {"words": words},
            "notes": ["Scored via heuristic (judge unavailable)"]
        },
        total=0.5
    )
