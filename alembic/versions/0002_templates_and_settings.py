"""Add reusable queue templates and organizer settings."""
from alembic import op
import sqlalchemy as sa


revision = "0002_templates_settings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queue_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("default_start_time", sa.Time(), nullable=True),
        sa.Column("default_end_time", sa.Time(), nullable=True),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("allow_join_after_start", sa.Boolean(), nullable=False),
        sa.Column("show_participant_list", sa.Boolean(), nullable=False),
        sa.Column("participant_instruction", sa.Text(), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "organizer_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organizer_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("notify_new_participant", sa.Boolean(), nullable=False),
        sa.Column("notify_queue_finished", sa.Boolean(), nullable=False),
        sa.Column("notify_queue_changes", sa.Boolean(), nullable=False),
        sa.Column("default_max_participants", sa.Integer(), nullable=False),
        sa.Column("default_show_participant_list", sa.Boolean(), nullable=False),
        sa.Column("default_allow_join_after_start", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("organizer_settings")
    op.drop_table("queue_templates")
