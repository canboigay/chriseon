"""
Model configuration for Chriseon

Defines available models for each position in the sequential refinement pipeline.
Position A (Draft), Position B (Refine), Position C (Synthesis/Validation)
"""

from typing import TypedDict


class ModelInfo(TypedDict):
    """Information about a model"""
    id: str  # provider:model format
    name: str  # Display name
    provider: str
    description: str
    supports_tools: bool  # Whether this model supports function calling
    recommended_for: list[str]  # Which positions it's recommended for


# Available models across all providers
AVAILABLE_MODELS: list[ModelInfo] = [
    # OpenAI Models
    {
        "id": "openai:gpt-4o",
        "name": "GPT-4o",
        "provider": "openai",
        "description": "Latest GPT-4 Omni model with vision and tool support",
        "supports_tools": True,
        "recommended_for": ["draft", "refine", "synthesis"],
    },
    {
        "id": "openai:gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "openai",
        "description": "Faster, more affordable GPT-4o model",
        "supports_tools": True,
        "recommended_for": ["draft", "refine", "synthesis"],
    },
    {
        "id": "openai:gpt-4-turbo",
        "name": "GPT-4 Turbo",
        "provider": "openai",
        "description": "High-capability GPT-4 model with extended context",
        "supports_tools": True,
        "recommended_for": ["refine", "synthesis"],
    },
    {
        "id": "openai:gpt-3.5-turbo",
        "name": "GPT-3.5 Turbo",
        "provider": "openai",
        "description": "Fast and efficient model for simpler tasks",
        "supports_tools": True,
        "recommended_for": ["draft"],
    },
    
    # Anthropic Models
    {
        "id": "anthropic:claude-3-5-sonnet-latest",
        "name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "description": "Best Claude model for coding, analysis, and complex tasks",
        "supports_tools": True,
        "recommended_for": ["refine", "synthesis"],
    },
    {
        "id": "anthropic:claude-3-5-haiku-latest",
        "name": "Claude 3.5 Haiku",
        "provider": "anthropic",
        "description": "Fast, affordable Claude model",
        "supports_tools": True,
        "recommended_for": ["draft"],
    },
    {
        "id": "anthropic:claude-3-opus-latest",
        "name": "Claude 3 Opus",
        "provider": "anthropic",
        "description": "Most powerful Claude 3 model for complex reasoning",
        "supports_tools": True,
        "recommended_for": ["synthesis"],
    },
    
    # Google Gemini Models
    {
        "id": "gemini:gemini-2.0-flash-exp",
        "name": "Gemini 2.0 Flash",
        "provider": "gemini",
        "description": "Latest fast Gemini model with multimodal capabilities",
        "supports_tools": True,
        "recommended_for": ["draft", "refine", "synthesis"],
    },
    {
        "id": "gemini:gemini-1.5-pro-latest",
        "name": "Gemini 1.5 Pro",
        "provider": "gemini",
        "description": "Advanced Gemini model with 2M token context",
        "supports_tools": True,
        "recommended_for": ["refine", "synthesis"],
    },
    {
        "id": "gemini:gemini-1.5-flash-latest",
        "name": "Gemini 1.5 Flash",
        "provider": "gemini",
        "description": "Fast and efficient Gemini model",
        "supports_tools": True,
        "recommended_for": ["draft"],
    },
    
    # xAI Models
    {
        "id": "xai:grok-4-fast-non-reasoning",
        "name": "Grok 4 Fast",
        "provider": "xai",
        "description": "Fastest Grok 4 model for quick responses",
        "supports_tools": False,
        "recommended_for": ["draft"],
    },
    {
        "id": "xai:grok-4-0709",
        "name": "Grok 4",
        "provider": "xai",
        "description": "Advanced Grok 4 model with enhanced capabilities",
        "supports_tools": False,
        "recommended_for": ["refine", "synthesis"],
    },
    {
        "id": "xai:grok-3",
        "name": "Grok 3",
        "provider": "xai",
        "description": "Latest Grok 3 model with real-time knowledge",
        "supports_tools": False,
        "recommended_for": ["draft", "refine"],
    },
    {
        "id": "xai:grok-3-mini",
        "name": "Grok 3 Mini",
        "provider": "xai",
        "description": "Compact, efficient Grok 3 model",
        "supports_tools": False,
        "recommended_for": ["draft"],
    },
    
    # DeepSeek Models
    {
        "id": "deepseek:deepseek-chat",
        "name": "DeepSeek Chat",
        "provider": "deepseek",
        "description": "DeepSeek's main chat model, cost-effective and capable",
        "supports_tools": True,
        "recommended_for": ["draft", "refine", "synthesis"],
    },
    {
        "id": "deepseek:deepseek-reasoner",
        "name": "DeepSeek Reasoner",
        "provider": "deepseek",
        "description": "Advanced reasoning model with chain-of-thought capabilities",
        "supports_tools": True,
        "recommended_for": ["refine", "synthesis"],
    },
]


# Position/Role definitions
POSITIONS = [
    {
        "slot": "a",
        "role": "draft",
        "name": "Position A (Draft)",
        "description": "Creates the initial response to the query. Should be fast and comprehensive.",
    },
    {
        "slot": "b",
        "role": "refine",
        "name": "Position B (Refine)",
        "description": "Analyzes Position A's output and produces an improved, refined version.",
    },
    {
        "slot": "c",
        "role": "synthesis",
        "name": "Position C (Validate)",
        "description": "Validates Position B's output against the original query and produces the final response.",
    },
]


# Default model selections
DEFAULT_SELECTIONS = {
    "a": "xai:grok-3",
    "b": "deepseek:deepseek-chat",
    "c": "xai:grok-4-0709",
}


def get_models_for_position(position: str) -> list[ModelInfo]:
    """Get models recommended for a specific position"""
    role_map = {
        "a": "draft",
        "b": "refine",
        "c": "synthesis",
    }
    role = role_map.get(position, "")
    
    # Filter models recommended for this role
    recommended = [m for m in AVAILABLE_MODELS if role in m["recommended_for"]]
    
    # If no specific recommendations, return all models
    if not recommended:
        return AVAILABLE_MODELS
    
    return recommended


def get_all_models() -> list[ModelInfo]:
    """Get all available models"""
    return AVAILABLE_MODELS


def get_positions() -> list[dict]:
    """Get position definitions"""
    return POSITIONS


def get_model_by_id(model_id: str) -> ModelInfo | None:
    """Get model info by ID"""
    for model in AVAILABLE_MODELS:
        if model["id"] == model_id:
            return model
    return None
