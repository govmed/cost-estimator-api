from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    role: str | None = None
