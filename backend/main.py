"""FastAPI application entrypoint for SourceMD."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import evaluate as evaluate_routes
from backend.api.routes import followup as followup_routes
from backend.api.routes import history as history_routes
from backend.config import get_settings

logger = logging.getLogger(__name__)


def _maybe_ingest() -> None:
    """Run ingestion if the ChromaDB guidelines collection is empty."""
    try:
        from backend.agents.chroma_client import get_guidelines_collection
        collection = get_guidelines_collection()
        count = collection.count()
        if count == 0:
            logger.info("ChromaDB collection is empty — running ingestion...")
            from backend.ingestion.ingest import main as ingest_main
            ingest_main()
            logger.info("Ingestion complete.")
        else:
            logger.info("ChromaDB collection has %d chunks — skipping ingestion.", count)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ingestion check failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan hook — auto-ingest if ChromaDB is empty."""
    await asyncio.get_event_loop().run_in_executor(None, _maybe_ingest)
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
    app.include_router(history_routes.router)
    return app


app = create_app()
