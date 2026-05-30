from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AuditEntryRead(BaseModel):
    id: str
    project_id: str
    user_id: str | None
    action_kind: str
    action_data: dict[str, Any]
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditPage(BaseModel):
    total: int
    limit: int
    offset: int
    entries: list[AuditEntryRead]
