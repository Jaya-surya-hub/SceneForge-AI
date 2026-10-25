"""FastAPI Application factory for IncuBrix Signal Room."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from signalroom.api.routes import (
    evidence_router,
    health_router,
    projects_router,
    questions_router,
    runs_router,
)
from signalroom.core.config import settings
from signalroom.core.exceptions import (
    SignalRoomException,
    format_error_response,
    signalroom_exception_handler,
)
from signalroom.core.logging import get_logger, setup_logging
from signalroom.db.session import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    
    # Initialize database tables if in development / test mode
    try:
        init_db()
        logger.info("Database schemas verified.")
    except Exception as e:
        logger.warning(f"Database auto-init deferred or failed: {e}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="The Evidence-First Search & AI Visibility Intelligence Engine",
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    app.add_exception_handler(SignalRoomException, signalroom_exception_handler)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return format_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred.",
            details={"path": request.url.path} if settings.DEBUG else {},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Include Routers
    api_prefix = settings.API_V1_PREFIX
    app.include_router(health_router, prefix=api_prefix)
    app.include_router(projects_router, prefix=api_prefix)
    app.include_router(questions_router, prefix=api_prefix)
    app.include_router(runs_router, prefix=api_prefix)
    app.include_router(evidence_router, prefix=api_prefix)

    @app.get("/", tags=["Root"])
    def root_info():
        return {
            "app": settings.PROJECT_NAME,
            "tagline": settings.TAGLINE,
            "version": settings.VERSION,
            "docs": "/docs",
            "health": f"{api_prefix}/health",
            "environment": settings.ENVIRONMENT,
        }

    return app


app = create_app()
