"""Add persistent queue event log and participant acknowledgement."""
from alembic import op
import sqlalchemy as sa


revision = "0003_queue_events"
down_revision = "0002_templates_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "queue_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_events_queue_id", "queue_events", ["queue_id"])
    op.create_index("ix_queue_events_created_at", "queue_events", ["created_at"])
    op.create_index("ix_queue_events_queue_created", "queue_events", ["queue_id", "created_at"])


def downgrade() -> None:
    op.drop_table("queue_events")
    op.drop_column("participants", "acknowledged_at")
