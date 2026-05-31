import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.auth.roles import require_admin
from app.models.user import User
from app.models.rate_card import RateCard
from app.schemas.rate_card import (
    RateCardCreate, RateCardUpdate, RateCardRead, RateCardFull, RateCardLookupResult,
    ORG_DEFAULT,
)

router = APIRouter(prefix="/rate-cards", tags=["rate-cards"])


def _org(user: User) -> str:
    return getattr(user, "org_id", None) or ORG_DEFAULT


# ── List / Get ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RateCardRead])
def list_rate_cards(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(RateCard).filter(RateCard.org_id == _org(current_user))
    if active_only:
        q = q.filter(RateCard.is_active == True)  # noqa: E712
    cards = q.order_by(RateCard.effective_date.desc()).all()
    return [RateCardRead.from_orm_summary(c) for c in cards]


@router.get("/{card_id}", response_model=RateCardFull)
def get_rate_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card = db.get(RateCard, card_id)
    if not card or card.org_id != _org(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")
    return RateCardFull.from_orm_full(card)


@router.get("/{card_id}/lookup", response_model=RateCardLookupResult)
def lookup_rate(
    card_id: str,
    role: str = Query(...),
    skill_level: str = Query(..., alias="skillLevel"),
    geography: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find a specific entry in a rate card by role × skillLevel × geography."""
    card = db.get(RateCard, card_id)
    if not card or card.org_id != _org(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")

    for entry in (card.entries or []):
        if (
            entry.get("role", "").lower() == role.lower()
            and entry.get("skillLevel", "").lower() == skill_level.lower()
            and entry.get("geography", "").lower() == geography.lower()
        ):
            return RateCardLookupResult(
                found=True,
                role=entry["role"],
                skillLevel=entry["skillLevel"],
                geography=entry["geography"],
                billRate=entry.get("billRate"),
                internalCostRate=entry.get("internalCostRate"),
                rateCardId=card.id,
                rateCardName=card.name,
            )

    return RateCardLookupResult(found=False, role=role, skillLevel=skill_level, geography=geography)


# ── Create / Update (admin only) ───────────────────────────────────────────────

@router.post("", response_model=RateCardFull, status_code=status.HTTP_201_CREATED)
def create_rate_card(
    data: RateCardCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    card = RateCard(
        id=str(uuid.uuid4()),
        org_id=_org(admin),
        name=data.name,
        version=data.version,
        effective_date=data.effective_date,
        is_illustrative=data.is_illustrative,
        entries=[e.model_dump() for e in data.entries],
        created_by=admin.id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return RateCardFull.from_orm_full(card)


@router.put("/{card_id}", response_model=RateCardFull)
def update_rate_card(
    card_id: str,
    data: RateCardUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    card = db.get(RateCard, card_id)
    if not card or card.org_id != _org(admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")

    if data.name is not None:
        card.name = data.name
    if data.version is not None:
        card.version = data.version
    if data.effective_date is not None:
        card.effective_date = data.effective_date
    if data.is_illustrative is not None:
        card.is_illustrative = data.is_illustrative
    if data.is_active is not None:
        card.is_active = data.is_active
    if data.entries is not None:
        card.entries = [e.model_dump() for e in data.entries]

    card.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(card)
    return RateCardFull.from_orm_full(card)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate_card(
    card_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    card = db.get(RateCard, card_id)
    if not card or card.org_id != _org(admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rate card not found")
    db.delete(card)
    db.commit()
