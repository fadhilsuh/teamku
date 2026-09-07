"""Add remote employees, location events, and attendance policy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("is_remote", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "invitations",
        sa.Column("is_remote", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "office_settings",
        sa.Column("reverify_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "office_settings",
        sa.Column("reverify_count_per_day", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "office_settings",
        sa.Column(
            "reverify_window_start_minutes", sa.Integer(), nullable=False, server_default="60"
        ),
    )
    op.add_column(
        "office_settings",
        sa.Column(
            "reverify_window_end_minutes", sa.Integer(), nullable=False, server_default="420"
        ),
    )
    op.add_column(
        "office_settings",
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "office_settings",
        sa.Column("clock_in_reminder_time", sa.String(), nullable=False, server_default="09:15"),
    )
    op.add_column(
        "office_settings",
        sa.Column("clock_out_reminder_time", sa.String(), nullable=False, server_default="18:15"),
    )
    op.add_column(
        "office_settings",
        sa.Column("max_open_hours", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "office_settings",
        sa.Column("alert_managers", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "location_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("attendance_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("inside_geofence", sa.Boolean(), nullable=True),
        sa.Column("anomaly", sa.String(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_location_events_tenant_id", "location_events", ["tenant_id"])
    op.create_table(
        "alert_receipts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
    )
    op.create_index("ix_alert_receipts_tenant_id", "alert_receipts", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("alert_receipts")
    op.drop_table("location_events")
    for column in (
        "alert_managers",
        "max_open_hours",
        "clock_out_reminder_time",
        "clock_in_reminder_time",
        "alerts_enabled",
        "reverify_window_end_minutes",
        "reverify_window_start_minutes",
        "reverify_count_per_day",
        "reverify_enabled",
    ):
        op.drop_column("office_settings", column)
    op.drop_column("invitations", "is_remote")
    op.drop_column("employees", "is_remote")
