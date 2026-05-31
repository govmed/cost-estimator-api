from datetime import datetime
from pydantic import BaseModel, HttpUrl
from app.models.webhook import VALID_EVENTS


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str]
    secret: str | None = None

    def validate_events(self) -> None:
        invalid = set(self.events) - VALID_EVENTS
        if invalid:
            raise ValueError(f"Unknown events: {invalid}. Valid: {sorted(VALID_EVENTS)}")


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookRead(BaseModel):
    id: str
    org_id: str
    name: str
    url: str
    events: list[str]
    is_active: bool
    created_by: str
    created_at: datetime
    last_fired_at: datetime | None

    model_config = {"from_attributes": True}
