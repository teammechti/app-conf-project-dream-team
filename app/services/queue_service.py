import secrets
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Participant, ParticipantStatus, Queue, QueueEvent, QueueStatus
from app.schemas.queue import ParticipantCreate, QueueCreate


ACTIVE_PARTICIPANT_STATUSES = (
    ParticipantStatus.waiting,
    ParticipantStatus.called,
    ParticipantStatus.skipped,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _code() -> str:
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].lower()


def average_wait_seconds(participants: list[Participant]) -> int:
    waits = [
        (p.called_at.replace(tzinfo=None) - p.joined_at.replace(tzinfo=None)).total_seconds()
        for p in participants
        if p.called_at is not None
    ]
    return round(sum(waits) / len(waits)) if waits else 0


def _event_message(kind: str, participant: Participant | None = None, *, detail: str = "") -> str:
    person = f"{participant.number} · {participant.name}" if participant else "Очередь"
    messages = {
        "joined": f"Новый участник: {person}",
        "called": f"Вызов участника: {person}",
        "acknowledged": f"Подтверждение «Я иду»: {person}",
        "completed": f"Обслуживание завершено: {person}",
        "skipped": f"Вызов пропущен: {person}",
        "restored": f"Возврат в очередь: {person}",
        "cancelled": f"Выход из очереди: {person}",
        "renamed": f"Имя участника изменено: {person}" if not detail else f"Имя изменено: {detail} → {participant.name}",
        "created": "Очередь создана и запущена",
        "paused": "Очередь поставлена на паузу",
        "resumed": "Очередь продолжена",
        "finished": "Очередь завершена",
    }
    return messages[kind]


def _record_event(
    db: Session,
    queue: Queue,
    kind: str,
    participant: Participant | None = None,
    *,
    detail: str = "",
) -> QueueEvent:
    event = QueueEvent(
        queue_id=queue.id,
        participant_id=participant.id if participant else None,
        kind=kind,
        message=_event_message(kind, participant, detail=detail),
    )
    db.add(event)
    return event


class QueueService:
    @staticmethod
    def create(db: Session, payload: QueueCreate, organizer_id=None) -> Queue:
        code = _code()
        while db.scalar(select(Queue.id).where(Queue.public_code == code)):
            code = _code()
        queue = Queue(
            **payload.model_dump(),
            organizer_id=organizer_id,
            public_code=code,
            management_token=secrets.token_urlsafe(32),
            status=QueueStatus.active,
            started_at=_now(),
        )
        db.add(queue)
        db.flush()
        _record_event(db, queue, "created")
        db.commit()
        db.refresh(queue)
        return queue

    @staticmethod
    def by_code(db: Session, code: str, *, lock: bool = False) -> Queue:
        stmt: Select[tuple[Queue]] = select(Queue).where(Queue.public_code == code)
        if lock:
            stmt = stmt.with_for_update()
        queue = db.scalar(stmt)
        if queue is None:
            raise HTTPException(404, "Очередь не найдена")
        return queue

    @staticmethod
    def by_management_token(db: Session, token: str, *, lock: bool = False) -> Queue:
        stmt = select(Queue).where(Queue.management_token == token)
        if lock:
            stmt = stmt.with_for_update()
        queue = db.scalar(stmt)
        if queue is None:
            raise HTTPException(404, "Ссылка управления недействительна")
        return queue

    @staticmethod
    def delete(db: Session, queue_id, organizer_id) -> None:
        queue = db.scalar(select(Queue).where(Queue.id == queue_id, Queue.organizer_id == organizer_id))
        if queue is None:
            raise HTTPException(404, "Очередь не найдена")
        db.delete(queue)
        db.commit()

    @staticmethod
    def participant_by_token(db: Session, token: str, *, lock: bool = False) -> Participant:
        stmt = select(Participant).where(Participant.token == token)
        if lock:
            stmt = stmt.with_for_update()
        participant = db.scalar(stmt)
        if participant is None:
            raise HTTPException(404, "Участник не найден")
        return participant

    @staticmethod
    def participants(db: Session, queue_id, *, lock: bool = False) -> list[Participant]:
        stmt = select(Participant).where(Participant.queue_id == queue_id).order_by(Participant.queue_order)
        if lock:
            stmt = stmt.with_for_update()
        return list(db.scalars(stmt))

    @staticmethod
    def join(db: Session, code: str, payload: ParticipantCreate) -> Participant:
        queue = QueueService.by_code(db, code, lock=True)
        if queue.status == QueueStatus.finished:
            raise HTTPException(409, "Эта очередь уже завершена")
        if queue.status in (QueueStatus.active, QueueStatus.paused) and not queue.allow_join_after_start:
            raise HTTPException(409, "Регистрация после запуска отключена")
        active_count = db.scalar(
            select(func.count(Participant.id)).where(
                Participant.queue_id == queue.id,
                Participant.status.in_(ACTIVE_PARTICIPANT_STATUSES),
            )
        ) or 0
        if active_count >= queue.max_participants:
            raise HTTPException(409, "В очереди больше нет свободных мест")
        max_order = db.scalar(select(func.max(Participant.queue_order)).where(Participant.queue_id == queue.id)) or 0
        order = max_order + 1
        participant = Participant(
            queue_id=queue.id,
            number=f"A-{order:03d}",
            queue_order=order,
            name=payload.name.strip(),
            token=secrets.token_urlsafe(32),
            status=ParticipantStatus.waiting,
        )
        db.add(participant)
        db.flush()
        _record_event(db, queue, "joined", participant)
        db.commit()
        db.refresh(participant)
        return participant

    @staticmethod
    def queue_state(db: Session, queue: Queue) -> dict[str, Any]:
        participants = QueueService.participants(db, queue.id)
        counts = {status.value: 0 for status in ParticipantStatus}
        for participant in participants:
            counts[participant.status.value] += 1
        called = next((p for p in participants if p.status == ParticipantStatus.called), None)
        visible = [p for p in participants if p.status in ACTIVE_PARTICIPANT_STATUSES]
        recent_events = list(db.scalars(
            select(QueueEvent).where(QueueEvent.queue_id == queue.id).order_by(QueueEvent.created_at.desc()).limit(20)
        ))
        return {
            "id": str(queue.id),
            "public_code": queue.public_code,
            "name": queue.name,
            "description": queue.description,
            "location": queue.location,
            "date": _iso(queue.date),
            "start_time": queue.start_time.strftime("%H:%M") if queue.start_time else None,
            "end_time": queue.end_time.strftime("%H:%M") if queue.end_time else None,
            "max_participants": queue.max_participants,
            "allow_join_after_start": queue.allow_join_after_start,
            "show_participant_list": queue.show_participant_list,
            "participant_instruction": queue.participant_instruction,
            "status": queue.status.value,
            "called": QueueService.participant_dict(called) if called else None,
            "participants": [QueueService.participant_dict(p) for p in visible],
            "all_participants": [QueueService.participant_dict(p) for p in participants],
            "counts": counts,
            "average_wait_seconds": average_wait_seconds(participants),
            "recent_events": [QueueService.event_dict(event, queue.name) for event in recent_events],
        }

    @staticmethod
    def participant_dict(participant: Participant | None) -> dict[str, Any] | None:
        if participant is None:
            return None
        return {
            "id": str(participant.id),
            "number": participant.number,
            "name": participant.name,
            "status": participant.status.value,
            "queue_order": participant.queue_order,
            "joined_at": _iso(participant.joined_at),
            "called_at": _iso(participant.called_at) if participant.called_at else None,
            "completed_at": _iso(participant.completed_at) if participant.completed_at else None,
            "acknowledged_at": _iso(participant.acknowledged_at) if participant.acknowledged_at else None,
        }

    @staticmethod
    def event_dict(event: QueueEvent, queue_name: str | None = None) -> dict[str, Any]:
        return {
            "id": str(event.id),
            "queue_id": str(event.queue_id),
            "queue_name": queue_name,
            "kind": event.kind,
            "message": event.message,
            "created_at": _iso(event.created_at),
        }

    @staticmethod
    def recent_events(db: Session, limit: int = 20, organizer_id=None) -> list[dict[str, Any]]:
        statement = (
            select(QueueEvent, Queue.name)
            .join(Queue, Queue.id == QueueEvent.queue_id)
            .order_by(QueueEvent.created_at.desc())
            .limit(limit)
        )
        if organizer_id is not None:
            statement = statement.where(Queue.organizer_id == organizer_id)
        rows = db.execute(statement).all()
        return [QueueService.event_dict(event, queue_name) for event, queue_name in rows]

    @staticmethod
    def participant_state(db: Session, participant: Participant) -> dict[str, Any]:
        queue = db.get(Queue, participant.queue_id)
        state = QueueService.queue_state(db, queue)
        active = state["participants"]
        ahead = sum(
            1 for p in active
            if p["status"] in ("waiting", "called") and p["queue_order"] < participant.queue_order
        )
        avg = state["average_wait_seconds"] or 4 * 60
        return {
            "participant": QueueService.participant_dict(participant),
            "queue": state,
            "people_ahead": ahead,
            "estimated_wait_seconds": ahead * avg,
        }

    @staticmethod
    def _call_next(participants: list[Participant]) -> Participant | None:
        waiting = next((p for p in participants if p.status == ParticipantStatus.waiting), None)
        if waiting:
            waiting.status = ParticipantStatus.called
            waiting.called_at = _now()
        return waiting

    @staticmethod
    def next(db: Session, token: str) -> tuple[Queue, Participant | None]:
        queue = QueueService.by_management_token(db, token, lock=True)
        if queue.status == QueueStatus.finished:
            raise HTTPException(409, "Очередь завершена")
        if queue.status == QueueStatus.paused:
            raise HTTPException(409, "Сначала продолжите очередь")
        participants = QueueService.participants(db, queue.id, lock=True)
        current = next((p for p in participants if p.status == ParticipantStatus.called), None)
        if current:
            current.status = ParticipantStatus.completed
            current.completed_at = _now()
            _record_event(db, queue, "completed", current)
        called = QueueService._call_next(participants)
        if called:
            _record_event(db, queue, "called", called)
        db.commit()
        return queue, called

    @staticmethod
    def call(db: Session, token: str, participant_id: str) -> tuple[Queue, Participant]:
        queue = QueueService.by_management_token(db, token, lock=True)
        if queue.status != QueueStatus.active:
            raise HTTPException(409, "Очередь сейчас недоступна для вызова")
        participants = QueueService.participants(db, queue.id, lock=True)
        target = next((p for p in participants if str(p.id) == participant_id), None)
        if target is None or target.status not in (ParticipantStatus.waiting, ParticipantStatus.skipped):
            raise HTTPException(409, "Участника нельзя вызвать")
        current = next((p for p in participants if p.status == ParticipantStatus.called), None)
        if current and current.id != target.id:
            current.status = ParticipantStatus.completed
            current.completed_at = _now()
            _record_event(db, queue, "completed", current)
        target.status = ParticipantStatus.called
        target.called_at = _now()
        target.acknowledged_at = None
        _record_event(db, queue, "called", target)
        db.commit()
        return queue, target

    @staticmethod
    def skip(db: Session, token: str, participant_id: str | None = None) -> tuple[Queue, Participant | None]:
        queue = QueueService.by_management_token(db, token, lock=True)
        participants = QueueService.participants(db, queue.id, lock=True)
        current = next(
            (p for p in participants if (str(p.id) == participant_id if participant_id else p.status == ParticipantStatus.called)),
            None,
        )
        if current is None or current.status not in (ParticipantStatus.called, ParticipantStatus.waiting):
            raise HTTPException(409, "Участника нельзя пропустить")
        current.status = ParticipantStatus.skipped
        current.skipped_at = _now()
        current.acknowledged_at = None
        _record_event(db, queue, "skipped", current)
        called = QueueService._call_next(participants) if queue.status == QueueStatus.active else None
        if called:
            _record_event(db, queue, "called", called)
        db.commit()
        return queue, called

    @staticmethod
    def restore(db: Session, token: str, participant_id: str) -> Queue:
        queue = QueueService.by_management_token(db, token, lock=True)
        participants = QueueService.participants(db, queue.id, lock=True)
        participant = next((p for p in participants if str(p.id) == participant_id), None)
        if participant is None or participant.status != ParticipantStatus.skipped:
            raise HTTPException(409, "Участника нельзя вернуть")
        participant.status = ParticipantStatus.waiting
        participant.acknowledged_at = None
        participant.queue_order = max((p.queue_order for p in participants), default=0) + 1
        _record_event(db, queue, "restored", participant)
        db.commit()
        return queue

    @staticmethod
    def set_status(db: Session, token: str, status: QueueStatus) -> Queue:
        queue = QueueService.by_management_token(db, token, lock=True)
        if queue.status == QueueStatus.finished:
            raise HTTPException(409, "Очередь уже завершена")
        queue.status = status
        if status == QueueStatus.finished:
            queue.finished_at = _now()
        _record_event(db, queue, {QueueStatus.paused: "paused", QueueStatus.active: "resumed", QueueStatus.finished: "finished"}[status])
        db.commit()
        return queue

    @staticmethod
    def rename_participant(db: Session, token: str, name: str) -> Participant:
        participant = QueueService.participant_by_token(db, token, lock=True)
        if participant.status == ParticipantStatus.cancelled:
            raise HTTPException(409, "Участник уже покинул очередь")
        old_identity = f"{participant.number} · {participant.name}"
        participant.name = name.strip()
        _record_event(db, participant.queue, "renamed", participant, detail=old_identity)
        db.commit()
        return participant

    @staticmethod
    def acknowledge_participant(db: Session, token: str) -> tuple[Queue, Participant]:
        participant = QueueService.participant_by_token(db, token, lock=True)
        queue = QueueService.by_code(db, participant.queue.public_code, lock=True)
        if participant.status != ParticipantStatus.called:
            raise HTTPException(409, "Подтвердить можно только после вызова")
        if participant.acknowledged_at is None:
            participant.acknowledged_at = _now()
            _record_event(db, queue, "acknowledged", participant)
            db.commit()
        return queue, participant

    @staticmethod
    def cancel_participant(db: Session, token: str) -> tuple[Queue, Participant]:
        participant = QueueService.participant_by_token(db, token, lock=True)
        queue = QueueService.by_code(db, participant.queue.public_code, lock=True)
        if participant.status == ParticipantStatus.cancelled:
            return queue, participant
        was_called = participant.status == ParticipantStatus.called
        participant.status = ParticipantStatus.cancelled
        participant.cancelled_at = _now()
        _record_event(db, queue, "cancelled", participant)
        if was_called and queue.status == QueueStatus.active:
            participants = QueueService.participants(db, queue.id, lock=True)
            called = QueueService._call_next(participants)
            if called:
                _record_event(db, queue, "called", called)
        db.commit()
        return queue, participant

    @staticmethod
    def dashboard(db: Session, organizer_id=None) -> dict[str, Any]:
        status_order = case(
            (Queue.status == QueueStatus.active, 0),
            (Queue.status == QueueStatus.paused, 1),
            (Queue.status == QueueStatus.finished, 2),
            else_=3,
        )
        statement = select(Queue).options(selectinload(Queue.participants)).order_by(status_order, Queue.created_at.desc())
        if organizer_id is not None:
            statement = statement.where(Queue.organizer_id == organizer_id)
        queues = list(db.scalars(statement))
        cards = []
        today_total = 0
        waits: list[int] = []
        for queue in queues:
            state = QueueService.queue_state(db, queue)
            today_total += sum(1 for p in queue.participants if p.joined_at.date() == date.today())
            if state["average_wait_seconds"]:
                waits.append(state["average_wait_seconds"])
            cards.append({"queue": queue, "state": state})
        return {
            "cards": cards,
            "active_count": sum(q.status == QueueStatus.active for q in queues),
            "paused_count": sum(q.status == QueueStatus.paused for q in queues),
            "finished_count": sum(q.status == QueueStatus.finished for q in queues),
            "today_total": today_total,
            "average_wait_seconds": round(sum(waits) / len(waits)) if waits else 0,
        }
