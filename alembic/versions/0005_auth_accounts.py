"""Add organizer credentials and per-account settings."""
from alembic import op
import sqlalchemy as sa


revision = "0005_auth_accounts"
down_revision = "0004_organizers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizers", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("organizers", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("organizers", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_organizers_email", "organizers", ["email"], unique=True)

    op.add_column("organizer_settings", sa.Column("organizer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_organizer_settings_organizer",
        "organizer_settings",
        "organizers",
        ["organizer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_organizer_settings_organizer_id", "organizer_settings", ["organizer_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organizer_settings_organizer_id", table_name="organizer_settings")
    op.drop_constraint("fk_organizer_settings_organizer", "organizer_settings", type_="foreignkey")
    op.drop_column("organizer_settings", "organizer_id")
    op.drop_index("ix_organizers_email", table_name="organizers")
    op.drop_column("organizers", "last_login_at")
    op.drop_column("organizers", "password_hash")
    op.drop_column("organizers", "email")
