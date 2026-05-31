from datetime import datetime
from pydantic import BaseModel, field_validator


class CommentCreate(BaseModel):
    entity_type: str
    entity_id: str
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment body cannot be empty")
        return v.strip()


class CommentRead(BaseModel):
    id: str
    project_id: str
    entity_type: str
    entity_id: str
    body: str
    created_by: str | None
    author_name: str | None
    author_email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentUpdate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment body cannot be empty")
        return v.strip()
