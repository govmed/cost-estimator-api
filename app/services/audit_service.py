"""
Server-side audit log.

append_audit() is called by project and share services on every mutation.
query_audit() is the read path for the API endpoint.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.audit_entry import AuditEntry

# Categories derived from action_kind prefix — used for filtering.
CATEGORY_PREFIXES: dict[str, str] = {
    "project": "project",
    "scenario": "scenario",
    "resource": "resource",
    "cloud": "cloud",
    "otherCost": "otherCost",
    "phase": "phase",
    "share": "share",
    "assumption": "assumption",
    "status": "status",
}


def _category(action_kind: str) -> str:
    prefix = action_kind.split(".")[0]
    return CATEGORY_PREFIXES.get(prefix, "other")


def append_audit(
    db: Session,
    *,
    project_id: str,
    user_id: str | None,
    action_kind: str,
    action_data: dict,
) -> AuditEntry:
    entry = AuditEntry(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=user_id,
        action_kind=action_kind,
        action_data=action_data,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(entry)
    # Caller is responsible for db.commit() — we don't commit here so the
    # audit write is part of the same transaction as the mutation.
    return entry


def query_audit(
    db: Session,
    project_id: str,
    *,
    category: str | None = None,
    action_kind: str | None = None,
    user_id: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEntry]:
    q = (
        db.query(AuditEntry)
        .filter(AuditEntry.project_id == project_id)
    )

    if action_kind:
        q = q.filter(AuditEntry.action_kind == action_kind)
    elif category:
        # Match all kinds that start with the category prefix
        q = q.filter(AuditEntry.action_kind.like(f"{category}.%"))

    if user_id:
        q = q.filter(AuditEntry.user_id == user_id)

    if since:
        q = q.filter(AuditEntry.timestamp >= since)

    return (
        q.order_by(desc(AuditEntry.timestamp))
        .offset(offset)
        .limit(min(limit, 500))  # hard cap
        .all()
    )


def count_audit(db: Session, project_id: str) -> int:
    return db.query(AuditEntry).filter(AuditEntry.project_id == project_id).count()
