"""Роуты встреч: создание с проверкой конфликтов и просмотр расписания."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.schemas import (
    ConflictDetail,
    ConflictError,
    MeetingCreate,
    MeetingOut,
    to_naive_utc,
)

router = APIRouter(tags=["meetings"])

DbSession = Annotated[Session, Depends(get_db)]


def _conflict_body(error: crud.MeetingConflict) -> dict[str, object]:
    """Собрать человекочитаемое тело 409: кто именно и когда занят."""
    details = [ConflictDetail.model_validate(c) for c in error.conflicts]
    message = "; ".join(
        f"{d.employee_name} занят(а): «{d.meeting_title}» "
        f"{d.starts_at.isoformat()}–{d.ends_at.isoformat()}"
        for d in details
    )
    body = ConflictError(message=message, conflicts=details)
    return body.model_dump(mode="json")


@router.post(
    "/meetings",
    response_model=MeetingOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ConflictError}},
)
def create_meeting(payload: MeetingCreate, db: DbSession) -> MeetingOut:
    """Создать встречу. 409 при конфликте, 422 при неизвестном участнике."""
    try:
        meeting = crud.create_meeting(db, payload)
    except crud.ParticipantNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except crud.MeetingConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_conflict_body(exc)
        ) from exc
    return MeetingOut.model_validate(meeting)


@router.get("/meetings", response_model=list[MeetingOut])
def get_schedule(
    db: DbSession,
    start: Annotated[datetime, Query(description="Начало окна (ISO-8601, UTC)")],
    end: Annotated[datetime, Query(description="Конец окна (ISO-8601, UTC)")],
    employee_id: Annotated[
        int | None, Query(description="Фильтр: только встречи этого сотрудника")
    ] = None,
) -> list[MeetingOut]:
    """Расписание за окно `[start, end)` (день/неделю) с опц. фильтром."""
    meetings = crud.get_schedule(
        db, to_naive_utc(start), to_naive_utc(end), employee_id
    )
    return [MeetingOut.model_validate(m) for m in meetings]
