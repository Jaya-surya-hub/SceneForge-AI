"""FastAPI application factory.

Creates and configures the application with:
- Middleware: CorrelationID, request size limit
- Exception handlers: domain errors → IS-03 schema
- Routers: health, jobs
- Lifespan: logging + storage bucket init
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sceneforge.api.errors import (
    sceneforge_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from sceneforge.api.middleware.correlation import CorrelationIDMiddleware
from sceneforge.api.routes import health as health_router
from sceneforge.api.routes import jobs as jobs_router
from sceneforge.observability.logging import configure_logging, get_logger
from sceneforge.schemas.exceptions import SceneForgeError

_MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run setup on startup and teardown on shutdown."""
    configure_logging()
    log = get_logger(__name__)
    log.info("sceneforge_starting", version=os.getenv("API_VERSION", "0.1.0"))

    # Initialise storage buckets (idempotent) — skip in test environments
    if os.getenv("SKIP_STARTUP_CHECKS", "false").lower() != "true":
        try:
            from sceneforge.storage.client import get_storage_client
            client = get_storage_client()
            client.ensure_buckets()
            log.info("storage_buckets_ready")
        except Exception as exc:
            log.warning("storage_bucket_init_skipped", reason=str(exc))

        # Reconcile any orphaned/stuck jobs left in active states by worker crashes or restarts
        try:
            from sceneforge.jobs.database import get_session
            from sceneforge.jobs.reconciler import reconcile_stale_jobs
            with get_session() as session:
                reconciled = reconcile_stale_jobs(session, stale_threshold_minutes=5)
                if reconciled:
                    log.warning("startup_reconciled_stale_jobs", count=reconciled)
        except Exception as exc:
            log.warning("startup_reconcile_stale_jobs_skipped", reason=str(exc))

    yield

    log.info("sceneforge_shutdown")


def create_app() -> FastAPI:
    """Create and return the configured FastAPI application."""
    app = FastAPI(
        title="SceneForge AI",
        description=(
            "Script and Voiceover to B-roll Video Engine. "
            "IncuBrix Software Engineer Assessment — PS3."
        ),
        version=os.getenv("API_VERSION", "0.1.0"),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # --- Middleware (applied last-in first-out) ---
    cors_env = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    )
    cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIDMiddleware)

    # --- Exception handlers ---
    app.add_exception_handler(SceneForgeError, sceneforge_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # --- Routers ---
    app.include_router(health_router.router)
    app.include_router(jobs_router.router)

    # API v1 prefix (Integration Standard IS-02 compliance)
    app.include_router(health_router.router, prefix="/api/v1")
    app.include_router(jobs_router.router, prefix="/api/v1")

    # Mount filesystem file-serving router when using filesystem storage backend
    import os as _os
    if _os.getenv("STORAGE_BACKEND", "s3").lower() == "filesystem":
        from sceneforge.api.routes import files as files_router
        app.include_router(files_router.router)

    # Mount frontend static files for direct browser access at /
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    public_candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../apps/web/public")),
        "/app/apps/web/public",
    ]
    public_dir = next((p for p in public_candidates if os.path.isdir(p)), None)
    if public_dir:
        index_file = os.path.join(public_dir, "index.html")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            if os.path.isfile(index_file):
                return FileResponse(index_file)
            return JSONResponse({"status": "ok", "app": "SceneForge AI"})

        app.mount("/static", StaticFiles(directory=public_dir), name="static")

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
