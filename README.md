# QueueManager

Инструкция для сервера с доменом и HTTPS: [DEPLOYMENT.md](DEPLOYMENT.md).

Пошаговая инструкция для установки на чистую Ubuntu: [SERVER_SETUP_RU.md](SERVER_SETUP_RU.md).

Рабочее веб-приложение для электронной очереди: организатор создаёт очередь и управляет вызовами, участники присоединяются без регистрации и получают обновления в реальном времени.

## Команда

- Иван — Team Lead / Backend Developer;
- Олег — Tech Lead;
- Егор — DevOps;
- Алексей — Backend Developer.

## Стек технологий

- Python 3.12, FastAPI, Pydantic;
- SQLAlchemy 2, Alembic, PostgreSQL 16;
- Jinja2, HTML5, CSS3, JavaScript;
- WebSocket;
- Ollama и Qwen3 8B;
- Docker, Docker Compose, Caddy и HTTPS;
- pytest и GitHub Actions.

## Возможности

- создание очереди с live preview и серверной валидацией;
- публичная ссылка и настоящий QR-код;
- сохранение состояния в PostgreSQL через SQLAlchemy 2;
- последовательные номера `A-001`, `A-002`, …;
- атомарные действия `Следующий`, `Вызвать`, `Пропустить`, `Вернуть`, `Пауза`, `Завершить`;
- восстановление участника после обновления страницы по локальному token;
- WebSocket-обновления с переподключением и полной синхронизацией состояния;
- desktop- и mobile-компоновки, custom toast/modal, анимация вызова;
- необязательный Qwen-помощник, который извлекает черновик полей из обычного русского описания;
- Alembic-миграции, Docker Compose и pytest.

## Запуск через Docker

Требуется Docker Desktop с Compose.

```bash
docker compose up --build
```

Откройте `http://localhost:8000`. При первом запуске применятся миграции и будет создана пустая рабочая база. Организатор регистрируется через главную страницу и создаёт свои очереди.

Остановка:

```bash
docker compose down
```

Данные PostgreSQL остаются в named volume `postgres-data`. Для полного удаления данных используйте `docker compose down -v` только если они больше не нужны.

## Qwen AI-помощник

Основная очередь не зависит от LLM. Без ключа всё приложение, формы и deterministic-логика продолжают работать; в AI-модальном окне отображается понятный статус недоступности.

Для включения помощника задайте backend-переменные окружения:

```env
LLM_API_KEY=ваш_ключ_Model_Studio
QWEN_BASE_URL=https://WORKSPACE_ID.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.7-plus
```

Вместо `LLM_API_KEY` также поддерживается стандартное имя Alibaba Cloud `DASHSCOPE_API_KEY`.

Base URL зависит от региона и workspace Alibaba Cloud Model Studio. Ключ никогда не отправляется в браузер. Backend вызывает OpenAI-compatible Chat Completions Qwen со строгим JSON Schema, затем повторно валидирует ответ через `AIQueueDraft`. AI только предлагает черновик; очередь создаётся исключительно обычной кнопкой после проверки организатором.

## Локальный запуск с PostgreSQL

1. Создайте Python 3.12 virtual environment и установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Скопируйте `.env.example` в `.env` и укажите доступный `DATABASE_URL`.
3. Примените миграцию, добавьте demo seed и запустите сервер:

```bash
alembic upgrade head
python -m app.seed_demo
uvicorn app.main:app --reload
```

## API совместимости

- `GET /` — главная HTML-страница с выбором роли;
- `GET /health` — `200 {"status":"ok"}`;
- `GET /version` — `{"version":"0.5.1","team":"Dream Team"}`.

Основные JSON-маршруты находятся под `/api`, WebSocket: `/ws/queues/{public_code}`. Интерактивная схема доступна на `/docs`.

## Тесты

```bash
pytest -q
```

Тесты используют отдельную временную SQLite-базу как изолированный тестовый адаптер. Основной runtime и Docker работают только с PostgreSQL.

## Структура

- `app/models` — SQLAlchemy-модели;
- `app/services` — транзакционная бизнес-логика;
- `app/api` — JSON API;
- `app/websocket` — диспетчер realtime-соединений;
- `app/templates`, `app/static` — Jinja UI, CSS и ES modules;
- `alembic` — миграции;
- `tests` — функциональные API-тесты;
