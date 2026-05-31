"""create rate_cards and project_templates tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("effective_date", sa.String(20), nullable=False),
        sa.Column("is_illustrative", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("entries", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rate_cards_org_id", "rate_cards", ["org_id"])

    op.create_table(
        "project_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("engagement_type", sa.String(50), nullable=False),
        sa.Column("engagement_context", sa.String(50), nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("template_json", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_templates_org_id", "project_templates", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_project_templates_org_id", table_name="project_templates")
    op.drop_table("project_templates")
    op.drop_index("ix_rate_cards_org_id", table_name="rate_cards")
    op.drop_table("rate_cards")
