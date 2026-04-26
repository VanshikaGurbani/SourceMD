"""FastAPI application entrypoint for SourceMD."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import evaluate as evaluate_routes
from backend.api.routes import followup as followup_routes
from backend.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan hook."""
    yield


def create_app() -> FastAPI:
    """Construct and configure the FastAPI app."""
    settings = get_settings()
    app = FastAPI(
        title="SourceMD",
        description="Trust scoring for AI-generated medical answers.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Lightweight liveness probe used by docker-compose and CI."""
        return {"status": "ok"}

    app.include_router(evaluate_routes.router)
    app.include_router(followup_routes.router)
    return app


app = create_app()
