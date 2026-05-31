import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.auth.roles import require_admin
from app.models.user import User
from app.models.webhook import Webhook, VALID_EVENTS
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookRead

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

ORG_DEFAULT = "org_demo"


def _org(user: User) -> str:
    return getattr(user, "org_id", None) or ORG_DEFAULT


@router.get("", response_model=list[WebhookRead])
def list_webhooks(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return db.query(Webhook).filter(Webhook.org_id == _org(admin)).all()


@router.get("/events", response_model=list[str])
def list_valid_events(_: User = Depends(get_current_user)):
    """Return the list of event names webhooks can subscribe to."""
    return sorted(VALID_EVENTS)


@router.post("", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
def create_webhook(
    data: WebhookCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data.validate_events()
    hook = Webhook(
        id=str(uuid.uuid4()),
        org_id=_org(admin),
        name=data.name,
        url=data.url,
        events=data.events,
        secret=data.secret,
        created_by=admin.id,
    )
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return hook


@router.put("/{webhook_id}", response_model=WebhookRead)
def update_webhook(
    webhook_id: str,
    data: WebhookUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    hook = db.get(Webhook, webhook_id)
    if not hook or hook.org_id != _org(admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    if data.name is not None:
        hook.name = data.name
    if data.url is not None:
        hook.url = data.url
    if data.events is not None:
        WebhookCreate(name="x", url="http://x", events=data.events).validate_events()
        hook.events = data.events
    if data.secret is not None:
        hook.secret = data.secret
    if data.is_active is not None:
        hook.is_active = data.is_active
    db.commit()
    db.refresh(hook)
    return hook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    hook = db.get(Webhook, webhook_id)
    if not hook or hook.org_id != _org(admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    db.delete(hook)
    db.commit()
