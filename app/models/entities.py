import enum
from datetime import date, datetime, time, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QueueStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    finished = "finished"


class ParticipantStatus(str, enum.Enum):
    waiting = "waiting"
    called = "called"
    completed = "completed"
    skipped = "skipped"
    cancelled = "cancelled"


class Organizer(Base):
    __tablename__ = "organizers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Queue(Base):
    __tablename__ = "queues"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organizer_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizers.id", ondelete="CASCADE"), nullable=True, index=True)
    public_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    management_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    max_participants: Mapped[int] = mapped_column(Integer, default=50)
    allow_join_after_start: Mapped[bool] = mapped_column(Boolean, default=True)
    show_participant_list: Mapped[bool] = mapped_column(Boolean, default=True)
    participant_instruction: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus), default=QueueStatus.active, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    participants: Mapped[list["Participant"]] = relationship(back_populates="queue", cascade="all, delete-orphan")
    events: Mapped[list["QueueEvent"]] = relationship(back_populates="queue", cascade="all, delete-orphan")


class QueueTemplate(Base):
    __tablename__ = "queue_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organizer_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizers.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    default_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    default_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    max_participants: Mapped[int] = mapped_column(Integer, default=50)
    allow_join_after_start: Mapped[bool] = mapped_column(Boolean, default=True)
    show_participant_list: Mapped[bool] = mapped_column(Boolean, default=True)
    participant_instruction: Mapped[str] = mapped_column(Text, default="")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OrganizerSettings(Base):
    __tablename__ = "organizer_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organizer_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizers.id", ondelete="CASCADE"), unique=True, index=True, nullable=True)
    organizer_name: Mapped[str] = mapped_column(String(100), default="Алексей Смирнов")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    notify_new_participant: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_queue_finished: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_queue_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    default_max_participants: Mapped[int] = mapped_column(Integer, default=50)
    default_show_participant_list: Mapped[bool] = mapped_column(Boolean, default=True)
    default_allow_join_after_start: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("queue_id", "number", name="uq_participant_queue_number"),
        UniqueConstraint("token", name="uq_participant_token"),
        Index("ix_participant_queue_status_order", "queue_id", "status", "queue_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    queue_id: Mapped[UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(100))
    token: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[ParticipantStatus] = mapped_column(Enum(ParticipantStatus), default=ParticipantStatus.waiting, index=True)
    queue_order: Mapped[int] = mapped_column(Integer)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queue: Mapped[Queue] = relationship(back_populates="participants")


class QueueEvent(Base):
    __tablename__ = "queue_events"
    __table_args__ = (Index("ix_queue_events_queue_created", "queue_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    queue_id: Mapped[UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[UUID | None] = mapped_column(ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    queue: Mapped[Queue] = relationship(back_populates="events")
