from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ProjectSummary(BaseModel):
    """Lightweight listing — no state_json."""
    id: str
    name: str
    client: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    """Full project blob from the SPA — project metadata + all scenarios."""
    project: dict[str, Any]
    scenarios: list[dict[str, Any]]


class ProjectRead(BaseModel):
    """Full project returned to the SPA."""
    id: str
    owner_id: str
    name: str
    client: str
    status: str
    state_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    """Partial update — replace state_json and/or status."""
    project: dict[str, Any] | None = None
    scenarios: list[dict[str, Any]] | None = None
    status: str | None = None
