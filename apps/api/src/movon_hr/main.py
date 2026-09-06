from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from movon_hr.core.settings import settings
from movon_hr.modules.api import router

app = FastAPI(title="Teamku API", version="0.1.0", openapi_url="/api/v1/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Demo-User"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
