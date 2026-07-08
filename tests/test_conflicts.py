"""Граничные случаи семантики пересечения полуоткрытых интервалов."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.conflicts import intervals_overlap


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, 8, hour, minute)


@pytest.mark.parametrize(
    ("s1", "e1", "s2", "e2", "expected"),
    [
        # Впритык: конец одной = начало другой → НЕ конфликт.
        (dt(10), dt(11), dt(11), dt(12), False),
        (dt(11), dt(12), dt(10), dt(11), False),
        # Одинаковые границы (полное совпадение) → конфликт.
        (dt(10), dt(11), dt(10), dt(11), True),
        # Вложенный интервал → конфликт (в обе стороны).
        (dt(10), dt(12), dt(10, 30), dt(11), True),
        (dt(10, 30), dt(11), dt(10), dt(12), True),
        # Частичное перекрытие слева и справа → конфликт.
        (dt(10), dt(11), dt(10, 30), dt(11, 30), True),
        (dt(10, 30), dt(11, 30), dt(10), dt(11), True),
        # Непересекающиеся → НЕ конфликт.
        (dt(10), dt(11), dt(13), dt(14), False),
    ],
)
def test_intervals_overlap(
    s1: datetime,
    e1: datetime,
    s2: datetime,
    e2: datetime,
    expected: bool,
) -> None:
    assert intervals_overlap(s1, e1, s2, e2) is expected
