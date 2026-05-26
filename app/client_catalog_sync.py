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
from app.template_bundle_clone import resolve_client_template_code
from app.utils import new_id32


def _client_position_dept_pairs(db: Session, client_id: str) -> set[tuple[str, str]]:
    """Пары (код должности из каталога, код подразделения-узла), есть у клиента."""
    out: set[tuple[str, str]] = set()
    for pos in db.scalars(select(Position).where(Position.client_id == client_id)).all():
        ou = db.get(OrgUnit, pos.org_unit_id)
        if not ou:
            continue
        code = (pos.position_catalog_code or pos.code or "").strip()
        dept = (ou.code or "").strip()
        if code and dept:
            out.add((code, dept))
    return out


def _existing_regulation_keys(db: Session, client_id: str) -> tuple[set[str], set[str], set[tuple[str, str, str]]]:
    codes: set[str] = set()
    global_codes: set[str] = set()
    slots: set[tuple[str, str, str]] = set()
    for reg in db.scalars(
        select(ClientPositionRegulation).where(ClientPositionRegulation.client_id == client_id)
    ).all():
        codes.add(reg.regulation_code.strip())
        glob = (reg.global_regulation_code or "").strip()
        if glob:
            global_codes.add(glob)
        slots.add(
            (reg.position_code.strip(), reg.dept_type_code.strip(), reg.version_no.strip())
        )
    return codes, global_codes, slots


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
        select(RegulationKpi).where(
            RegulationKpi.template_code == glob.template_code,
            RegulationKpi.regulation_code == glob.regulation_code,
        )
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
        .where(
            RegulationInstruction.template_code == glob.template_code,
            RegulationInstruction.regulation_code == glob.regulation_code,
        )
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


def _sync_missing_regulation_children(
    db: Session, client_id: str, template_code: str
) -> tuple[int, int]:
    """Добавить отсутствующие KPI и инструкции в уже скопированные клиентские регламенты."""
    kpis_added = 0
    instructions_added = 0
    for client_reg in db.scalars(
        select(ClientPositionRegulation).where(ClientPositionRegulation.client_id == client_id)
    ).all():
        glob_code = (client_reg.global_regulation_code or client_reg.regulation_code).strip()
        glob = db.scalar(
            select(PositionRegulation).where(
                PositionRegulation.template_code == template_code,
                PositionRegulation.regulation_code == glob_code,
            )
        )
        if not glob:
            continue
        existing_kpi = {
            k.kpi_code.strip()
            for k in db.scalars(
                select(ClientRegulationKpi).where(
                    ClientRegulationKpi.client_regulation_id == client_reg.id
                )
            ).all()
        }
        for k in db.scalars(
            select(RegulationKpi).where(
                RegulationKpi.template_code == template_code,
                RegulationKpi.regulation_code == glob.regulation_code,
            )
        ).all():
            if k.kpi_code.strip() in existing_kpi:
                continue
            db.add(
                ClientRegulationKpi(
                    id=new_id32(),
                    client_regulation_id=client_reg.id,
                    kpi_code=k.kpi_code,
                    target_value=k.target_value,
                    period_type=k.period_type,
                    weight=k.weight,
                    is_required=k.is_required,
                )
            )
            existing_kpi.add(k.kpi_code.strip())
            kpis_added += 1

        existing_ins = {
            i.instruction_code.strip()
            for i in db.scalars(
                select(ClientRegulationInstruction).where(
                    ClientRegulationInstruction.client_regulation_id == client_reg.id
                )
            ).all()
        }
        for ins in db.scalars(
            select(RegulationInstruction)
            .where(
                RegulationInstruction.template_code == template_code,
                RegulationInstruction.regulation_code == glob.regulation_code,
            )
            .order_by(RegulationInstruction.sort_order)
        ).all():
            if ins.instruction_code.strip() in existing_ins:
                continue
            db.add(
                ClientRegulationInstruction(
                    id=new_id32(),
                    client_regulation_id=client_reg.id,
                    instruction_code=ins.instruction_code,
                    instruction_name=ins.instruction_name,
                    instruction_url=ins.instruction_url,
                    is_required=ins.is_required,
                    sort_order=ins.sort_order,
                )
            )
            existing_ins.add(ins.instruction_code.strip())
            instructions_added += 1
    return kpis_added, instructions_added


def sync_global_regulations_to_client(
    db: Session, client_id: str, *, template_code: str | None = None
) -> int:
    """
    Для каждого глобального регламента bundle клиента, чья пара (position_code, dept_type_code)
    покрыта должностями клиента на соответствующих подразделениях, создать клиентскую копию (если ещё нет).
    """
    tpl = template_code or resolve_client_template_code(db, client_id)
    pairs = _client_position_dept_pairs(db, client_id)
    if not pairs:
        return 0
    existing_codes, existing_global_codes, existing_slots = _existing_regulation_keys(db, client_id)
    created = 0
    for glob in db.scalars(
        select(PositionRegulation).where(PositionRegulation.template_code == tpl)
    ).all():
        if (glob.position_code, glob.dept_type_code) not in pairs:
            continue
        slot = (glob.position_code.strip(), glob.dept_type_code.strip(), glob.version_no.strip())
        if (
            glob.regulation_code in existing_codes
            or glob.regulation_code in existing_global_codes
            or slot in existing_slots
        ):
            continue
        if copy_global_regulation_to_client(db, client_id, glob):
            created += 1
            existing_codes.add(glob.regulation_code)
            existing_global_codes.add(glob.regulation_code)
            existing_slots.add(slot)
    _sync_missing_regulation_children(db, client_id, tpl)
    return created
