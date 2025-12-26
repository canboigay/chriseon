from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)

    query: Mapped[str] = mapped_column(Text)
    header_prompt: Mapped[dict] = mapped_column(JSONB, default=dict)
    selected_models: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Run-level controls
    output_length: Mapped[str] = mapped_column(String(16), default="standard")
    stage_prompts: Mapped[dict] = mapped_column(JSONB, default=dict)

    budget: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_usage: Mapped[dict] = mapped_column(JSONB, default=dict)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    artifacts: Mapped[list[Artifact]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"), index=True)

    pass_index: Mapped[int] = mapped_column(Integer, index=True)
    model_id: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))  # draft/refine/synthesis

    input_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_text: Mapped[str] = mapped_column(Text, default="")

    usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run: Mapped[Run] = relationship(back_populates="artifacts")
    score: Mapped["Score"] = relationship(back_populates="artifact", uselist=False)


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id"),
        index=True,
        unique=True,
    )

    # Store raw dimension values and any notes/metadata.
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    total: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    artifact: Mapped[Artifact] = relationship(back_populates="score")


class ProviderKey(Base):
    __tablename__ = "provider_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # For now we run local single-user. Future: scope_id is a UUID for user/org.
    scope: Mapped[str] = mapped_column(String(16), default="user")
    scope_id: Mapped[str] = mapped_column(String(64), default="local")

    provider: Mapped[str] = mapped_column(String(32), index=True)  # openai/anthropic/gemini/xai
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    key_ciphertext: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
