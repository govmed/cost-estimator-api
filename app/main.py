from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db import check_db_connection
from .api.auth import router as auth_router
from .api.projects import router as projects_router

app = FastAPI(
    title="SOW Cost Calculator API",
    version="0.1.0",
    description="Phase 2 backend for the SOW Cost Calculator.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # SPA dev server; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(projects_router)


@app.get("/health", tags=["ops"])
def health():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "version": app.version,
        "environment": settings.environment,
    }
