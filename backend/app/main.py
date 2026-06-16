import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

from app.api.routers import auth, users, cases, fraud_reports, investigation_notes, audit

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for DhanRakshak Fraud Investigation Platform",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(cases.router, prefix=f"{settings.API_V1_STR}/cases", tags=["cases"])
app.include_router(fraud_reports.router, prefix=f"{settings.API_V1_STR}/reports", tags=["fraud_reports"])
app.include_router(investigation_notes.router, prefix=f"{settings.API_V1_STR}/notes", tags=["investigation_notes"])
app.include_router(audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["audit"])

os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

@app.get("/")
def root():
    return {"message": "Welcome to DhanRakshak API"}
