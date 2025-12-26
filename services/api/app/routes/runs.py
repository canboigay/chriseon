from __future__ import annotations

import json
import uuid
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import joinedload

from app.db import session_scope
from app.events import iter_sse_events, publish_event
from app.models import Artifact, Run, Score
from app.queue import get_queue
from app.schemas import ArtifactOut, RunCreateRequest, RunCreateResponse, RunOut

router = APIRouter()


def _sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.post("/runs", response_model=RunCreateResponse)
def create_run(body: RunCreateRequest):
    with session_scope() as session:
        run = Run(
            status="queued",
            query=body.query,
            header_prompt=body.header_prompt,
            selected_models=body.selected_models,
            output_length=body.output_length,
            stage_prompts=body.stage_prompts,
            budget=body.budget,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    publish_event(str(run.id), "run.queued", {"run_id": str(run.id)})

    q = get_queue("default")
    q.enqueue("worker.jobs.execute_run", str(run.id), body.credential_mode)

    return RunCreateResponse(id=str(run.id), status=run.status)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str):
    try:
        run_uuid = uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid run_id")

    with session_scope() as session:
        run = session.get(Run, run_uuid)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")

        return RunOut(
            id=str(run.id),
            status=run.status,
            query=run.query,
            header_prompt=run.header_prompt,
            selected_models=run.selected_models,
            output_length=run.output_length or "standard",
            stage_prompts=run.stage_prompts or {},
            budget=run.budget,
            total_usage=run.total_usage,
            error=run.error,
        )


@router.get("/runs/{run_id}/artifacts")
def list_artifacts(run_id: str):
    try:
        run_uuid = uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid run_id")

    with session_scope() as session:
        # Use joinedload to avoid N+1 query - fetch artifacts with scores in single query
        artifacts = (
            session.query(Artifact)
            .options(joinedload(Artifact.score))  # Eager load scores
            .filter(Artifact.run_id == run_uuid)
            .order_by(Artifact.pass_index.asc())
            .all()
        )

    return {
        "run_id": run_id,
        "artifacts": [
            ArtifactOut(
                id=str(a.id),
                pass_index=a.pass_index,
                model_id=a.model_id,
                role=a.role,
                output_text=a.output_text,
                error=a.error,
                usage=a.usage,
                score=(
                    {"total": a.score.total, **(a.score.data or {})}
                    if a.score else None
                ),
            ).model_dump()
            for a in artifacts
        ],
    }


@router.get("/runs/{run_id}/events")
def run_events(run_id: str, last_id: str = "0-0"):
    def gen() -> Iterator[str]:
        for event_type, payload, new_last_id in iter_sse_events(run_id, last_id=last_id):
            yield _sse_format(event_type, {"id": new_last_id, **payload})

    return StreamingResponse(gen(), media_type="text/event-stream")
