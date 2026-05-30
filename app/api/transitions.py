from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.project import ProjectRead
from app.schemas.transition import TransitionRequest
from app.services.transition_service import apply_transition

router = APIRouter(prefix="/projects/{project_id}/transitions", tags=["workflow"])


@router.post("", response_model=ProjectRead)
def transition_project(
    project_id: str,
    data: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return apply_transition(db, project_id, data, current_user.id)
