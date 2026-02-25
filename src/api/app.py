"""FastAPI app factory for read-only trading dashboard endpoints."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import create_router


def create_app(db_path: str = "trading_paper.db") -> FastAPI:
    """Create a FastAPI app with read-only dashboard routes."""
    app = FastAPI(title="Trading Bot Dashboard API", version="0.1.0")
    app.include_router(create_router(db_path))
    return app
