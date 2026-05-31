from datetime import datetime
from typing import Any
from pydantic import BaseModel


class TemplateCreate(BaseModel):
    """Create a template from an existing project."""
    source_project_id: str
    name: str
    description: str = ""
    is_public: bool = True


class TemplateSummary(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    engagement_type: str
    engagement_context: str
    is_public: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateInstantiateRequest(BaseModel):
    """Create a new project from a template."""
    name: str
    client: str
    base_currency: str = "USD"


class TemplateInstantiateResponse(BaseModel):
    """The newly created project."""
    project_id: str
    message: str
