from pydantic import BaseModel


class TransitionRequest(BaseModel):
    to_status: str
    note: str | None = None


class TransitionResponse(BaseModel):
    id: str
    status: str
    previous_status: str

    model_config = {"from_attributes": True}
