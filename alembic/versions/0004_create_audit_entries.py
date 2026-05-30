"""create audit_entries table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-30

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action_kind", sa.String(80), nullable=False),
        sa.Column("action_data", sa.JSON, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_entries_project_id", "audit_entries", ["project_id"])
    op.create_index("ix_audit_entries_user_id", "audit_entries", ["user_id"])
    op.create_index("ix_audit_entries_action_kind", "audit_entries", ["action_kind"])
    op.create_index("ix_audit_entries_timestamp", "audit_entries", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_entries_timestamp", table_name="audit_entries")
    op.drop_index("ix_audit_entries_action_kind", table_name="audit_entries")
    op.drop_index("ix_audit_entries_user_id", table_name="audit_entries")
    op.drop_index("ix_audit_entries_project_id", table_name="audit_entries")
    op.drop_table("audit_entries")
