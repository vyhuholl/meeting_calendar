"""Тестовые фикстуры: изолированная in-memory БД и клиент API."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

# Перенаправляем модульный engine приложения на throwaway-файл ДО импорта app,
# чтобы тесты не трогали рабочий meeting_calendar.db.
_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/app.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401  # регистрируем модели
from app.crud import seed_employees  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Отдельный in-memory engine для тестов: одно общее соединение (StaticPool).
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(
    bind=_test_engine, autoflush=False, expire_on_commit=False, class_=Session
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Свежая схема + засеянные сотрудники на каждый тест."""
    Base.metadata.create_all(_test_engine)
    session = _TestingSession()
    seed_employees(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(_test_engine)


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient с подменённой зависимостью get_db на тестовую сессию."""

    def _override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
