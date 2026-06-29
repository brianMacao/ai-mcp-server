"""FastAPI app factory."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="ai-mcp ui", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.cache = None
    app.state.templates = templates

    from .token_middleware import TokenMiddleware

    app.add_middleware(TokenMiddleware)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    from .routes import (
        dashboard,
        endpoints,
        jobs,
        meta,
        models,
        overrides,
        probes,
    )

    app.include_router(dashboard.router)
    app.include_router(endpoints.router)
    app.include_router(models.router)
    app.include_router(overrides.router)
    app.include_router(probes.router)
    app.include_router(jobs.router)
    app.include_router(meta.router)
    return app
