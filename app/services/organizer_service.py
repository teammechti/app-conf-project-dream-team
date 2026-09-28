from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import OrganizerSettings, Participant, ParticipantStatus, Queue, QueueTemplate
from app.schemas.queue import OrganizerSettingsUpdate, QueueTemplateCreate
from app.services.queue_service import average_wait_seconds


def get_organizer_settings(db: Session, organizer_id=None) -> OrganizerSettings:
    value = None
    if organizer_id is not None:
        value = db.scalar(select(OrganizerSettings).where(OrganizerSettings.organizer_id == organizer_id))
    else:
        value = db.scalar(select(OrganizerSettings).where(OrganizerSettings.organizer_id.is_(None)).order_by(OrganizerSettings.id))
    if value is None:
        value = OrganizerSettings(organizer_id=organizer_id)
        db.add(value)
        db.commit()
        db.refresh(value)
    return value


def update_organizer_settings(db: Session, payload: OrganizerSettingsUpdate, organizer_id=None) -> OrganizerSettings:
    value = get_organizer_settings(db, organizer_id)
    for key, item in payload.model_dump().items():
        setattr(value, key, item)
    db.commit()
    db.refresh(value)
    return value


def list_templates(db: Session, organizer_id=None) -> list[QueueTemplate]:
    statement = select(QueueTemplate).order_by(QueueTemplate.created_at.desc())
    if organizer_id is not None:
        statement = statement.where(QueueTemplate.organizer_id == organizer_id)
    return list(db.scalars(statement))


def get_template(db: Session, template_id: UUID, organizer_id=None) -> QueueTemplate:
    value = db.get(QueueTemplate, template_id)
    if value is None or (organizer_id is not None and value.organizer_id != organizer_id):
        raise HTTPException(404, "Шаблон не найден")
    return value


def create_template(db: Session, payload: QueueTemplateCreate, organizer_id=None) -> QueueTemplate:
    value = QueueTemplate(**payload.model_dump(), organizer_id=organizer_id)
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def update_template(db: Session, template_id: UUID, payload: QueueTemplateCreate, organizer_id=None) -> QueueTemplate:
    value = get_template(db, template_id, organizer_id)
    for key, item in payload.model_dump().items():
        setattr(value, key, item)
    db.commit()
    db.refresh(value)
    return value


def duplicate_template(db: Session, template_id: UUID, organizer_id=None) -> QueueTemplate:
    source = get_template(db, template_id, organizer_id)
    payload = QueueTemplateCreate(
        name=f"{source.name} — копия",
        description=source.description,
        location=source.location,
        default_start_time=source.default_start_time,
        default_end_time=source.default_end_time,
        max_participants=source.max_participants,
        allow_join_after_start=source.allow_join_after_start,
        show_participant_list=source.show_participant_list,
        participant_instruction=source.participant_instruction,
    )
    return create_template(db, payload, organizer_id)


def delete_template(db: Session, template_id: UUID, organizer_id=None) -> None:
    value = get_template(db, template_id, organizer_id)
    db.delete(value)
    db.commit()


def mark_template_used(db: Session, template_id: UUID, organizer_id=None) -> None:
    value = get_template(db, template_id, organizer_id)
    value.usage_count += 1
    db.commit()


def statistics(db: Session, period: str = "week", queue_id: UUID | None = None, organizer_id=None) -> dict:
    period = period if period in {"today", "week", "month"} else "week"
    days = {"today": 1, "week": 7, "month": 30}[period]
    try:
        local_timezone = ZoneInfo(get_organizer_settings(db, organizer_id).timezone)
    except ZoneInfoNotFoundError:
        local_timezone = ZoneInfo("Europe/Moscow")
    local_today = datetime.now(local_timezone).date()
    local_start = datetime.combine(local_today - timedelta(days=days - 1), datetime.min.time(), tzinfo=local_timezone)
    start = local_start.astimezone(timezone.utc)

    def local_joined_at(participant: Participant) -> datetime:
        value = participant.joined_at
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_timezone)

    statement = select(Queue).options(selectinload(Queue.participants)).order_by(Queue.created_at.desc())
    if organizer_id is not None:
        statement = statement.where(Queue.organizer_id == organizer_id)
    queues = list(db.scalars(statement))
    selected = [q for q in queues if queue_id is None or q.id == queue_id]
    participants = [p for q in selected for p in q.participants if local_joined_at(p).astimezone(timezone.utc) >= start]
    completed = [p for p in participants if p.status == ParticipantStatus.completed]
    skipped = [p for p in participants if p.status == ParticipantStatus.skipped]
    waits = average_wait_seconds(participants)
    service_times = [
        (p.completed_at.replace(tzinfo=None) - p.called_at.replace(tzinfo=None)).total_seconds()
        for p in participants
        if p.called_at is not None and p.completed_at is not None
    ]
    average_service_seconds = round(sum(service_times) / len(service_times)) if service_times else 0

    labels: list[str] = []
    points: list[int] = []
    if period == "today":
        for hour in range(0, 24, 2):
            labels.append(f"{hour:02d}:00")
            points.append(sum(1 for p in participants if local_joined_at(p).date() == local_today and hour <= local_joined_at(p).hour < hour + 2))
    else:
        for offset in range(days):
            current = (local_start + timedelta(days=offset)).date()
            labels.append(current.strftime("%d.%m"))
            points.append(sum(1 for p in participants if local_joined_at(p).date() == current))

    queue_rows = []
    for queue in selected:
        scoped = [p for p in queue.participants if local_joined_at(p).astimezone(timezone.utc) >= start]
        queue_service_times = [
            (p.completed_at.replace(tzinfo=None) - p.called_at.replace(tzinfo=None)).total_seconds()
            for p in scoped if p.called_at is not None and p.completed_at is not None
        ]
        queue_rows.append({
            "queue": queue,
            "total": len(scoped),
            "completed": sum(p.status == ParticipantStatus.completed for p in scoped),
            "skipped": sum(p.status == ParticipantStatus.skipped for p in scoped),
            "average_wait_seconds": average_wait_seconds(scoped),
            "average_service_seconds": round(sum(queue_service_times) / len(queue_service_times)) if queue_service_times else 0,
        })

    return {
        "period": period,
        "queues": queues,
        "selected_queue_id": str(queue_id) if queue_id else "",
        "total": len(participants),
        "completed": len(completed),
        "skipped": len(skipped),
        "average_wait_seconds": waits,
        "average_service_seconds": average_service_seconds,
        "waiting": sum(p.status == ParticipantStatus.waiting for p in participants),
        "cancelled": sum(p.status == ParticipantStatus.cancelled for p in participants),
        "labels": labels,
        "points": points,
        "queue_rows": queue_rows,
    }
