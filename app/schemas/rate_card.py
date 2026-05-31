from datetime import datetime
from typing import Any
from pydantic import BaseModel

ORG_DEFAULT = "org_demo"


class RateCardEntry(BaseModel):
    role: str
    skillLevel: str
    geography: str
    billRate: dict[str, Any]        # {amount: float, currency: str}
    internalCostRate: dict[str, Any]


class RateCardCreate(BaseModel):
    name: str
    version: str = "1.0"
    effective_date: str
    is_illustrative: bool = False
    entries: list[RateCardEntry]


class RateCardUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    effective_date: str | None = None
    is_illustrative: bool | None = None
    is_active: bool | None = None
    entries: list[RateCardEntry] | None = None


class RateCardRead(BaseModel):
    id: str
    org_id: str
    name: str
    version: str
    effective_date: str
    is_illustrative: bool
    is_active: bool
    entry_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_summary(cls, rc) -> "RateCardRead":
        return cls(
            id=rc.id, org_id=rc.org_id, name=rc.name, version=rc.version,
            effective_date=rc.effective_date, is_illustrative=rc.is_illustrative,
            is_active=rc.is_active, entry_count=len(rc.entries or []),
            created_by=rc.created_by, created_at=rc.created_at, updated_at=rc.updated_at,
        )


class RateCardFull(RateCardRead):
    entries: list[dict[str, Any]]

    @classmethod
    def from_orm_full(cls, rc) -> "RateCardFull":
        base = RateCardRead.from_orm_summary(rc)
        return cls(**base.model_dump(), entries=rc.entries or [])


class RateCardLookupResult(BaseModel):
    found: bool
    role: str
    skillLevel: str
    geography: str
    billRate: dict[str, Any] | None = None
    internalCostRate: dict[str, Any] | None = None
    rateCardId: str | None = None
    rateCardName: str | None = None
