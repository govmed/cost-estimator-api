import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class RateCard(Base):
    """
    Org-level pricing reference. Multiple cards can coexist (e.g. Standard
    2026 Q1, Federal 2026). Each entry is keyed by (role, skillLevel, geography).

    Entries are stored as a JSON array — same structure as the seed JSON files
    shipped in Phase 1 — so the SPA can hot-swap the catalog without a schema change.
    """

    __tablename__ = "rate_cards"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    effective_date: Mapped[str] = mapped_column(String(20), nullable=False)
    is_illustrative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Array of {role, skillLevel, geography, billRate: {amount, currency},
    #            internalCostRate: {amount, currency}}
    entries: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RateCard {self.name} v{self.version} org={self.org_id}>"
