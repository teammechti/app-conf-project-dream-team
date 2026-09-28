import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB = Path(__file__).with_name("test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["AUTO_CREATE_TABLES"] = "false"

from app.db.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as value:
        response = value.post("/api/auth/register", json={
            "name": "Тестовый организатор",
            "email": "organizer@example.com",
            "password": "Testpass123",
            "accept_terms": True,
        })
        assert response.status_code == 201
        yield value


@pytest.fixture
def queue_payload():
    return {
        "name": "Тестовая очередь",
        "description": "Описание",
        "location": "Ауд. 100",
        "date": "2030-05-12",
        "start_time": "10:00",
        "end_time": "18:00",
        "max_participants": 3,
        "allow_join_after_start": True,
        "show_participant_list": True,
        "participant_instruction": "Ожидайте вызова",
    }


@pytest.fixture
def created_queue(client, queue_payload):
    response = client.post("/api/queues", json=queue_payload)
    assert response.status_code == 201
    return response.json()
