"""Add multiple work locations and employee assignments."""

from alembic import op
import sqlalchemy as sa

revision = "0004_multi_work_locations"
down_revision = "0003_policy_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("work_location_id", sa.String(), nullable=True, server_default="office-default"))
    op.add_column("invitations", sa.Column("work_location_id", sa.String(), nullable=True))
    op.create_table(
        "office_locations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("radius_meters", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("office_locations")
    op.drop_column("invitations", "work_location_id")
    op.drop_column("employees", "work_location_id")
