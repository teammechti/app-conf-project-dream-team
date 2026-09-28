from datetime import date as DateValue, time as TimeValue

from pydantic import BaseModel, Field, field_validator, model_validator


class QueueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    location: str | None = Field(default=None, min_length=2, max_length=200)
    date: DateValue | None = None
    start_time: TimeValue | None = None
    end_time: TimeValue | None = None
    max_participants: int = Field(gt=0, le=10000)
    allow_join_after_start: bool = True
    show_participant_list: bool = True
    participant_instruction: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("Время окончания должно быть позже времени начала")
        return self

    @field_validator("location", mode="before")
    @classmethod
    def blank_location_is_none(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class OrganizerOnboarding(BaseModel):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Введите имя организатора")
        return value


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or value.count("@") != 1:
        raise ValueError("Введите корректный адрес электронной почты")
    local, domain = value.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Введите корректный адрес электронной почты")
    return value


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Пароль должен содержать не менее 8 символов")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Добавьте в пароль хотя бы одну букву и одну цифру")
    return value


class OrganizerRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str
    password: str = Field(max_length=128)
    accept_terms: bool

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return OrganizerOnboarding(name=value).name

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def terms_are_required(self):
        if not self.accept_terms:
            raise ValueError("Для регистрации примите пользовательское соглашение и политику конфиденциальности")
        return self


class OrganizerLogin(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password(value)


class ParticipantUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class AIQueueDescriptionRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Описание не может быть пустым")
        return value


class AIQueueDraft(BaseModel):
    name: str | None = Field(max_length=100)
    description: str | None = Field(max_length=500)
    location: str | None = Field(max_length=200)
    date: DateValue | None
    start_time: TimeValue | None
    end_time: TimeValue | None
    max_participants: int | None = Field(default=None, gt=0, le=10000)
    participant_instruction: str | None = Field(max_length=1000)


class QueueTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=200)
    default_start_time: TimeValue | None = None
    default_end_time: TimeValue | None = None
    max_participants: int = Field(default=50, gt=0, le=10000)
    allow_join_after_start: bool = True
    show_participant_list: bool = True
    participant_instruction: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_default_times(self):
        if bool(self.default_start_time) != bool(self.default_end_time):
            raise ValueError("Укажите оба значения времени или оставьте оба пустыми")
        if self.default_start_time and self.default_start_time >= self.default_end_time:
            raise ValueError("Время окончания должно быть позже времени начала")
        return self


class OrganizerSettingsUpdate(BaseModel):
    organizer_name: str = Field(min_length=2, max_length=100)
    timezone: str = Field(min_length=2, max_length=64)
    notify_new_participant: bool = True
    notify_queue_finished: bool = True
    notify_queue_changes: bool = False
    default_max_participants: int = Field(default=50, gt=0, le=10000)
    default_show_participant_list: bool = True
    default_allow_join_after_start: bool = True
