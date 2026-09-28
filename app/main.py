from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import UUID

import qrcode
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.config import get_settings
from app.db.database import Base, engine, get_db
from app.models.entities import Organizer, Queue
from app.services.queue_service import QueueService
from app.services.organizer_service import get_organizer_settings, get_template, list_templates, statistics
from app.services.ai_service import provider_status
from app.websocket.manager import manager


BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="QueueManager",
    description="Сервис управления электронной очередью",
    version=settings.version,
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="qm_session",
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.secure_cookies,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def queue_schedule(queue: Queue) -> str:
    parts: list[str] = []
    if queue.date:
        parts.append(queue.date.strftime("%d.%m.%Y"))
    if queue.start_time and queue.end_time:
        parts.append(f'{queue.start_time.strftime("%H:%M")} – {queue.end_time.strftime("%H:%M")}')
    elif queue.start_time:
        parts.append(f'с {queue.start_time.strftime("%H:%M")}')
    elif queue.end_time:
        parts.append(f'до {queue.end_time.strftime("%H:%M")}')
    return ", ".join(parts) or "Время не указано"


templates.env.filters["queue_schedule"] = queue_schedule
app.include_router(api_router)


def context(request: Request, **values):
    return {
        "request": request,
        "version": settings.version,
        "organizer_name": request.session.get("organizer_name", "Организатор"),
        "authenticated": bool(request.session.get("organizer_id")),
        "legal_operator_name": settings.legal_operator_name,
        "legal_contact_email": settings.legal_contact_email,
        "app_url": settings.app_url.rstrip("/"),
        **values,
    }


def organizer_id(request: Request) -> UUID | None:
    try:
        return UUID(request.session["organizer_id"])
    except (KeyError, ValueError, TypeError):
        return None


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", context(request))


@app.get("/organizer", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("organizer/dashboard.html", context(request, dashboard=QueueService.dashboard(db, owner_id)))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": settings.version, "team": "Dream Team"}


@app.get("/queues/new", response_class=HTMLResponse)
def create_queue_page(request: Request, template: UUID | None = None, db: Session = Depends(get_db)):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    queue_template = get_template(db, template, owner_id) if template else None
    organizer_settings = get_organizer_settings(db, owner_id)
    return templates.TemplateResponse(
        "organizer/create.html",
        context(request, queue_template=queue_template, organizer_settings=organizer_settings),
    )


@app.get("/templates", response_class=HTMLResponse)
def templates_page(request: Request, db: Session = Depends(get_db)):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("organizer/templates.html", context(request, queue_templates=list_templates(db, owner_id)))


@app.get("/templates/new", response_class=HTMLResponse)
def template_create_page(request: Request):
    if organizer_id(request) is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("organizer/template_form.html", context(request, queue_template=None))


@app.get("/templates/{template_id}/edit", response_class=HTMLResponse)
def template_edit_page(template_id: UUID, request: Request, db: Session = Depends(get_db)):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "organizer/template_form.html", context(request, queue_template=get_template(db, template_id, owner_id))
    )


@app.get("/statistics", response_class=HTMLResponse)
def statistics_page(
    request: Request,
    period: str = "week",
    queue: str | None = None,
    db: Session = Depends(get_db),
):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    try:
        queue_id = UUID(queue) if queue else None
    except ValueError as exc:
        raise HTTPException(400, "Некорректный идентификатор очереди") from exc
    return templates.TemplateResponse(
        "organizer/statistics.html", context(request, stats=statistics(db, period, queue_id, owner_id))
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    owner_id = organizer_id(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    organizer = db.get(Organizer, owner_id)
    if organizer is None:
        request.session.clear()
        return RedirectResponse("/", status_code=303)
    ai_status = provider_status()
    return templates.TemplateResponse(
        "organizer/settings.html",
        context(request, organizer=organizer, organizer_settings=get_organizer_settings(db, owner_id), ai_available=ai_status["available"], ai_provider=ai_status["provider"], qwen_model=ai_status["model"]),
    )


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse("legal/privacy.html", context(request))


@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse("legal/terms.html", context(request))


@app.get("/queues/{queue_id}/created", response_class=HTMLResponse)
def queue_created(queue_id: UUID, token: str, request: Request, db: Session = Depends(get_db)):
    queue = db.get(Queue, queue_id)
    if queue is None or queue.management_token != token:
        raise HTTPException(404, "Очередь не найдена")
    return templates.TemplateResponse("organizer/created.html", context(request, queue=queue))


@app.get("/manage/{token}", response_class=HTMLResponse)
def manage_queue(token: str, request: Request, db: Session = Depends(get_db)):
    queue = QueueService.by_management_token(db, token)
    state = QueueService.queue_state(db, queue)
    template = "organizer/finished.html" if queue.status.value == "finished" else "organizer/manage.html"
    owner = db.get(Organizer, queue.organizer_id) if queue.organizer_id else None
    return templates.TemplateResponse(template, context(request, queue=queue, state=state, queue_organizer_name=owner.name if owner else "Организатор"))


@app.get("/q/{code}", response_class=HTMLResponse)
def public_queue(code: str, request: Request, db: Session = Depends(get_db)):
    queue = QueueService.by_code(db, code)
    state = QueueService.queue_state(db, queue)
    owner = db.get(Organizer, queue.organizer_id) if queue.organizer_id else None
    return templates.TemplateResponse("participant/public.html", context(request, queue=queue, state=state, queue_organizer_name=owner.name if owner else "Организатор"))


@app.get("/q/{code}/qr")
def queue_qr(code: str, request: Request, db: Session = Depends(get_db)):
    QueueService.by_code(db, code)
    target = f"{settings.app_url.rstrip('/')}/q/{code}"
    image = qrcode.make(target)
    output = BytesIO()
    image.save(output, format="PNG")
    return Response(output.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.websocket("/ws/queues/{code}")
async def websocket_queue(websocket: WebSocket, code: str):
    await manager.connect(code, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(code, websocket)
