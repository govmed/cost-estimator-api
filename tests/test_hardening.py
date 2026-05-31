"""
B3 hardening tests — security headers, CORS, startup validation, health endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.config import settings


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Security headers ──────────────────────────────────────────────────────────

def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in r.headers


def test_hsts_not_set_in_dev(client):
    # HSTS is only set in production (requires HTTPS)
    assert settings.is_production is False
    r = client.get("/health")
    assert "Strict-Transport-Security" not in r.headers


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_health_hides_db_details_in_production():
    with patch.object(settings, "is_production", True):
        with patch("app.main.check_db_connection", return_value=True):
            with TestClient(app) as c:
                r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "database" not in body        # hidden in production
    assert "environment" not in body     # hidden in production
    assert "status" in body
    assert "version" in body


def test_health_shows_db_details_in_dev(client):
    with patch("app.main.check_db_connection", return_value=True):
        r = client.get("/health")
    body = r.json()
    assert "database" in body
    assert "environment" in body


# ── CORS ─────────────────────────────────────────────────────────────────────

def test_cors_allows_configured_origin(client):
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    r = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORSMiddleware simply omits the header for disallowed origins
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


# ── Settings validation ────────────────────────────────────────────────────────

def test_validate_production_secrets_passes_in_dev():
    # Should not raise in development with default secrets
    settings.validate_production_secrets()  # no exception


def test_validate_production_secrets_blocks_default_secret():
    with patch.object(settings, "environment", "production"):
        with patch.object(settings, "secret_key", "dev-secret-change-in-production"):
            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                settings.validate_production_secrets()


def test_validate_production_secrets_blocks_dev_db():
    with patch.object(settings, "environment", "production"):
        with patch.object(settings, "secret_key", "real-secret"):
            with patch.object(settings, "database_url", "postgresql://user:devpassword@host/db"):
                with pytest.raises(RuntimeError, match="DATABASE_URL"):
                    settings.validate_production_secrets()


def test_validate_production_secrets_blocks_missing_oidc_issuer():
    with patch.object(settings, "environment", "production"):
        with patch.object(settings, "secret_key", "real-secret"):
            with patch.object(settings, "database_url", "postgresql://user:realpass@host/db"):
                with patch.object(settings, "auth_mode", "oidc"):
                    with patch.object(settings, "authentik_issuer", ""):
                        with pytest.raises(RuntimeError, match="AUTHENTIK_ISSUER"):
                            settings.validate_production_secrets()


# ── Rate limiting ─────────────────────────────────────────────────────────────

def test_rate_limit_config_is_set():
    # Confirm rate limits are configured and non-empty
    assert settings.rate_limit_auth
    assert settings.rate_limit_default
    assert "/" in settings.rate_limit_auth     # e.g. "10/minute"


# ── Origins parsing ────────────────────────────────────────────────────────────

def test_origins_property_splits_correctly():
    with patch.object(settings, "allowed_origins", "http://a.com , https://b.com"):
        assert settings.origins == ["http://a.com", "https://b.com"]


def test_origins_property_single():
    with patch.object(settings, "allowed_origins", "http://localhost:5173"):
        assert settings.origins == ["http://localhost:5173"]
