"""Add organizer accounts and ownership."""
from alembic import op
import sqlalchemy as sa


revision = "0004_organizers"
down_revision = "0003_queue_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("queues", sa.Column("organizer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_queues_organizer", "queues", "organizers", ["organizer_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_queues_organizer_id", "queues", ["organizer_id"])
    op.add_column("queue_templates", sa.Column("organizer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_templates_organizer", "queue_templates", "organizers", ["organizer_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_queue_templates_organizer_id", "queue_templates", ["organizer_id"])


def downgrade() -> None:
    op.drop_index("ix_queue_templates_organizer_id", table_name="queue_templates")
    op.drop_constraint("fk_templates_organizer", "queue_templates", type_="foreignkey")
    op.drop_column("queue_templates", "organizer_id")
    op.drop_index("ix_queues_organizer_id", table_name="queues")
    op.drop_constraint("fk_queues_organizer", "queues", type_="foreignkey")
    op.drop_column("queues", "organizer_id")
    op.drop_table("organizers")
