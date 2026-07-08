"""Операции с БД: сотрудники, расписание и транзакционное создание встречи."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import SEED_EMPLOYEES
from app.conflicts import Conflict, find_conflicts
from app.models import Employee, Meeting, meeting_participants
from app.schemas import MeetingCreate


class ParticipantNotFound(Exception):
    """Один или несколько участников не найдены в справочнике."""

    def __init__(self, missing: set[int]) -> None:
        self.missing = sorted(missing)
        super().__init__(f"Сотрудники не найдены: {self.missing}")


class MeetingConflict(Exception):
    """Хотя бы один участник занят в пересекающемся интервале."""

    def __init__(self, conflicts: list[Conflict]) -> None:
        self.conflicts = conflicts
        super().__init__("Обнаружен конфликт расписания")


def list_employees(db: Session) -> list[Employee]:
    """Все сотрудники, отсортированные по имени."""
    return list(db.scalars(select(Employee).order_by(Employee.name)))


def seed_employees(db: Session) -> None:
    """Идемпотентно наполнить пустой справочник предопределёнными именами."""
    count = db.scalar(select(func.count()).select_from(Employee))
    if count:
        return
    db.add_all([Employee(name=name) for name in SEED_EMPLOYEES])
    db.commit()


def get_schedule(
    db: Session,
    start: datetime,
    end: datetime,
    employee_id: int | None = None,
) -> list[Meeting]:
    """Встречи, пересекающиеся с окном `[start, end)`; опц. фильтр по сотруднику.

    Длинные встречи, начавшиеся до окна, но заходящие в него, тоже попадают.
    """
    stmt = (
        select(Meeting)
        .where(Meeting.starts_at < end)
        .where(start < Meeting.ends_at)
        .order_by(Meeting.starts_at)
    )
    if employee_id is not None:
        stmt = stmt.join(
            meeting_participants,
            meeting_participants.c.meeting_id == Meeting.id,
        ).where(meeting_participants.c.employee_id == employee_id)
    return list(db.scalars(stmt).unique())


def create_meeting(db: Session, data: MeetingCreate) -> Meeting:
    """Создать встречу; проверка занятости и вставка — в одной транзакции.

    Порядок «проверить конфликты → вставить» внутри одной транзакции исключает
    гонку двойного бронирования (в SQLite запись сериализуется).
    """
    employees = list(
        db.scalars(select(Employee).where(Employee.id.in_(data.participant_ids)))
    )
    found_ids = {e.id for e in employees}
    missing = set(data.participant_ids) - found_ids
    if missing:
        raise ParticipantNotFound(missing)

    conflicts = find_conflicts(db, data.participant_ids, data.starts_at, data.ends_at)
    if conflicts:
        db.rollback()
        raise MeetingConflict(conflicts)

    meeting = Meeting(
        title=data.title,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        participants=employees,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting
