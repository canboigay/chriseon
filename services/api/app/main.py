from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_engine
from app.models import Base
from app.routes.health import router as health_router
from app.routes.info import router as info_router
from app.routes.models import router as models_router
from app.routes.osint import router as osint_router
from app.routes.runs import router as runs_router
from app.routes.settings import router as settings_router


def create_app() -> FastAPI:
    app = FastAPI(title="chriseon-api")

    # CORS: Allow localhost for dev and Render URLs for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.onrender\.com$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # MVP: create tables automatically for local dev.
    Base.metadata.create_all(get_engine())

    app.include_router(health_router)
    app.include_router(info_router, prefix="/v1")
    app.include_router(models_router, prefix="/v1")
    app.include_router(osint_router, prefix="/v1")
    app.include_router(settings_router, prefix="/v1")
    app.include_router(runs_router, prefix="/v1")

    return app


app = create_app()
