"""
Role-based access control.

Roles: user (default) | admin
Admin endpoints use require_admin() as a FastAPI dependency.
"""

from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user
from app.models.user import User

VALID_ROLES = {"user", "admin"}

# Authentik group names that map to the admin role.
# Must match the group names configured in the Authentik admin UI.
ADMIN_GROUPS = {"SOWCalc-Admins", "sow-calc-admins"}


def role_from_groups(groups: list[str]) -> str:
    """Derive the highest role from a list of Authentik group names."""
    for g in groups:
        if g in ADMIN_GROUPS:
            return "admin"
    return "user"


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
