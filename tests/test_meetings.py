"""API-тесты: создание встреч, конфликты, валидация и расписание.

Сотрудники засеиваются в порядке SEED_EMPLOYEES, id идут с 1:
1=Алиса, 2=Борис, 3=Виктор, ...
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def iso(hour: int, minute: int = 0, day: int = 8) -> str:
    return f"2026-07-{day:02d}T{hour:02d}:{minute:02d}:00+00:00"


def make_payload(
    starts_at: str,
    ends_at: str,
    participant_ids: list[int],
    title: str = "Встреча",
) -> dict[str, Any]:
    return {
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "participant_ids": participant_ids,
    }


def test_create_meeting_and_appears_in_schedule(client: TestClient) -> None:
    resp = client.post("/meetings", json=make_payload(iso(10), iso(11), [1, 2]))
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["id"]
    assert {p["id"] for p in created["participants"]} == {1, 2}

    schedule = client.get("/meetings", params={"start": iso(0), "end": iso(23, 59)})
    assert schedule.status_code == 200
    assert any(m["id"] == created["id"] for m in schedule.json())


def test_conflict_when_participant_busy(client: TestClient) -> None:
    first = client.post(
        "/meetings",
        json=make_payload(iso(10), iso(11), [1, 2], title="Первая"),
    )
    assert first.status_code == 201

    # Участник 2 (Борис) занят 10:00–11:00, новая 10:30–11:30 пересекается.
    second = client.post(
        "/meetings",
        json=make_payload(iso(10, 30), iso(11, 30), [2, 3], title="Вторая"),
    )
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert "conflicts" in detail
    busy_names = {c["employee_name"] for c in detail["conflicts"]}
    assert "Борис" in busy_names
    # В человекочитаемом сообщении есть имя и время конфликта.
    assert "Борис" in detail["message"]
    assert "Первая" in detail["message"]

    # Конфликтная встреча не создана.
    schedule = client.get("/meetings", params={"start": iso(0), "end": iso(23, 59)})
    assert len(schedule.json()) == 1


def test_adjacent_meetings_do_not_conflict(client: TestClient) -> None:
    first = client.post("/meetings", json=make_payload(iso(10), iso(11), [1, 2]))
    assert first.status_code == 201
    # Впритык 11:00–12:00 у тех же участников — конфликта нет.
    second = client.post("/meetings", json=make_payload(iso(11), iso(12), [1, 2]))
    assert second.status_code == 201, second.text


def test_validation_too_few_participants(client: TestClient) -> None:
    resp = client.post("/meetings", json=make_payload(iso(10), iso(11), [1]))
    assert resp.status_code == 422


def test_validation_starts_not_before_ends(client: TestClient) -> None:
    resp = client.post("/meetings", json=make_payload(iso(11), iso(10), [1, 2]))
    assert resp.status_code == 422


def test_unknown_participant_rejected(client: TestClient) -> None:
    resp = client.post("/meetings", json=make_payload(iso(10), iso(11), [1, 999]))
    assert resp.status_code == 422


def test_schedule_day_week_and_employee_filter(client: TestClient) -> None:
    # Встреча в понедельник (участники 1,2) и во вторник (участники 3,4).
    mon = client.post(
        "/meetings",
        json=make_payload(iso(10, day=6), iso(11, day=6), [1, 2]),
    )
    tue = client.post(
        "/meetings",
        json=make_payload(iso(10, day=7), iso(11, day=7), [3, 4]),
    )
    assert mon.status_code == 201 and tue.status_code == 201

    # Расписание на один день (понедельник 6 июля) → только первая встреча.
    day_view = client.get(
        "/meetings",
        params={"start": iso(0, day=6), "end": iso(0, day=7)},
    )
    assert {m["id"] for m in day_view.json()} == {mon.json()["id"]}

    # Расписание на неделю (6–13 июля) → обе встречи.
    week_view = client.get(
        "/meetings",
        params={"start": iso(0, day=6), "end": iso(0, day=13)},
    )
    assert len(week_view.json()) == 2

    # Фильтр по сотруднику 3 (Виктор) → только вторничная встреча.
    filtered = client.get(
        "/meetings",
        params={
            "start": iso(0, day=6),
            "end": iso(0, day=13),
            "employee_id": 3,
        },
    )
    assert {m["id"] for m in filtered.json()} == {tue.json()["id"]}
