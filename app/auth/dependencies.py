"""
get_current_user — the single dependency every protected endpoint uses.

Routes to the standalone JWT validator (dev) or the Authentik OIDC
validator (staging/prod) based on AUTH_MODE in config.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models.user import User

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    if settings.use_oidc:
        from app.auth.oidc import get_or_create_user_from_token
        return get_or_create_user_from_token(token, db)

    # Standalone JWT path (dev / CI)
    from app.auth.jwt import decode_token
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("missing sub")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
