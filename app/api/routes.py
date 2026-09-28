from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.entities import Organizer, QueueStatus
from app.schemas.queue import (
    AIQueueDescriptionRequest,
    AIQueueDraft,
    OrganizerSettingsUpdate,
    OrganizerLogin,
    OrganizerRegister,
    PasswordChange,
    ParticipantCreate,
    ParticipantUpdate,
    QueueCreate,
    QueueTemplateCreate,
)
from app.services import ai_service
from app.services.ai_service import AIServiceError, AIServiceUnavailable
from app.services.auth_service import authenticate_organizer, change_password, register_organizer
from app.services.queue_service import QueueService
from app.services.organizer_service import (
    create_template,
    delete_template,
    duplicate_template,
    get_organizer_settings,
    get_template,
    mark_template_used,
    update_organizer_settings,
    update_template,
)
from app.websocket.manager import manager
from app.config import get_settings


router = APIRouter(prefix="/api")


def current_organizer_id(request: Request) -> UUID:
    try:
        return UUID(request.session["organizer_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(401, "Сначала войдите как организатор") from exc


def start_organizer_session(request: Request, organizer: Organizer) -> None:
    request.session.clear()
    request.session.update({"organizer_id": str(organizer.id), "organizer_name": organizer.name})


@router.post("/auth/register", status_code=201)
def register(payload: OrganizerRegister, request: Request, db: Session = Depends(get_db)):
    organizer = register_organizer(db, payload)
    start_organizer_session(request, organizer)
    return {"id": str(organizer.id), "name": organizer.name, "dashboard_url": "/organizer"}


@router.post("/auth/login")
def login(payload: OrganizerLogin, request: Request, db: Session = Depends(get_db)):
    organizer = authenticate_organizer(db, payload.email, payload.password)
    start_organizer_session(request, organizer)
    return {"id": str(organizer.id), "name": organizer.name, "dashboard_url": "/organizer"}


@router.get("/auth/session")
def auth_session(request: Request, db: Session = Depends(get_db)):
    owner_id = current_organizer_id(request)
    organizer = db.get(Organizer, owner_id)
    if organizer is None:
        request.session.clear()
        raise HTTPException(401, "Сессия истекла")
    return {"id": str(organizer.id), "name": organizer.name, "email": organizer.email}


@router.post("/auth/change-password", status_code=204)
def api_change_password(payload: PasswordChange, request: Request, db: Session = Depends(get_db)):
    organizer = db.get(Organizer, current_organizer_id(request))
    if organizer is None:
        raise HTTPException(401, "Сессия истекла")
    change_password(db, organizer, payload.current_password, payload.new_password)
    return Response(status_code=204)


@router.post("/auth/logout")
def logout_organizer(request: Request):
    request.session.clear()
    return {"ok": True, "redirect_url": "/"}


@router.get("/ai/status")
def ai_status():
    return ai_service.provider_status()


@router.get("/notifications")
def notifications(request: Request, db: Session = Depends(get_db)):
    owner_id = current_organizer_id(request)
    preferences = get_organizer_settings(db, owner_id)
    hidden = set()
    if not preferences.notify_new_participant:
        hidden.add("joined")
    if not preferences.notify_queue_finished:
        hidden.add("finished")
    if not preferences.notify_queue_changes:
        hidden.update({"paused", "resumed"})
    return {"events": [event for event in QueueService.recent_events(db, organizer_id=owner_id) if event["kind"] not in hidden]}


@router.post("/ai/parse-queue-description", response_model=AIQueueDraft)
async def parse_ai_queue_description(payload: AIQueueDescriptionRequest, request: Request):
    from datetime import date
    current_organizer_id(request)
    try:
        return await ai_service.parse_queue_description(payload.text.strip(), date.today())
    except AIServiceUnavailable:
        from fastapi import HTTPException
        raise HTTPException(503, "AI-помощник не настроен. Заполните поля вручную.")
    except AIServiceError:
        from fastapi import HTTPException
        raise HTTPException(502, "Не удалось обработать описание. Заполните поля вручную или попробуйте ещё раз.")


@router.post("/queues", status_code=201)
async def create_queue(payload: QueueCreate, request: Request, template_id: UUID | None = None, db: Session = Depends(get_db)):
    owner_id = current_organizer_id(request)
    queue = QueueService.create(db, payload, owner_id)
    if template_id is not None:
        mark_template_used(db, template_id, owner_id)
    root = get_settings().app_url.rstrip("/")
    return {
        "id": str(queue.id),
        "public_code": queue.public_code,
        "public_url": f"{root}/q/{queue.public_code}",
        "management_token": queue.management_token,
        "management_url": f"{root}/manage/{queue.management_token}",
        "created_url": f"{root}/queues/{queue.id}/created?token={queue.management_token}",
    }


@router.delete("/queues/{queue_id}", status_code=204)
def delete_queue(queue_id: UUID, request: Request, db: Session = Depends(get_db)):
    QueueService.delete(db, queue_id, current_organizer_id(request))
    return Response(status_code=204)


def template_dict(value):
    return {
        "id": str(value.id),
        "name": value.name,
        "description": value.description,
        "location": value.location,
        "default_start_time": value.default_start_time.strftime("%H:%M") if value.default_start_time else None,
        "default_end_time": value.default_end_time.strftime("%H:%M") if value.default_end_time else None,
        "max_participants": value.max_participants,
        "allow_join_after_start": value.allow_join_after_start,
        "show_participant_list": value.show_participant_list,
        "participant_instruction": value.participant_instruction,
        "usage_count": value.usage_count,
    }


@router.post("/templates", status_code=201)
def api_create_template(payload: QueueTemplateCreate, request: Request, db: Session = Depends(get_db)):
    return template_dict(create_template(db, payload, current_organizer_id(request)))


@router.put("/templates/{template_id}")
def api_update_template(template_id: UUID, payload: QueueTemplateCreate, request: Request, db: Session = Depends(get_db)):
    return template_dict(update_template(db, template_id, payload, current_organizer_id(request)))


@router.post("/templates/{template_id}/duplicate", status_code=201)
def api_duplicate_template(template_id: UUID, request: Request, db: Session = Depends(get_db)):
    return template_dict(duplicate_template(db, template_id, current_organizer_id(request)))


@router.delete("/templates/{template_id}", status_code=204)
def api_delete_template(template_id: UUID, request: Request, db: Session = Depends(get_db)):
    delete_template(db, template_id, current_organizer_id(request))
    return Response(status_code=204)


@router.get("/templates/{template_id}")
def api_get_template(template_id: UUID, request: Request, db: Session = Depends(get_db)):
    return template_dict(get_template(db, template_id, current_organizer_id(request)))


@router.get("/settings")
def api_get_settings(request: Request, db: Session = Depends(get_db)):
    owner_id = current_organizer_id(request)
    value = get_organizer_settings(db, owner_id)
    result = {key: getattr(value, key) for key in OrganizerSettingsUpdate.model_fields}
    organizer = db.get(Organizer, owner_id)
    result["organizer_name"] = organizer.name
    return result


@router.put("/settings")
def api_update_settings(payload: OrganizerSettingsUpdate, request: Request, db: Session = Depends(get_db)):
    owner_id = current_organizer_id(request)
    value = update_organizer_settings(db, payload, owner_id)
    organizer = db.get(Organizer, owner_id)
    organizer.name = payload.organizer_name
    db.commit()
    request.session["organizer_name"] = organizer.name
    return {key: getattr(value, key) for key in OrganizerSettingsUpdate.model_fields}


@router.get("/queues/{code}")
def queue_state(code: str, db: Session = Depends(get_db)):
    return QueueService.queue_state(db, QueueService.by_code(db, code))


@router.post("/queues/{code}/join", status_code=201)
async def join_queue(code: str, payload: ParticipantCreate, db: Session = Depends(get_db)):
    participant = QueueService.join(db, code, payload)
    await manager.broadcast(code, "participant_joined")
    return {"token": participant.token, "participant": QueueService.participant_dict(participant)}


@router.get("/participants/{token}")
def participant_state(token: str, db: Session = Depends(get_db)):
    participant = QueueService.participant_by_token(db, token)
    return QueueService.participant_state(db, participant)


@router.patch("/participants/{token}")
async def rename_participant(token: str, payload: ParticipantUpdate, db: Session = Depends(get_db)):
    participant = QueueService.rename_participant(db, token, payload.name)
    code = participant.queue.public_code
    await manager.broadcast(code, "participant_updated")
    return QueueService.participant_state(db, participant)


@router.delete("/participants/{token}")
async def cancel_participant(token: str, db: Session = Depends(get_db)):
    queue, participant = QueueService.cancel_participant(db, token)
    await manager.broadcast(queue.public_code, "participant_cancelled")
    return {"ok": True, "participant": QueueService.participant_dict(participant)}


@router.post("/participants/{token}/acknowledge")
async def acknowledge_participant(token: str, db: Session = Depends(get_db)):
    queue, participant = QueueService.acknowledge_participant(db, token)
    await manager.broadcast(queue.public_code, "participant_acknowledged")
    return QueueService.participant_state(db, participant)


@router.get("/manage/{token}")
def management_state(token: str, db: Session = Depends(get_db)):
    queue = QueueService.by_management_token(db, token)
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/next")
async def next_participant(token: str, db: Session = Depends(get_db)):
    queue, called = QueueService.next(db, token)
    await manager.broadcast(queue.public_code, "participant_called" if called else "participant_completed")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/call/{participant_id}")
async def call_participant(token: str, participant_id: str, db: Session = Depends(get_db)):
    queue, _ = QueueService.call(db, token, participant_id)
    await manager.broadcast(queue.public_code, "participant_called")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/skip")
async def skip_current(token: str, db: Session = Depends(get_db)):
    queue, _ = QueueService.skip(db, token)
    await manager.broadcast(queue.public_code, "participant_skipped")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/skip/{participant_id}")
async def skip_participant(token: str, participant_id: str, db: Session = Depends(get_db)):
    queue, _ = QueueService.skip(db, token, participant_id)
    await manager.broadcast(queue.public_code, "participant_skipped")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/restore/{participant_id}")
async def restore_participant(token: str, participant_id: str, db: Session = Depends(get_db)):
    queue = QueueService.restore(db, token, participant_id)
    await manager.broadcast(queue.public_code, "participant_updated")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/pause")
async def pause_queue(token: str, db: Session = Depends(get_db)):
    queue = QueueService.set_status(db, token, QueueStatus.paused)
    await manager.broadcast(queue.public_code, "queue_paused")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/resume")
async def resume_queue(token: str, db: Session = Depends(get_db)):
    queue = QueueService.set_status(db, token, QueueStatus.active)
    await manager.broadcast(queue.public_code, "queue_resumed")
    return QueueService.queue_state(db, queue)


@router.post("/manage/{token}/finish")
async def finish_queue(token: str, db: Session = Depends(get_db)):
    queue = QueueService.set_status(db, token, QueueStatus.finished)
    await manager.broadcast(queue.public_code, "queue_finished")
    return QueueService.queue_state(db, queue)
