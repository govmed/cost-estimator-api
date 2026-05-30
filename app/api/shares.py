from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.share import ShareCreate, ShareRead
from app.services.share_service import list_shares, create_share, delete_share

router = APIRouter(prefix="/projects/{project_id}/shares", tags=["shares"])


@router.get("", response_model=list[ShareRead])
def get_shares(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_shares(db, project_id, current_user.id)


@router.post("", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
def add_share(
    project_id: str,
    data: ShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_share(db, project_id, data, current_user.id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_share(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_share(db, project_id, user_id, current_user.id)
