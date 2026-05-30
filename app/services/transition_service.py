"""
Approval workflow — explicit status transitions with a state machine.

Valid transitions:
  draft        → underReview   (owner or write-share)
  underReview  → draft         (owner — send back)
  underReview  → approved      (owner)
  approved     → archived      (owner)
  *            → archived      (owner — force archive from any state)

Blocked:
  approved → draft/underReview  (must archive then re-create)
  any transition by read-share users
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status as http_status
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.schemas.transition import TransitionRequest
from app.services.audit_service import append_audit

# (from_status, to_status) → minimum access required
ALLOWED: dict[tuple[str, str], str] = {
    ("draft",       "underReview"): "write",   # owner or write-share
    ("underReview", "draft"):       "owner",
    ("underReview", "approved"):    "owner",
    ("approved",    "archived"):    "owner",
    # Force-archive from any non-archived state
    ("draft",       "archived"):    "owner",
    ("underReview", "archived"):    "owner",
}


def _resolve_level(db: Session, project: Project, user_id: str) -> str | None:
    if project.owner_id == user_id:
        return "owner"
    share = (
        db.query(ProjectShare)
        .filter(ProjectShare.project_id == project.id, ProjectShare.user_id == user_id)
        .first()
    )
    return share.access_level if share else None


def _level_gte(actual: str, required: str) -> bool:
    order = {"read": 0, "write": 1, "owner": 2}
    return order.get(actual, -1) >= order.get(required, 99)


def apply_transition(db: Session, project_id: str, data: TransitionRequest, user_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Project not found")

    level = _resolve_level(db, project, user_id)
    if level is None:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Access denied")

    key = (project.status, data.to_status)
    required = ALLOWED.get(key)

    if required is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transition '{project.status}' → '{data.to_status}' is not allowed.",
        )

    if not _level_gte(level, required):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"This transition requires '{required}' access.",
        )

    old_status = project.status
    project.status = data.to_status

    append_audit(
        db,
        project_id=project_id,
        user_id=user_id,
        action_kind="status.transition",
        action_data={
            "from": old_status,
            "to": data.to_status,
            "note": data.note,
        },
    )
    db.commit()
    db.refresh(project)
    return project
