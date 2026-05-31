import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class ProjectTemplate(Base):
    """
    A reusable project scaffold — a Project blob minus IDs and dates, with a
    name and description. New projects can instantiate from a template,
    inheriting phases, resources, cloud items, and other-cost structure.

    Org-scoped: templates are visible to all users in the org.
    Created from an existing project via POST /templates.
    """

    __tablename__ = "project_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    engagement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    engagement_context: Mapped[str] = mapped_column(String(50), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The template blob: {project: {...}, scenarios: [...]} with IDs stripped
    template_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProjectTemplate {self.name!r} org={self.org_id}>"
