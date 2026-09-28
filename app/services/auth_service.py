from datetime import datetime, timezone

from fastapi import HTTPException
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Organizer
from app.schemas.queue import OrganizerRegister


password_hash = PasswordHash.recommended()


def register_organizer(db: Session, payload: OrganizerRegister) -> Organizer:
    existing = db.scalar(select(Organizer).where(Organizer.email == payload.email))
    if existing is not None:
        raise HTTPException(409, "Аккаунт с такой почтой уже существует")
    organizer = Organizer(
        name=payload.name,
        email=payload.email,
        password_hash=password_hash.hash(payload.password),
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)
    return organizer


def authenticate_organizer(db: Session, email: str, password: str) -> Organizer:
    organizer = db.scalar(select(Organizer).where(Organizer.email == email))
    valid = organizer is not None and organizer.password_hash is not None and password_hash.verify(password, organizer.password_hash)
    if not valid:
        raise HTTPException(401, "Неверная почта или пароль")
    organizer.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return organizer


def change_password(db: Session, organizer: Organizer, current_password: str, new_password: str) -> None:
    if organizer.password_hash is None or not password_hash.verify(current_password, organizer.password_hash):
        raise HTTPException(400, "Текущий пароль указан неверно")
    if password_hash.verify(new_password, organizer.password_hash):
        raise HTTPException(400, "Новый пароль должен отличаться от текущего")
    organizer.password_hash = password_hash.hash(new_password)
    db.commit()
