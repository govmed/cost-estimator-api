"""create comments and webhooks tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("created_by", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comments_project_id", "comments", ["project_id"])
    op.create_index("ix_comments_entity", "comments", ["project_id", "entity_type", "entity_id"])

    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("events", sa.JSON, nullable=False),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webhooks_org_id", "webhooks", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_webhooks_org_id", table_name="webhooks")
    op.drop_table("webhooks")
    op.drop_index("ix_comments_entity", table_name="comments")
    op.drop_index("ix_comments_project_id", table_name="comments")
    op.drop_table("comments")
