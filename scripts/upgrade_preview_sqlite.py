"""Idempotent schema upgrade for the local preview SQLite database.

Production deployments use Alembic. This helper exists because the preview
database predates Alembic tracking and SQLite cannot add foreign keys in place.
"""
import os

from sqlalchemy import inspect, text


os.environ.setdefault("DATABASE_URL", "sqlite:///./preview.db")

from app.db.database import Base, engine  # noqa: E402


if engine.dialect.name != "sqlite":
    raise SystemExit("This helper may only be used with SQLite.")

Base.metadata.create_all(bind=engine)

columns_to_add = {
    "queues": {"organizer_id": "CHAR(32)"},
    "queue_templates": {"organizer_id": "CHAR(32)"},
    "organizer_settings": {"organizer_id": "CHAR(32)"},
}

with engine.begin() as connection:
    inspector = inspect(connection)
    for table, additions in columns_to_add.items():
        current = {column["name"] for column in inspector.get_columns(table)}
        for column, sql_type in additions.items():
            if column not in current:
                connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}'))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_queues_organizer_id ON queues (organizer_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_queue_templates_organizer_id ON queue_templates (organizer_id)"))
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_organizer_settings_organizer_id ON organizer_settings (organizer_id)"))

print("preview.db schema is up to date")
