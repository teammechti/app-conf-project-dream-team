"""Initial QueueManager schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    queue_status = sa.Enum("draft", "active", "paused", "finished", name="queuestatus")
    participant_status = sa.Enum("waiting", "called", "completed", "skipped", "cancelled", name="participantstatus")
    op.create_table(
        "queues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_code", sa.String(20), nullable=False),
        sa.Column("management_token", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("allow_join_after_start", sa.Boolean(), nullable=False),
        sa.Column("show_participant_list", sa.Boolean(), nullable=False),
        sa.Column("participant_instruction", sa.Text(), nullable=False),
        sa.Column("status", queue_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("management_token"),
        sa.UniqueConstraint("public_code"),
    )
    op.create_index("ix_queues_public_code", "queues", ["public_code"])
    op.create_index("ix_queues_management_token", "queues", ["management_token"])
    op.create_index("ix_queues_status", "queues", ["status"])
    op.create_table(
        "participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token", sa.String(80), nullable=False),
        sa.Column("status", participant_status, nullable=False),
        sa.Column("queue_order", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("queue_id", "number", name="uq_participant_queue_number"),
        sa.UniqueConstraint("token", name="uq_participant_token"),
    )
    op.create_index("ix_participants_queue_id", "participants", ["queue_id"])
    op.create_index("ix_participants_status", "participants", ["status"])
    op.create_index("ix_participants_token", "participants", ["token"])
    op.create_index("ix_participant_queue_status_order", "participants", ["queue_id", "status", "queue_order"])


def downgrade() -> None:
    op.drop_table("participants")
    op.drop_table("queues")
    sa.Enum(name="participantstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="queuestatus").drop(op.get_bind(), checkfirst=True)
