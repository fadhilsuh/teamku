import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from movon_hr.core import persistence
from movon_hr.core.settings import settings
from movon_hr.core.tenancy import iter_stores
from movon_hr.modules.api import bind_from_token, reset_demo_store, router


def _header_map(scope: dict) -> dict[str, str]:
    return {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}


def _cookie_token(cookie_header: str) -> str | None:
    prefix = f"{settings.session_cookie_name}="
    for part in cookie_header.split(";"):
        item = part.strip()
        if item.startswith(prefix):
            return item[len(prefix):]
    return None


class TenantScopeMiddleware:
    """Bind tenant from cookie/header in the same context as the request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = _header_map(scope)
            bind_from_token(headers.get("x-demo-user") or _cookie_token(headers.get("cookie", "")))
        await self.app(scope, receive, send)

logger = logging.getLogger("movon_hr.persistence")

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if persistence.is_enabled():
        await persistence.init_db()
        loaded = await persistence.load_store()
        if not loaded:
            # Fresh database: seed the demo data and persist it so subsequent
            # restarts reload the real, accumulated state.
            reset_demo_store()
            await persistence.save_store(iter_stores()[0])
        logger.info("PostgreSQL persistence active (loaded=%s)", loaded)
    else:
        logger.info("Persistence disabled; using in-memory demo store")
    yield
    if persistence.is_enabled():
        await persistence.dispose()


app = FastAPI(
    title="Teamku API",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(TenantScopeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Demo-User"],
)


@app.middleware("http")
async def persist_after_mutation(request: Request, call_next):
    response = await call_next(request)
    if (
        persistence.is_enabled()
        and request.method in MUTATING_METHODS
        and response.status_code < 500
    ):
        try:
            for tenant_store in iter_stores():
                await persistence.save_store(tenant_store)
        except Exception:
            # Never fail a request because of a persistence hiccup.
            logger.exception(
                "Failed to persist store after %s %s", request.method, request.url.path
            )
    return response


app.include_router(router, prefix="/api/v1")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
