from datetime import datetime
from pydantic import BaseModel, EmailStr

VALID_ACCESS_LEVELS = {"read", "write"}


class ShareCreate(BaseModel):
    email: EmailStr
    access_level: str = "read"


class ShareRead(BaseModel):
    id: str
    project_id: str
    user_id: str
    email: str
    display_name: str
    access_level: str
    created_at: datetime

    model_config = {"from_attributes": True}
