"""
OIDC token validation backend for Authentik.

When AUTH_MODE=oidc, get_current_user() uses this instead of the
standalone JWT validator. It:
  1. Fetches the JWKS from Authentik's discovery endpoint (cached)
  2. Validates the Bearer token signature and claims
  3. Upserts the user into the local DB using sub + email from the token
     so the rest of the app (project ownership, audit) works unchanged

The JWKS is fetched once at startup and cached. Call refresh_jwks()
to force a reload (e.g. after Authentik key rotation).
"""

import httpx
from functools import lru_cache
from jose import JWTError, jwt as jose_jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.auth.password import hash_password


@lru_cache(maxsize=1)
def _fetch_jwks() -> dict:
    discovery_url = settings.authentik_issuer.rstrip("/") + "/.well-known/openid-configuration"
    discovery = httpx.get(discovery_url, timeout=10).json()
    jwks_uri = discovery["jwks_uri"]
    return httpx.get(jwks_uri, timeout=10).json()


def refresh_jwks() -> None:
    _fetch_jwks.cache_clear()


def _decode_oidc_token(token: str) -> dict:
    try:
        jwks = _fetch_jwks()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot reach Authentik JWKS endpoint: {exc}",
        )
    try:
        return jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=settings.authentik_issuer.rstrip("/"),
            options={"verify_aud": False},  # audience varies by app setup
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid OIDC token: {exc}")


def get_or_create_user_from_token(token: str, db: Session) -> User:
    """Validate token, upsert user, return User ORM object."""
    payload = _decode_oidc_token(token)

    sub: str = payload.get("sub", "")
    email: str = payload.get("email", "")
    name: str = payload.get("name") or payload.get("preferred_username") or email.split("@")[0]

    if not sub or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing sub or email")

    # Use sub as the stable user ID (Authentik's UUID for this user)
    user = db.get(User, sub)
    if user is None:
        # First login — provision the user locally
        user = User(
            id=sub,
            email=email,
            hashed_password=hash_password(sub),  # unusable placeholder — login is via OIDC
            display_name=name,
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return user
