from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .config import settings
from .db import check_db_connection
from .middleware import SecurityHeadersMiddleware
from .api.auth import router as auth_router
from .api.projects import router as projects_router
from .api.shares import router as shares_router
from .api.audit import router as audit_router
from .api.transitions import router as transitions_router
from .api.users import router as users_router
from .api.pricing import router as pricing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast in production if secrets are defaults.
    settings.validate_production_secrets()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])

app = FastAPI(
    title="SOW Cost Calculator API",
    version="0.1.0",
    description="Phase 2 backend for the SOW Cost Calculator.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost first) ───────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(shares_router)
app.include_router(audit_router)
app.include_router(transitions_router)
app.include_router(users_router)
app.include_router(pricing_router)


# ── Ops ───────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
def health():
    db_ok = check_db_connection()
    body: dict = {"status": "ok" if db_ok else "degraded", "version": app.version}
    # Expose DB details only in non-production environments.
    if not settings.is_production:
        body["database"] = "connected" if db_ok else "unreachable"
        body["environment"] = settings.environment
        body["auth_mode"] = settings.auth_mode
    return body
