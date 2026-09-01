"""DhanRakshak FastAPI application entry point."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.routers import users, cases, fraud_reports, investigation_notes, audit, ml_analyze
from app.api.routers import auth
from app.database.session import engine
from app.database.base import Base

logger = logging.getLogger(__name__)

# ── Startup / shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (idempotent)
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    os.makedirs(_STORAGE_PATH, exist_ok=True)  # ensure static-files dir is always present
    logger.info("DhanRakshak API started — storage: %s", settings.STORAGE_DIR)
    yield
    logger.info("DhanRakshak API shutting down")

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for DhanRakshak Fraud Investigation Platform — Canara Bank",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict to known origins. Add prod domain via EXTRA_CORS_ORIGINS env var.
_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev
    "http://localhost:3000",   # CRA / Next dev (fallback)
    "http://127.0.0.1:5173",
    *settings.get_allowed_origins(),  # Production/staging URLs from env var
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# ── Routers ───────────────────────────────────────────────────────────────────
_V1 = settings.API_V1_STR
app.include_router(auth.router,                 prefix=f"{_V1}/auth",  tags=["auth"])
app.include_router(users.router,                prefix=f"{_V1}/users",  tags=["users"])
app.include_router(cases.router,                prefix=f"{_V1}/cases",  tags=["cases"])
app.include_router(fraud_reports.router,        prefix=f"{_V1}/reports",tags=["fraud_reports"])
app.include_router(investigation_notes.router,  prefix=f"{_V1}/notes",  tags=["investigation_notes"])
app.include_router(audit.router,                prefix=f"{_V1}/audit",  tags=["audit"])
app.include_router(ml_analyze.router,           prefix="/api/ml",       tags=["ml_pipeline"])

# ── Static storage ────────────────────────────────────────────────────────────
# Resolve once at module level and pre-create the directory so that
# StaticFiles() never crashes on a fresh deploy before lifespan runs.
_STORAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
os.makedirs(_STORAGE_PATH, exist_ok=True)
app.mount("/storage", StaticFiles(directory=_STORAGE_PATH), name="storage")

@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
