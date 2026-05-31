from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.project import ProjectRead
from app.schemas.transition import TransitionRequest
from app.services.transition_service import apply_transition
from app.services.webhook_service import fire_event

ORG_DEFAULT = "org_demo"

router = APIRouter(prefix="/projects/{project_id}/transitions", tags=["workflow"])


@router.post("", response_model=ProjectRead)
def transition_project(
    project_id: str,
    data: TransitionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    old_status = db.execute(
        __import__("sqlalchemy").text("SELECT status FROM projects WHERE id = :id"),
        {"id": project_id},
    ).scalar()

    project = apply_transition(db, project_id, data, current_user.id)

    org_id = getattr(current_user, "org_id", None) or ORG_DEFAULT
    fire_event(db, background_tasks, org_id, "status.transition", {
        "project_id": project_id,
        "project_name": project.name,
        "from": old_status,
        "to": project.status,
        "note": data.note,
        "by": current_user.email,
    })

    return project
