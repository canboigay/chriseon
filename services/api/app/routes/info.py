from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/info")
def info():
    return {
        "service": "chriseon-api",
        "version": "0.1.0",
    }
