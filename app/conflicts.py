"""Ядро задачи: семантика пересечения интервалов и поиск конфликтов.

Интервалы полуоткрытые `[starts_at, ends_at)`. Встречи впритык не конфликтуют.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, Meeting, meeting_participants


def intervals_overlap(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    """Пересекаются ли полуоткрытые интервалы `[s1, e1)` и `[s2, e2)`.

    Два интервала пересекаются ⟺ ``s1 < e2 AND s2 < e1``. Встречи впритык
    (конец одной равен началу другой) НЕ считаются пересечением.
    """
    return s1 < e2 and s2 < e1


@dataclass(frozen=True)
class Conflict:
    """Кто именно и когда занят — для отказа 409."""

    employee_id: int
    employee_name: str
    meeting_id: int
    meeting_title: str
    starts_at: datetime
    ends_at: datetime


def find_conflicts(
    db: Session,
    participant_ids: Sequence[int],
    starts_at: datetime,
    ends_at: datetime,
    exclude_meeting_id: int | None = None,
) -> list[Conflict]:
    """Найти встречи, в которых кто-то из участников занят в интервале.

    Кандидаты отбираются одним запросом по правилу пересечения
    (``Meeting.starts_at < ends_at AND starts_at < Meeting.ends_at``),
    ограниченному участниками ``participant_ids``.
    """
    stmt = (
        select(Meeting, Employee)
        .join(
            meeting_participants,
            meeting_participants.c.meeting_id == Meeting.id,
        )
        .join(Employee, Employee.id == meeting_participants.c.employee_id)
        .where(meeting_participants.c.employee_id.in_(participant_ids))
        .where(Meeting.starts_at < ends_at)
        .where(starts_at < Meeting.ends_at)
    )
    if exclude_meeting_id is not None:
        stmt = stmt.where(Meeting.id != exclude_meeting_id)

    return [
        Conflict(
            employee_id=employee.id,
            employee_name=employee.name,
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
        )
        for meeting, employee in db.execute(stmt).all()
    ]
