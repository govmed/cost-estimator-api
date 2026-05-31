import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.audit_service import append_audit
from app.schemas.validation import validate_project_blob

VALID_STATUSES = {"draft", "underReview", "approved", "archived"}


def _access_level(db: Session, project: Project, user_id: str) -> str | None:
    """Return 'owner', 'write', 'read', or None (no access)."""
    if project.owner_id == user_id:
        return "owner"
    share = (
        db.query(ProjectShare)
        .filter(ProjectShare.project_id == project.id, ProjectShare.user_id == user_id)
        .first()
    )
    return share.access_level if share else None


def list_projects(db: Session, owner_id: str) -> list[Project]:
    shared_ids = (
        db.query(ProjectShare.project_id)
        .filter(ProjectShare.user_id == owner_id)
        .subquery()
    )
    return (
        db.query(Project)
        .filter(or_(Project.owner_id == owner_id, Project.id.in_(shared_ids)))
        .order_by(Project.updated_at.desc())
        .all()
    )


def get_project(db: Session, project_id: str, user_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if _access_level(db, project, user_id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


def create_project(db: Session, data: ProjectCreate, owner_id: str) -> Project:
    validate_project_blob({"project": data.project, "scenarios": data.scenarios})
    proj_data = data.project
    project_id = proj_data.get("id") or str(uuid.uuid4())
    project = Project(
        id=project_id,
        owner_id=owner_id,
        name=proj_data.get("name", "Untitled"),
        client=proj_data.get("client", ""),
        status=proj_data.get("status", "draft"),
        state_json={"project": data.project, "scenarios": data.scenarios},
    )
    db.add(project)
    append_audit(
        db,
        project_id=project_id,
        user_id=owner_id,
        action_kind="project.create",
        action_data={"name": project.name, "client": project.client, "engagementType": proj_data.get("engagementType")},
    )
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: str, data: ProjectUpdate, user_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    level = _access_level(db, project, user_id)
    if level is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if level == "read":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only access")

    changes: dict = {}

    if data.status is not None:
        if data.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}",
            )
        if data.status != project.status:
            changes["status"] = {"before": project.status, "after": data.status}
        project.status = data.status

    current = dict(project.state_json)
    if data.project is not None or data.scenarios is not None:
        preview = {
            "project": data.project if data.project is not None else current.get("project", {}),
            "scenarios": data.scenarios if data.scenarios is not None else current.get("scenarios", []),
        }
        validate_project_blob(preview)

    if data.project is not None:
        if data.project.get("name") != project.name:
            changes["name"] = {"before": project.name, "after": data.project.get("name")}
        current["project"] = data.project
        project.name = data.project.get("name", project.name)
        project.client = data.project.get("client", project.client)
    if data.scenarios is not None:
        changes["scenarios_updated"] = True
        current["scenarios"] = data.scenarios

    project.state_json = current
    project.updated_at = datetime.now(timezone.utc)

    if changes:
        append_audit(
            db,
            project_id=project_id,
            user_id=user_id,
            action_kind="project.update",
            action_data={"changes": changes},
        )

    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str, user_id: str) -> None:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete a project")
    # Audit entry written before delete (CASCADE will remove it, but it's recorded in the response)
    append_audit(
        db,
        project_id=project_id,
        user_id=user_id,
        action_kind="project.delete",
        action_data={"name": project.name},
    )
    db.commit()
    db.delete(project)
    db.commit()
