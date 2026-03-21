"""Копирование глобальных регламентов (и связанных KPI/инструкций) в справочник клиента."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    OrgUnit,
    Position,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)
from app.utils import new_id32


def _client_position_dept_pairs(db: Session, client_id: str) -> set[tuple[str, str]]:
    """Пары (код должности из каталога, код подразделения-узла), есть у клиента."""
    out: set[tuple[str, str]] = set()
    for pos in db.scalars(select(Position).where(Position.client_id == client_id)).all():
        ou = db.get(OrgUnit, pos.org_unit_id)
        if not ou:
            continue
        code = (pos.position_catalog_code or pos.code or "").strip()
        if code:
            out.add((code, ou.code.strip()))
    return out


def copy_global_regulation_to_client(
    db: Session, client_id: str, glob: PositionRegulation, regulation_code: str | None = None
) -> ClientPositionRegulation | None:
    """Создать клиентскую копию глобального регламента с KPI и инструкциями. Возвращает None при дубликате кода."""
    target_code = (regulation_code or glob.regulation_code).strip()
    dup = db.scalar(
        select(ClientPositionRegulation).where(
            ClientPositionRegulation.client_id == client_id,
            ClientPositionRegulation.regulation_code == target_code,
        )
    )
    if dup:
        return None
    rid = new_id32()
    obj = ClientPositionRegulation(
        id=rid,
        client_id=client_id,
        regulation_code=target_code,
        global_regulation_code=glob.regulation_code,
        is_detached=True,
        position_code=glob.position_code,
        dept_type_code=glob.dept_type_code,
        regulation_name=glob.regulation_name,
        goal_summary=glob.goal_summary,
        ckp_short=glob.ckp_short,
        ckp_full=glob.ckp_full,
        google_doc_url=glob.google_doc_url,
        instructions_folder_url=glob.instructions_folder_url,
        version_no=glob.version_no,
        status=glob.status,
        effective_from=glob.effective_from,
        effective_to=glob.effective_to,
        is_current=glob.is_current,
        owner_unit_code=glob.owner_unit_code,
        notes=glob.notes,
    )
    db.add(obj)
    db.flush()
    for k in db.scalars(
        select(RegulationKpi).where(RegulationKpi.regulation_code == glob.regulation_code)
    ).all():
        db.add(
            ClientRegulationKpi(
                id=new_id32(),
                client_regulation_id=rid,
                kpi_code=k.kpi_code,
                target_value=k.target_value,
                period_type=k.period_type,
                weight=k.weight,
                is_required=k.is_required,
            )
        )
    for ins in db.scalars(
        select(RegulationInstruction)
        .where(RegulationInstruction.regulation_code == glob.regulation_code)
        .order_by(RegulationInstruction.sort_order)
    ).all():
        db.add(
            ClientRegulationInstruction(
                id=new_id32(),
                client_regulation_id=rid,
                instruction_code=ins.instruction_code,
                instruction_name=ins.instruction_name,
                instruction_url=ins.instruction_url,
                is_required=ins.is_required,
                sort_order=ins.sort_order,
            )
        )
    return obj


def sync_global_regulations_to_client(db: Session, client_id: str) -> int:
    """
    Для каждого глобального регламента, чья пара (position_code, dept_type_code)
    покрыта должностями клиента на соответствующих подразделениях, создать клиентскую копию (если ещё нет).
    """
    pairs = _client_position_dept_pairs(db, client_id)
    if not pairs:
        return 0
    existing_codes = set(
        db.scalars(
            select(ClientPositionRegulation.regulation_code).where(
                ClientPositionRegulation.client_id == client_id
            )
        ).all()
    )
    created = 0
    for glob in db.scalars(select(PositionRegulation)).all():
        if (glob.position_code, glob.dept_type_code) not in pairs:
            continue
        if glob.regulation_code in existing_codes:
            continue
        if copy_global_regulation_to_client(db, client_id, glob):
            created += 1
            existing_codes.add(glob.regulation_code)
    return created
