"""Роуты справочника сотрудников."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.schemas import EmployeeOut

router = APIRouter(tags=["employees"])


@router.get("/employees", response_model=list[EmployeeOut])
def get_employees(db: Annotated[Session, Depends(get_db)]) -> list[EmployeeOut]:
    """Список всех сотрудников для выбора «кто я» и участников встречи."""
    return [EmployeeOut.model_validate(e) for e in crud.list_employees(db)]
