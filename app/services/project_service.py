import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.schemas.project import ProjectCreate, ProjectUpdate

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
    """Return all projects the user owns or has been shared with."""
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

    if data.status is not None:
        if data.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}",
            )
        project.status = data.status

    current = dict(project.state_json)
    if data.project is not None:
        current["project"] = data.project
        project.name = data.project.get("name", project.name)
        project.client = data.project.get("client", project.client)
    if data.scenarios is not None:
        current["scenarios"] = data.scenarios

    project.state_json = current
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str, user_id: str) -> None:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete a project")
    db.delete(project)
    db.commit()
