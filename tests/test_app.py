def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "0.5.1", "team": "Dream Team"}


def test_registration_login_and_persistent_session():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as browser:
        landing = browser.get("/")
        assert "Войти или зарегистрироваться" in landing.text
        created = browser.post("/api/auth/register", json={
            "name": "Новый организатор", "email": "new@example.com",
            "password": "Strongpass1", "accept_terms": True,
        })
        assert created.status_code == 201
        assert browser.get("/organizer").status_code == 200
        assert browser.get("/api/auth/session").json()["email"] == "new@example.com"
        browser.post("/api/auth/logout")
        assert browser.get("/organizer", follow_redirects=False).status_code == 303
        assert browser.post("/api/auth/login", json={"email": "NEW@example.com", "password": "Strongpass1"}).status_code == 200


def test_registration_rejects_duplicate_email_and_weak_password():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as browser:
        payload = {"name": "Организатор", "email": "owner@example.com", "password": "Password1", "accept_terms": True}
        assert browser.post("/api/auth/register", json=payload).status_code == 201
        assert browser.post("/api/auth/register", json=payload).status_code == 409
        weak = payload | {"email": "weak@example.com", "password": "password"}
        assert browser.post("/api/auth/register", json=weak).status_code == 422


def test_password_change_invalidates_old_password(client):
    assert client.post("/api/auth/change-password", json={"current_password": "Testpass123", "new_password": "Changedpass2"}).status_code == 204
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "organizer@example.com", "password": "Testpass123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "organizer@example.com", "password": "Changedpass2"}).status_code == 200


def test_landing_and_legal_pages_render(client):
    assert "Как вы хотите использовать QueueManager?" in client.get("/").text
    assert "Политика конфиденциальности" in client.get("/privacy").text
    assert "Пользовательское соглашение" in client.get("/terms").text


def test_create_queue(client, queue_payload):
    response = client.post("/api/queues", json=queue_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["public_code"]
    assert data["management_token"]
    assert client.get(f"/api/queues/{data['public_code']}").json()["name"] == queue_payload["name"]


def test_create_queue_validation(client, queue_payload):
    queue_payload["end_time"] = "09:00"
    response = client.post("/api/queues", json=queue_payload)
    assert response.status_code == 422


def test_create_queue_without_place_or_schedule(client, queue_payload):
    for field in ("location", "date", "start_time", "end_time"):
        queue_payload[field] = None
    response = client.post("/api/queues", json=queue_payload)
    assert response.status_code == 201
    created = response.json()
    state = client.get(f"/api/queues/{created['public_code']}").json()
    assert state["location"] is None
    assert state["date"] is None
    assert state["start_time"] is None
    assert state["end_time"] is None
    for path in (created["created_url"], created["management_url"], created["public_url"], "/organizer", "/statistics"):
        page = client.get(path)
        assert page.status_code == 200


def test_join_queue_and_number_generation(client, created_queue):
    first = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Анна"})
    second = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Иван"})
    assert first.status_code == second.status_code == 201
    assert first.json()["participant"]["number"] == "A-001"
    assert second.json()["participant"]["number"] == "A-002"


def test_participant_restore_and_rename(client, created_queue):
    joined = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Анна"}).json()
    state = client.get(f"/api/participants/{joined['token']}")
    assert state.status_code == 200
    assert state.json()["participant"]["number"] == "A-001"
    renamed = client.patch(f"/api/participants/{joined['token']}", json={"name": "Анна Петрова"})
    assert renamed.json()["participant"]["name"] == "Анна Петрова"


def test_full_queue(client, created_queue):
    for name in ("Первый", "Второй", "Третий"):
        assert client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": name}).status_code == 201
    response = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Четвёртый"})
    assert response.status_code == 409


def test_next_skip_pause_resume_and_no_two_called(client, created_queue):
    participants = []
    for name in ("Первый", "Второй", "Третий"):
        participants.append(client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": name}).json()["participant"])
    token = created_queue["management_token"]
    state = client.post(f"/api/manage/{token}/next").json()
    assert state["called"]["number"] == "A-001"
    state = client.post(f"/api/manage/{token}/call/{participants[2]['id']}").json()
    assert state["called"]["number"] == "A-003"
    assert sum(p["status"] == "called" for p in state["all_participants"]) == 1
    state = client.post(f"/api/manage/{token}/skip").json()
    assert state["counts"]["skipped"] == 1
    assert client.post(f"/api/manage/{token}/pause").json()["status"] == "paused"
    assert client.post(f"/api/manage/{token}/resume").json()["status"] == "active"


def test_participant_restore_from_skipped(client, created_queue):
    participant = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Первый"}).json()["participant"]
    token = created_queue["management_token"]
    client.post(f"/api/manage/{token}/skip/{participant['id']}")
    state = client.post(f"/api/manage/{token}/restore/{participant['id']}")
    assert state.status_code == 200
    assert state.json()["counts"]["waiting"] == 1


def test_cancel_participant(client, created_queue):
    joined = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Анна"}).json()
    response = client.delete(f"/api/participants/{joined['token']}")
    assert response.status_code == 200
    assert response.json()["participant"]["status"] == "cancelled"


def test_finish_prevents_join(client, created_queue):
    token = created_queue["management_token"]
    state = client.post(f"/api/manage/{token}/finish")
    assert state.status_code == 200
    assert state.json()["status"] == "finished"
    response = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Опоздавший"})
    assert response.status_code == 409


def test_ai_parse_full_description(client, monkeypatch):
    from datetime import date, time
    from app.schemas.queue import AIQueueDraft
    from app.services import ai_service

    async def fake_parse(text, current_date):
        assert "Защита лабораторных" in text
        return AIQueueDraft(name="Защита лабораторных работ", description="Очередь для защиты лабораторных работ", location="Ауд. 401", date=date(2026, 9, 28), start_time=time(10), end_time=time(16), max_participants=25, participant_instruction=None)

    monkeypatch.setattr(ai_service, "parse_queue_description", fake_parse)
    response = client.post("/api/ai/parse-queue-description", json={"text": "Защита лабораторных завтра с 10 до 16 в 401 аудитории, максимум 25 человек"})
    assert response.status_code == 200
    assert response.json()["max_participants"] == 25
    assert response.json()["date"] == "2026-09-28"


def test_ai_parse_partial_description(client, monkeypatch):
    from app.schemas.queue import AIQueueDraft
    from app.services import ai_service

    async def fake_parse(text, current_date):
        return AIQueueDraft(name="Консультация по курсовым", description=None, location="Ауд. 305", date=None, start_time=None, end_time=None, max_participants=None, participant_instruction=None)

    monkeypatch.setattr(ai_service, "parse_queue_description", fake_parse)
    data = client.post("/api/ai/parse-queue-description", json={"text": "Консультация по курсовым в 305 аудитории"}).json()
    assert data["location"] == "Ауд. 305"
    assert data["date"] is None
    assert data["start_time"] is None and data["end_time"] is None


def test_ai_service_failure(client, monkeypatch):
    from app.services import ai_service

    async def fail(text, current_date):
        raise ai_service.AIServiceError("provider failed")

    monkeypatch.setattr(ai_service, "parse_queue_description", fail)
    response = client.post("/api/ai/parse-queue-description", json={"text": "Любое корректное описание"})
    assert response.status_code == 502
    assert "Заполните поля вручную" in response.json()["detail"]


def test_ai_empty_text(client):
    response = client.post("/api/ai/parse-queue-description", json={"text": ""})
    assert response.status_code == 422


def test_ai_parse_requires_organizer_session():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as anonymous:
        response = anonymous.post(
            "/api/ai/parse-queue-description",
            json={"text": "Консультация завтра"},
        )
        assert response.status_code == 401


def test_qr_is_unique_for_each_queue(client, queue_payload):
    first = client.post("/api/queues", json=queue_payload).json()
    queue_payload["name"] = "Вторая очередь"
    second = client.post("/api/queues", json=queue_payload).json()
    first_qr = client.get(f"/q/{first['public_code']}/qr")
    second_qr = client.get(f"/q/{second['public_code']}/qr")
    assert first_qr.status_code == second_qr.status_code == 200
    assert first_qr.headers["content-type"] == "image/png"
    assert first_qr.content.startswith(b"\x89PNG")
    assert first_qr.content != second_qr.content


def test_public_links_and_qr_use_configured_app_url(client, queue_payload, monkeypatch):
    from app import main
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_url", "https://queuemanager.duckdns.org")
    original_make = main.qrcode.make
    captured = {}

    def capture_qr_target(target):
        captured["target"] = target
        return original_make(target)

    monkeypatch.setattr(main.qrcode, "make", capture_qr_target)
    created = client.post("/api/queues", json=queue_payload).json()
    assert created["public_url"].startswith("https://queuemanager.duckdns.org/q/")
    assert created["management_url"].startswith("https://queuemanager.duckdns.org/manage/")
    page = client.get(f"/queues/{created['id']}/created?token={created['management_token']}")
    assert created["public_url"] in page.text
    assert client.get(f"/q/{created['public_code']}/qr").status_code == 200
    assert captured["target"] == created["public_url"]


def test_public_logo_does_not_link_to_organizer(client, created_queue):
    page = client.get(f"/q/{created_queue['public_code']}")
    assert page.status_code == 200
    assert 'class="brand public-brand"' in page.text
    assert 'class="brand" href="/"' not in page.text


def test_template_crud_and_queue_prefill(client):
    payload = {
        "name": "Выдача справок", "description": "Получение справок", "location": "Каб. 102",
        "default_start_time": "09:00", "default_end_time": "12:00", "max_participants": 40,
        "allow_join_after_start": True, "show_participant_list": False, "participant_instruction": "Возьмите паспорт",
    }
    created = client.post("/api/templates", json=payload)
    assert created.status_code == 201
    template_id = created.json()["id"]
    page = client.get(f"/queues/new?template={template_id}")
    assert page.status_code == 200
    assert 'value="09:00"' in page.text
    assert "Каб. 102" in page.text
    duplicated = client.post(f"/api/templates/{template_id}/duplicate")
    assert duplicated.status_code == 201
    assert "копия" in duplicated.json()["name"]
    assert client.delete(f"/api/templates/{template_id}").status_code == 204


def test_settings_are_persisted(client):
    payload = {
        "organizer_name": "Ирина Волкова", "timezone": "Europe/Moscow",
        "notify_new_participant": False, "notify_queue_finished": True, "notify_queue_changes": True,
        "default_max_participants": 24, "default_show_participant_list": False,
        "default_allow_join_after_start": True,
    }
    assert client.put("/api/settings", json=payload).status_code == 200
    saved = client.get("/api/settings").json()
    assert saved["organizer_name"] == "Ирина Волкова"
    assert saved["default_max_participants"] == 24


def test_statistics_and_new_screens_render(client, created_queue):
    for path in ("/templates", "/templates/new", "/statistics", "/settings"):
        response = client.get(path)
        assert response.status_code == 200
    page = client.get("/statistics?period=month")
    assert 'data-period="month" class="active"' in page.text
    assert client.get("/statistics?period=month&queue=").status_code == 200
    assert client.get("/statistics?period=today&queue=").status_code == 200


def test_participant_acknowledgement_and_event_log(client, created_queue):
    joined = client.post(
        f"/api/queues/{created_queue['public_code']}/join", json={"name": "Алексей"}
    ).json()
    client.post(f"/api/manage/{created_queue['management_token']}/next")
    response = client.post(f"/api/participants/{joined['token']}/acknowledge")
    assert response.status_code == 200
    assert response.json()["participant"]["acknowledged_at"] is not None
    state = client.get(f"/api/manage/{created_queue['management_token']}").json()
    assert state["called"]["name"] == "Алексей"
    assert state["called"]["acknowledged_at"] is not None
    kinds = [event["kind"] for event in state["recent_events"]]
    assert kinds[:3] == ["acknowledged", "called", "joined"]
    assert "Я иду" in state["recent_events"][0]["message"]


def test_notifications_return_real_queue_events(client, created_queue):
    client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Мария"})
    events = client.get("/api/notifications").json()["events"]
    assert events[0]["kind"] == "joined"
    assert "Мария" in events[0]["message"]
    assert events[0]["queue_name"] == "Тестовая очередь"


def test_finished_queue_keeps_participants_and_action_history(client, created_queue):
    first = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Анна"}).json()
    second = client.post(f"/api/queues/{created_queue['public_code']}/join", json={"name": "Иван"}).json()
    token = created_queue["management_token"]
    client.post(f"/api/manage/{token}/next")
    client.post(f"/api/manage/{token}/next")
    client.post(f"/api/manage/{token}/skip")
    client.post(f"/api/manage/{token}/finish")

    page = client.get(f"/manage/{token}")
    assert page.status_code == 200
    assert "История действий" in page.text
    assert "Участники очереди" in page.text
    assert first["participant"]["name"] in page.text
    assert second["participant"]["name"] in page.text
    assert "Обслуживание завершено" in page.text
    assert "Пропущен" in page.text
    assert "Очередь завершена" in page.text


def test_organizer_can_delete_only_own_queue(client, created_queue):
    from fastapi.testclient import TestClient
    from app.main import app

    queue_id = created_queue["id"]
    with TestClient(app) as other:
        other.post("/api/auth/register", json={
            "name": "Другой организатор", "email": "other@example.com",
            "password": "Otherpass123", "accept_terms": True,
        })
        assert other.delete(f"/api/queues/{queue_id}").status_code == 404

    dashboard = client.get("/organizer")
    assert f'data-delete-queue="{queue_id}"' in dashboard.text
    assert client.delete(f"/api/queues/{queue_id}").status_code == 204
    assert client.get(created_queue["public_url"]).status_code == 404
    assert client.get(created_queue["management_url"]).status_code == 404


def test_statistics_metrics_are_calculated_from_participants(client, created_queue):
    from datetime import datetime, timedelta, timezone
    from uuid import UUID

    from sqlalchemy import select

    from app.db.database import SessionLocal
    from app.models.entities import Participant, ParticipantStatus
    from app.services.organizer_service import statistics

    joined = client.post(
        f"/api/queues/{created_queue['public_code']}/join", json={"name": "Расчёт статистики"}
    ).json()["participant"]
    with SessionLocal() as db:
        participant = db.scalar(select(Participant).where(Participant.id == UUID(joined["id"])))
        now = datetime.now(timezone.utc)
        participant.joined_at = now - timedelta(minutes=10)
        participant.called_at = now - timedelta(minutes=5)
        participant.completed_at = now
        participant.status = ParticipantStatus.completed
        db.commit()
        result = statistics(db, "today")
    assert result["total"] == 1
    assert result["completed"] == 1
    assert result["average_wait_seconds"] == 300
    assert result["average_service_seconds"] == 300
    assert sum(result["points"]) == 1
    assert len(result["points"]) == 12
