"""ORM-модели: сотрудники, встречи и связь M2M между ними.

Время (`starts_at`, `ends_at`) хранится как naive UTC.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Ассоциативная таблица M2M: участники встречи.
meeting_participants = Table(
    "meeting_participants",
    Base.metadata,
    Column(
        "meeting_id",
        ForeignKey("meetings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "employee_id",
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Employee(Base):
    """Сотрудник. Используется для выбора «кто я» и как участник встречи."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Meeting(Base):
    """Встреча с интервалом `[starts_at, ends_at)` в UTC и участниками."""

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    participants: Mapped[list[Employee]] = relationship(
        secondary=meeting_participants,
        lazy="selectin",
    )
