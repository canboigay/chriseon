from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models_config import (
    DEFAULT_SELECTIONS,
    get_all_models,
    get_model_by_id,
    get_models_for_position,
    get_positions,
)

router = APIRouter()


@router.get("/models")
def list_models(position: str | None = Query(None)):
    """List available models.

    If position is provided (a, b, or c), returns only models recommended for that position.
    Otherwise returns all models.
    """
    models = get_models_for_position(position) if position else get_all_models()
    return {"models": models, "count": len(models)}


@router.get("/models/positions/list")
def list_positions():
    """Get information about the positions in the refinement pipeline."""
    return {"positions": get_positions(), "defaults": DEFAULT_SELECTIONS}


@router.get("/models/{model_id:path}")
def get_model(model_id: str):
    """Get details for a specific model by ID (format: provider:model)."""
    model = get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model
