from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from research_lab.api import router as api_router
from research_lab.config import get_settings
from research_lab.db import engine
from research_lab.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI & Management of Technology Research Intelligence.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_read_only_mode(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    safe_post_paths = {"/api/v1/chat"}
    configured_public_hosts = {
        host.strip().lower()
        for host in settings.public_api_hosts.split(",")
        if host.strip()
    }
    request_host = (request.url.hostname or "").lower()
    public_read_only = (
        settings.read_only_mode
        or settings.app_environment.lower() == "production"
        or request_host in configured_public_hosts
    )
    if (
        public_read_only
        and request.url.path.startswith("/api/v1/")
        and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
        and not (request.method.upper() == "POST" and request.url.path in safe_post_paths)
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": "This deployment is a public read-only research demo. Mutations are disabled.",
            },
        )
    return await call_next(request)

app.include_router(api_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    database = "unavailable"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"

    return HealthResponse(status="ok", service="api", database=database)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }

