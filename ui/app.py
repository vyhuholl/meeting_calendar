"""Streamlit-клиент планировщика встреч.

Тонкий клиент: не ходит в БД, только в API по HTTP. База API — из env
``API_BASE_URL`` (дефолт ``http://localhost:8000``). Время вводится/показывается
в локальной таймзоне, а в API уходит/приходит в UTC.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
import streamlit as st


def _api_base_url() -> str:
    """База API: env → секреты Streamlit → локальный дефолт.

    В Streamlit Community Cloud значение задаётся в App → Settings → Secrets
    и читается через ``st.secrets`` (``os.getenv`` их не видит).
    """
    from_env = os.getenv("API_BASE_URL")
    if from_env:
        return from_env
    try:
        return str(st.secrets.get("API_BASE_URL", "http://localhost:8000"))
    except Exception:  # секретов нет вовсе (локальный запуск) — не падаем
        return "http://localhost:8000"


API_BASE_URL = _api_base_url()
# Запас на холодный старт бесплатного хостинга (Render усыпляет сервис после
# простоя и будит первый запрос ~30–50 с).
REQUEST_TIMEOUT = 30.0


def api_get(path: str, **params: Any) -> httpx.Response:
    """GET к API."""
    return httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)


def api_post(path: str, payload: dict[str, Any]) -> httpx.Response:
    """POST к API."""
    return httpx.post(f"{API_BASE_URL}{path}", json=payload, timeout=REQUEST_TIMEOUT)


def local_to_utc(d: date, t: time) -> str:
    """Локальные дата+время → ISO-8601 в UTC для отправки в API."""
    local_dt = datetime.combine(d, t).astimezone()
    return local_dt.astimezone(UTC).isoformat()


def utc_to_local_str(iso_str: str) -> str:
    """ISO-8601 из API (UTC) → строка в локальной TZ для показа."""
    dt = datetime.fromisoformat(iso_str).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


@st.cache_data(ttl=30)
def load_employees() -> list[dict[str, Any]]:
    """Справочник сотрудников (с коротким кэшем)."""
    resp = api_get("/employees")
    resp.raise_for_status()
    return list(resp.json())


def window_for(day: date, span: str) -> tuple[str, str]:
    """Границы окна расписания (UTC ISO) для дня или недели."""
    if span == "Неделя":
        start_day = day - timedelta(days=day.weekday())
        end_day = start_day + timedelta(days=7)
    else:
        start_day = day
        end_day = day + timedelta(days=1)
    start = datetime.combine(start_day, time()).astimezone().astimezone(UTC)
    end = datetime.combine(end_day, time()).astimezone().astimezone(UTC)
    return start.isoformat(), end.isoformat()


def render_create_form(
    employees: list[dict[str, Any]], name_by_id: dict[int, str]
) -> None:
    """Форма создания встречи."""
    st.subheader("Новая встреча")
    with st.form("create_meeting"):
        title = st.text_input("Название")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Дата начала", value=date.today())
            start_time = st.time_input("Время начала", value=time(10, 0))
        with col2:
            end_date = st.date_input("Дата конца", value=date.today())
            end_time = st.time_input("Время конца", value=time(11, 0))
        participant_ids = st.multiselect(
            "Участники (минимум 2)",
            options=[e["id"] for e in employees],
            format_func=lambda eid: name_by_id.get(eid, str(eid)),
        )
        submitted = st.form_submit_button("Создать")

    if not submitted:
        return

    if not title:
        st.error("Название встречи не может быть пустым.")
        return

    if len(participant_ids) < 2:
        st.error("Нужно выбрать минимум двух участников.")
        return

    starts_at = local_to_utc(start_date, start_time)
    ends_at = local_to_utc(end_date, end_time)

    if starts_at >= ends_at:
        st.error("Дата и время начала должны быть раньше даты и времени конца.")
        return

    payload = {
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "participant_ids": participant_ids,
    }
    resp = api_post("/meetings", payload)
    if resp.status_code == 201:
        st.success("Встреча создана.")
    elif resp.status_code == 409:
        detail = resp.json().get("detail", {})
        st.error(f"Конфликт: {detail.get('message', 'кто-то из участников занят')}")
    else:
        st.error(f"Ошибка {resp.status_code}: {resp.text}")


def render_schedule(
    employees: list[dict[str, Any]], name_by_id: dict[int, str]
) -> None:
    """Просмотр расписания на день/неделю с фильтром по сотруднику."""
    st.subheader("Расписание")
    col1, col2, col3 = st.columns(3)
    with col1:
        span = st.radio("Период", ["День", "Неделя"], horizontal=True)
    with col2:
        day = st.date_input("Дата", value=date.today(), key="schedule_date")
    with col3:
        filter_id = st.selectbox(
            "Сотрудник",
            options=[None, *[e["id"] for e in employees]],
            format_func=lambda eid: (
                "Все" if eid is None else name_by_id.get(eid, str(eid))
            ),
        )

    start, end = window_for(day, span)
    params: dict[str, Any] = {"start": start, "end": end}
    if filter_id is not None:
        params["employee_id"] = filter_id
    resp = api_get("/meetings", **params)
    if resp.status_code != 200:
        st.error(f"Ошибка {resp.status_code}: {resp.text}")
        return

    meetings = resp.json()
    if not meetings:
        st.info("Встреч нет.")
        return

    for m in meetings:
        names = ", ".join(p["name"] for p in m["participants"])
        st.markdown(
            f"**{m['title']}** — {utc_to_local_str(m['starts_at'])} → "
            f"{utc_to_local_str(m['ends_at'])}  \nУчастники: {names}"
        )


def main() -> None:
    st.set_page_config(page_title="Планировщик встреч", page_icon="📅")
    st.title("📅 Планировщик встреч")

    try:
        employees = load_employees()
    except httpx.HTTPError as exc:
        st.error(f"Не удалось загрузить сотрудников из API: {exc}")
        st.stop()

    name_by_id = {e["id"]: e["name"] for e in employees}

    with st.sidebar:
        st.header("Кто я")
        st.selectbox(
            "Выберите сотрудника",
            options=[e["id"] for e in employees],
            format_func=lambda eid: name_by_id.get(eid, str(eid)),
            key="current_employee",
        )
        st.caption(f"API: {API_BASE_URL}")

    render_create_form(employees, name_by_id)
    st.divider()
    render_schedule(employees, name_by_id)


if __name__ == "__main__":
    main()
