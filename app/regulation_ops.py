"""Операции с глобальными регламентами должностей."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.models import (
    PositionCatalog,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)


def resolve_catalog_position_code(db: Session, template_code: str, position_code: str) -> str | None:
    """Код должности как в справочнике (регистр сохраняется, поиск без учёта регистра)."""
    raw = position_code.strip()
    if not raw:
        return None
    exact = db.get(PositionCatalog, (template_code, raw))
    if exact:
        return exact.position_code
    matches = db.scalars(
        select(PositionCatalog).where(
            PositionCatalog.template_code == template_code,
            func.upper(PositionCatalog.position_code) == raw.upper(),
        )
    ).all()
    if len(matches) == 1:
        return matches[0].position_code
    return None


def ensure_regulation_position_code(db: Session, template_code: str, position_code: str) -> str:
    code = resolve_catalog_position_code(db, template_code, position_code)
    if not code:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "position_not_in_catalog",
                "message": (
                    f"Должность «{position_code.strip()}» не найдена в справочнике типовых должностей "
                    f"шаблона «{template_code}». Сначала заведите её в каталоге должностей."
                ),
            },
        )
    return code


def ensure_regulation_slot_available(
    db: Session,
    template_code: str,
    position_code: str,
    dept_type_code: str,
    version_no: str,
    exclude_regulation_code: str,
) -> None:
    slot = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.position_code == position_code,
            PositionRegulation.dept_type_code == dept_type_code,
            PositionRegulation.version_no == version_no,
            PositionRegulation.regulation_code != exclude_regulation_code,
        )
    )
    if slot:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "regulation_slot_already_exists",
                "message": (
                    f"Для должности «{position_code}», типа подразделения «{dept_type_code}» "
                    f"и версии «{version_no}» регламент уже есть "
                    f"(код «{slot.regulation_code}», «{slot.regulation_name}»)."
                ),
            },
        )


def rename_regulation_code(db: Session, row: PositionRegulation, new_code: str) -> None:
    new_code = new_code.strip()
    if not new_code:
        raise HTTPException(status_code=422, detail="invalid_regulation_code")
    if new_code == row.regulation_code:
        return
    existing = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == row.template_code,
            PositionRegulation.regulation_code == new_code,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "regulation_code_already_exists",
                "message": (
                    f"Код регламента «{new_code}» уже занят в шаблоне "
                    f"«{row.template_code}» (карточка «{existing.regulation_name}»)."
                ),
            },
        )
    old_code = row.regulation_code
    tpl = row.template_code
    row.regulation_code = new_code
    db.execute(
        update(RegulationKpi)
        .where(
            RegulationKpi.template_code == tpl,
            RegulationKpi.regulation_code == old_code,
        )
        .values(regulation_code=new_code)
    )
    db.execute(
        update(RegulationInstruction)
        .where(
            RegulationInstruction.template_code == tpl,
            RegulationInstruction.regulation_code == old_code,
        )
        .values(regulation_code=new_code)
    )
    db.execute(
        update(PositionCatalog)
        .where(
            PositionCatalog.template_code == tpl,
            PositionCatalog.default_regulation_code == old_code,
        )
        .values(default_regulation_code=new_code)
    )
