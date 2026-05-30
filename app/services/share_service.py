import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.models.user import User
from app.schemas.share import ShareCreate, ShareRead, VALID_ACCESS_LEVELS
from app.services.user_service import get_by_email


def _require_owner(project: Project, user_id: str) -> None:
    if project.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can manage shares")


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def list_shares(db: Session, project_id: str, owner_id: str) -> list[ShareRead]:
    project = _get_project_or_404(db, project_id)
    _require_owner(project, owner_id)
    shares = db.query(ProjectShare).filter(ProjectShare.project_id == project_id).all()
    return [
        ShareRead(
            id=s.id,
            project_id=s.project_id,
            user_id=s.user_id,
            email=s.user.email,
            display_name=s.user.display_name,
            access_level=s.access_level,
            created_at=s.created_at,
        )
        for s in shares
    ]


def create_share(db: Session, project_id: str, data: ShareCreate, owner_id: str) -> ShareRead:
    project = _get_project_or_404(db, project_id)
    _require_owner(project, owner_id)

    if data.access_level not in VALID_ACCESS_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"access_level must be one of: {sorted(VALID_ACCESS_LEVELS)}",
        )

    target = get_by_email(db, data.email)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with yourself")

    share = ProjectShare(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=target.id,
        access_level=data.access_level,
    )
    db.add(share)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already shared with this user")
    db.refresh(share)

    return ShareRead(
        id=share.id,
        project_id=share.project_id,
        user_id=share.user_id,
        email=target.email,
        display_name=target.display_name,
        access_level=share.access_level,
        created_at=share.created_at,
    )


def delete_share(db: Session, project_id: str, user_id: str, owner_id: str) -> None:
    project = _get_project_or_404(db, project_id)
    _require_owner(project, owner_id)

    share = (
        db.query(ProjectShare)
        .filter(ProjectShare.project_id == project_id, ProjectShare.user_id == user_id)
        .first()
    )
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    db.delete(share)
    db.commit()
