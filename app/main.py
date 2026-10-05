from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.routers import analytics, auth, devices, exercises, patterns, sessions

settings = get_settings()

app = FastAPI(title="GymBeam API", version="0.1.0")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

api = APIRouter(prefix="/api/v1")
for module in (auth, exercises, patterns, devices, sessions, analytics):
    api.include_router(module.router)
app.include_router(api)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "environment": settings.environment}
