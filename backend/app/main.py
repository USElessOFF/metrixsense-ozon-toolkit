"""MetrixSense"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import PROJECT_ROOT, settings
from backend.app.lifespan import lifespan
from backend.app.logger import setup_logging
from backend.app.routers import (
    get_calculator_router,
    get_auth_router,
    get_health_router,
    get_onboarding_router,
    get_reports_router,
    get_secrets_router,
    get_settings_router,
)

setup_logging(settings)

logger = structlog.get_logger(__name__)


_WEB_DIR = PROJECT_ROOT.parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(
        title="MetrixSense",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(get_calculator_router())
    app.include_router(get_auth_router())
    app.include_router(get_health_router())
    app.include_router(get_onboarding_router())
    app.include_router(get_settings_router())
    app.include_router(get_secrets_router())
    app.include_router(get_reports_router())

    if _WEB_DIR.is_dir() and (_WEB_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
        logger.info("[MetrixSense] Serving web UI", path=str(_WEB_DIR))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
