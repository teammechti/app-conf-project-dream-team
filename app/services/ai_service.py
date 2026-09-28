import json
from datetime import date

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas.queue import AIQueueDraft


class AIServiceUnavailable(Exception):
    pass


class AIServiceError(Exception):
    pass


QUEUE_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"], "description": "Краткое понятное название очереди"},
        "description": {"type": ["string", "null"], "description": "Краткое описание без новых фактов"},
        "location": {"type": ["string", "null"], "description": "Место в нормализованном виде"},
        "date": {"type": ["string", "null"], "format": "date", "description": "Дата YYYY-MM-DD"},
        "start_time": {"type": ["string", "null"], "description": "Время HH:MM"},
        "end_time": {"type": ["string", "null"], "description": "Время HH:MM"},
        "max_participants": {"type": ["integer", "null"], "minimum": 1, "maximum": 10000},
        "participant_instruction": {"type": ["string", "null"], "description": "Только требования, явно указанные пользователем"},
    },
    "required": ["name", "description", "location", "date", "start_time", "end_time", "max_participants", "participant_instruction"],
    "additionalProperties": False,
}


def _system_prompt(current_date: date) -> str:
    return f"""Ты извлекаешь параметры электронной очереди из русского текста пользователя.
Верни только JSON, строго соответствующий переданной JSON Schema.
Не придумывай значения, которых нет в тексте. Если значение не указано — верни null.
Название сделай кратким и понятным. Описание можно аккуратно нормализовать без добавления фактов.
Инструкцию можно переформулировать яснее, но нельзя добавлять новые требования.
Текущая дата: {current_date.isoformat()}.
Интерпретируй сегодня, завтра, послезавтра и дни недели относительно этой даты.
Не создавай очередь и не принимай решений о порядке участников."""


def provider_status(settings: Settings | None = None) -> dict[str, str | bool]:
    """Return the currently usable provider without making app startup depend on it."""
    config = settings or get_settings()
    if config.llm_api_key and config.qwen_base_url:
        return {"available": True, "provider": "Qwen Model Studio", "model": config.qwen_model}
    try:
        response = httpx.get(f"{config.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5)
        response.raise_for_status()
        models = {item.get("name") for item in response.json().get("models", [])}
        if config.ollama_model in models:
            return {"available": True, "provider": "Ollama", "model": config.ollama_model}
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        pass
    return {"available": False, "provider": "Qwen", "model": config.ollama_model}


async def _parse_with_ollama(text: str, current_date: date, config: Settings) -> AIQueueDraft:
    payload = {
        "model": config.ollama_model,
        "messages": [
            {"role": "system", "content": _system_prompt(current_date)},
            {"role": "user", "content": text},
        ],
        "format": QUEUE_DRAFT_SCHEMA,
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    try:
        async with httpx.AsyncClient(timeout=config.qwen_timeout_seconds) as client:
            response = await client.post(f"{config.ollama_base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        return AIQueueDraft.model_validate(json.loads(content))
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AIServiceError("Локальная модель Qwen вернула некорректный ответ") from exc


async def parse_queue_description(text: str, current_date: date, settings: Settings | None = None) -> AIQueueDraft:
    config = settings or get_settings()
    if not config.llm_api_key or not config.qwen_base_url:
        status = provider_status(config)
        if status["available"] and status["provider"] == "Ollama":
            return await _parse_with_ollama(text, current_date, config)
        raise AIServiceUnavailable("Qwen не настроен")
    payload = {
        "model": config.qwen_model,
        "messages": [
            {"role": "system", "content": _system_prompt(current_date)},
            {"role": "user", "content": text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "queue_draft", "strict": True, "schema": QUEUE_DRAFT_SCHEMA},
        },
        "enable_thinking": False,
    }
    try:
        async with httpx.AsyncClient(timeout=config.qwen_timeout_seconds) as client:
            response = await client.post(
                f"{config.qwen_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {config.llm_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return AIQueueDraft.model_validate(json.loads(content))
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AIServiceError("Qwen вернул некорректный ответ") from exc
