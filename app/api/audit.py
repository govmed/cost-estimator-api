from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.audit import AuditEntryRead, AuditPage
from app.services.audit_service import query_audit, count_audit
from app.services.project_service import get_project

router = APIRouter(prefix="/projects/{project_id}/audit", tags=["audit"])


@router.get("", response_model=AuditPage)
def get_audit_log(
    project_id: str,
    category: str | None = Query(None, description="Filter by category prefix (project, resource, cloud, share…)"),
    action_kind: str | None = Query(None, description="Filter by exact action kind"),
    user_id: str | None = Query(None, description="Filter by acting user"),
    since: datetime | None = Query(None, description="Only entries at or after this ISO timestamp"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the caller has at least read access to this project
    get_project(db, project_id, current_user.id)

    entries = query_audit(
        db,
        project_id,
        category=category,
        action_kind=action_kind,
        user_id=user_id,
        since=since,
        limit=limit,
        offset=offset,
    )
    total = count_audit(db, project_id)

    return AuditPage(
        total=total,
        limit=limit,
        offset=offset,
        entries=[AuditEntryRead.model_validate(e) for e in entries],
    )
