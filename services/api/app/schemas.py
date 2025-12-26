from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Provider = Literal["openai", "anthropic", "gemini", "xai"]
CredentialMode = Literal["byok", "managed", "auto"]
OutputLength = Literal["brief", "standard", "comprehensive"]


class RunCreateRequest(BaseModel):
    query: str = Field(min_length=1)

    header_prompt: dict[str, Any] = Field(default_factory=dict)

    # Which provider:model each stage uses.
    selected_models: dict[str, str] = Field(
        default_factory=lambda: {
            "a": "xai:grok-3",
            "b": "gemini:gemini-2.0-flash",
            "c": "xai:grok-4-0709",
        }
    )

    # Optional user controls
    output_length: OutputLength = "standard"

    # Per-stage prompt additions (appended to Chriseon's built-in prompts)
    stage_prompts: dict[str, str] = Field(default_factory=dict)

    budget: dict[str, Any] = Field(default_factory=dict)

    credential_mode: dict[Provider, CredentialMode] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    id: str
    status: str


class ArtifactOut(BaseModel):
    id: str
    pass_index: int
    model_id: str
    role: str
    output_text: str
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    score: dict[str, Any] | None = None


class RunOut(BaseModel):
    id: str
    status: str
    query: str
    header_prompt: dict[str, Any]
    selected_models: dict[str, str]
    output_length: OutputLength
    stage_prompts: dict[str, str]
    budget: dict[str, Any]
    total_usage: dict[str, Any]
    error: str | None


class ProviderKeyUpsertRequest(BaseModel):
    api_key: str = Field(min_length=10)
    enabled: bool = True
