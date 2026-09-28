"""Make queue place and schedule optional."""
from alembic import op
import sqlalchemy as sa


revision = "0006_optional_queue_schedule"
down_revision = "0005_auth_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("queues") as batch:
        batch.alter_column("location", existing_type=sa.String(200), nullable=True)
        batch.alter_column("date", existing_type=sa.Date(), nullable=True)
        batch.alter_column("start_time", existing_type=sa.Time(), nullable=True)
        batch.alter_column("end_time", existing_type=sa.Time(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("queues") as batch:
        batch.alter_column("end_time", existing_type=sa.Time(), nullable=False)
        batch.alter_column("start_time", existing_type=sa.Time(), nullable=False)
        batch.alter_column("date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("location", existing_type=sa.String(200), nullable=False)
