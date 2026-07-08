"""Pydantic-схемы ввода/вывода API.

Соглашение по времени: на входе принимаем ISO-8601 (aware или naive); нормализуем
к naive UTC для хранения/сравнения. На выходе отдаём aware UTC (суффикс +00:00).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    field_validator,
    model_validator,
)


def to_naive_utc(dt: datetime) -> datetime:
    """Привести datetime к naive UTC. Naive-вход считаем уже в UTC."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _as_aware_utc(dt: datetime) -> datetime:
    """Пометить naive datetime как UTC для сериализации на выходе."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class EmployeeOut(BaseModel):
    """Сотрудник в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MeetingCreate(BaseModel):
    """Тело запроса на создание встречи."""

    title: str
    starts_at: datetime
    ends_at: datetime
    participant_ids: list[int]

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title не может быть пустым")
        return v.strip()

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _normalize_utc(cls, v: datetime) -> datetime:
        return to_naive_utc(v)

    @field_validator("participant_ids")
    @classmethod
    def _min_two_unique(cls, v: list[int]) -> list[int]:
        unique = list(dict.fromkeys(v))
        if len(unique) < 2:
            raise ValueError("встреча должна иметь не менее двух участников")
        return unique

    @model_validator(mode="after")
    def _starts_before_ends(self) -> MeetingCreate:
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at должен быть строго раньше ends_at")
        return self


class MeetingOut(BaseModel):
    """Встреча в ответах API (с участниками)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    participants: list[EmployeeOut]

    @field_serializer("starts_at", "ends_at")
    def _serialize_utc(self, dt: datetime) -> datetime:
        return _as_aware_utc(dt)


class ConflictDetail(BaseModel):
    """Один конфликт: кто занят и когда."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    employee_name: str
    meeting_id: int
    meeting_title: str
    starts_at: datetime
    ends_at: datetime

    @field_serializer("starts_at", "ends_at")
    def _serialize_utc(self, dt: datetime) -> datetime:
        return _as_aware_utc(dt)


class ConflictError(BaseModel):
    """Тело ответа при отказе 409."""

    message: str
    conflicts: list[ConflictDetail]
