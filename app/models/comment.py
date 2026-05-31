import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Comment(Base):
    """
    Annotation on any entity in a project — a resource, a cloud line item,
    a KPI, a phase, or the project itself.

    entity_type: the kind of thing being annotated
      (project | scenario | resource | cloud | otherCost | assumption | kpi)
    entity_id:   the ID of that specific entity
    """

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    author: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Comment {self.id} {self.entity_type}/{self.entity_id}>"
