import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

VALID_STATUSES = {"draft", "underReview", "approved", "archived"}


def list_projects(db: Session, owner_id: str) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.owner_id == owner_id)
        .order_by(Project.updated_at.desc())
        .all()
    )


def get_project(db: Session, project_id: str, owner_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != owner_id:
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


def update_project(db: Session, project_id: str, data: ProjectUpdate, owner_id: str) -> Project:
    project = get_project(db, project_id, owner_id)

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


def delete_project(db: Session, project_id: str, owner_id: str) -> None:
    project = get_project(db, project_id, owner_id)
    db.delete(project)
    db.commit()
