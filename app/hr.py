"""In-process HR helpers consumed by the optional skill assessment module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ClientPositionRegulation,
    ClientRegulationKpi,
    Employee,
    KpiTemplate,
    OrgUnit,
    Position,
)


def get_employee(db: Session, client_id: str, employee_id: str) -> Employee | None:
    return db.scalar(select(Employee).where(Employee.client_id == client_id, Employee.id == employee_id))


def get_position(db: Session, client_id: str, position_id: str) -> Position | None:
    return db.scalar(select(Position).where(Position.client_id == client_id, Position.id == position_id))


def get_org_unit(db: Session, client_id: str, org_unit_id: str | None) -> OrgUnit | None:
    if not org_unit_id:
        return None
    return db.scalar(select(OrgUnit).where(OrgUnit.client_id == client_id, OrgUnit.id == org_unit_id))


def _employee_position(db: Session, client_id: str, employee_id: str | None) -> Position | None:
    emp = get_employee(db, client_id, employee_id) if employee_id else None
    if not emp or not emp.position_id:
        return None
    return get_position(db, client_id, emp.position_id)


def _position_regulations(db: Session, client_id: str, pos: Position | None) -> list[ClientPositionRegulation]:
    if not pos:
        return []
    codes = {c for c in (pos.position_catalog_code, pos.code) if c}
    if not codes:
        return []
    return list(
        db.scalars(
            select(ClientPositionRegulation)
            .where(
                ClientPositionRegulation.client_id == client_id,
                ClientPositionRegulation.position_code.in_(codes),
            )
            .order_by(ClientPositionRegulation.regulation_code)
        )
    )


def get_examination_question_texts(db: Session, client_id: str, employee_id: str) -> list[str]:
    pos = _employee_position(db, client_id, employee_id)
    questions: list[str] = []
    for reg in _position_regulations(db, client_id, pos):
        title = reg.regulation_name or reg.regulation_code
        if reg.goal_summary:
            questions.append(f"{title}: {reg.goal_summary}")
        if reg.ckp_short:
            questions.append(f"{title}: {reg.ckp_short}")
    return questions


def get_examination_instructions_folder_url(db: Session, client_id: str, employee_id: str) -> str | None:
    pos = _employee_position(db, client_id, employee_id)
    for reg in _position_regulations(db, client_id, pos):
        if reg.instructions_folder_url:
            return reg.instructions_folder_url
    return None


def get_examination_regulation_reference_text(db: Session, client_id: str, employee_id: str) -> str | None:
    pos = _employee_position(db, client_id, employee_id)
    parts: list[str] = []
    for reg in _position_regulations(db, client_id, pos):
        body = reg.ckp_full or reg.ckp_short or reg.goal_summary
        if body:
            parts.append(f"{reg.regulation_name or reg.regulation_code}\n{body}")
    return "\n\n".join(parts) if parts else None


def get_examination_kpi_labels(db: Session, client_id: str, employee_id: str) -> list[str]:
    pos = _employee_position(db, client_id, employee_id)
    regs = _position_regulations(db, client_id, pos)
    if not regs:
        return []
    reg_ids = [reg.id for reg in regs]
    stmt = (
        select(ClientRegulationKpi, KpiTemplate)
        .join(KpiTemplate, KpiTemplate.kpi_code == ClientRegulationKpi.kpi_code, isouter=True)
        .where(ClientRegulationKpi.client_regulation_id.in_(reg_ids))
        .order_by(ClientRegulationKpi.kpi_code)
    )
    labels: list[str] = []
    for kpi, template in db.execute(stmt).all():
        labels.append(template.kpi_name if template else kpi.kpi_code)
    return labels


def get_assessment_case_count(db: Session, client_id: str, employee_id: str) -> int:
    return 3


def get_exam_protocol_manager_employee_id(db: Session, client_id: str, employee_id: str) -> str | None:
    return None


def get_company_director_employee_id(db: Session, client_id: str) -> str | None:
    return None


def get_managing_deputy_employee_id(db: Session, client_id: str) -> str | None:
    return None
