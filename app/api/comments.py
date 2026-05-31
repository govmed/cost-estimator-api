import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.services.project_service import get_project
from app.services.webhook_service import fire_event

ORG_DEFAULT = "org_demo"

router = APIRouter(prefix="/projects/{project_id}/comments", tags=["comments"])


def _read(c: Comment) -> CommentRead:
    return CommentRead(
        id=c.id, project_id=c.project_id,
        entity_type=c.entity_type, entity_id=c.entity_id,
        body=c.body, created_by=c.created_by,
        author_name=c.author.display_name if c.author else None,
        author_email=c.author.email if c.author else None,
        created_at=c.created_at, updated_at=c.updated_at,
    )


@router.get("", response_model=list[CommentRead])
def list_comments(
    project_id: str,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(db, project_id, current_user.id)  # access check
    q = db.query(Comment).filter(Comment.project_id == project_id)
    if entity_type:
        q = q.filter(Comment.entity_type == entity_type)
    if entity_id:
        q = q.filter(Comment.entity_id == entity_id)
    return [_read(c) for c in q.order_by(Comment.created_at).all()]


@router.post("", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(
    project_id: str,
    data: CommentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project(db, project_id, current_user.id)
    c = Comment(
        id=str(uuid.uuid4()),
        project_id=project_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        body=data.body,
        created_by=current_user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    org_id = getattr(current_user, "org_id", None) or ORG_DEFAULT
    fire_event(db, background_tasks, org_id, "comment.created", {
        "project_id": project_id, "project_name": project.name,
        "entity_type": data.entity_type, "entity_id": data.entity_id,
        "comment_id": c.id, "author": current_user.email,
        "preview": data.body[:120],
    })

    return _read(c)


@router.patch("/{comment_id}", response_model=CommentRead)
def update_comment(
    project_id: str,
    comment_id: str,
    data: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(db, project_id, current_user.id)
    c = db.get(Comment, comment_id)
    if not c or c.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if c.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's comment")
    c.body = data.body.strip()
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(c)
    return _read(c)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    project_id: str,
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(db, project_id, current_user.id)
    c = db.get(Comment, comment_id)
    if not c or c.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if c.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's comment")
    db.delete(c)
    db.commit()
