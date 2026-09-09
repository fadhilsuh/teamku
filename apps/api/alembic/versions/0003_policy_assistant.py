"""Add tenant-scoped policy content and Ask Teamku audit records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False), sa.Column("category", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False), sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True), sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False), sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_policies_tenant_id", "policies", ["tenant_id"])
    op.create_table(
        "policy_sections",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False), sa.Column("heading", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_policy_sections_tenant_id", "policy_sections", ["tenant_id"])
    op.create_index("ix_policy_sections_policy_id", "policy_sections", ["policy_id"])
    op.create_table(
        "policy_answer_audit",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False), sa.Column("question", sa.Text(), nullable=False),
        sa.Column("cited_sections", postgresql.JSONB(), nullable=False), sa.Column("provider", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False), sa.Column("suggested_action", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_answer_audit_tenant_id", "policy_answer_audit", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("policy_answer_audit")
    op.drop_table("policy_sections")
    op.drop_table("policies")
