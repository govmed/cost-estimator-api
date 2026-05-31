import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

VALID_EVENTS = {
    "project.created",
    "project.updated",
    "project.deleted",
    "status.transition",
    "share.grant",
    "share.revoke",
    "comment.created",
}


class Webhook(Base):
    """
    Outgoing webhook — POST to url when any of the subscribed events fires.

    secret: if set, sent as X-SOW-Signature (HMAC-SHA256 of the body)
    events: list of event names to subscribe to, e.g. ["status.transition"]
    last_fired_at: updated on each successful delivery attempt
    """

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Webhook {self.name!r} url={self.url[:40]}>"
