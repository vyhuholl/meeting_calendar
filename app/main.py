"""Точка входа FastAPI: схема на старте, seed сотрудников, роутеры."""

from __future__ import annotations

from fastapi import FastAPI

from app import models  # noqa: F401  # регистрируем модели в Base.metadata
from app.crud import seed_employees
from app.db import Base, SessionLocal, engine
from app.routers import employees, meetings


def create_app() -> FastAPI:
    """Собрать приложение: создать схему (идемпотентно), засеять сотрудников."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_employees(db)

    app = FastAPI(title="Планировщик встреч", version="1.0.0")
    app.include_router(employees.router)
    app.include_router(meetings.router)
    return app


app = create_app()
