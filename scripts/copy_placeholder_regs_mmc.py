#!/usr/bin/env python3
"""
Временные локальные регламенты ММЦ для MAIN_NURSE и ADM_ZAM_STRATEG:
копия содержимого глобального шаблона REG_ADM_ZAMADM_V1 (hosp).
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import (
    Client,
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    PositionCatalog,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)
from app.utils import new_id32

CLIENT_CODE = "mmc"
TEMPLATE_CODE = "hosp"
SOURCE_GLOBAL_CODE = "REG_ADM_ZAMADM_V1"
DEPT_CODE = "ADM"

TARGETS: list[tuple[str, str]] = [
    ("MAIN_NURSE", "REG_MAIN_NURSE_V1"),
    ("ADM_ZAM_STRATEG", "REG_ADM_ZAM_STRATEG_V1"),
]


def _delete_client_regs_for_position(db, client_id: str, position_code: str) -> int:
    regs = list(
        db.scalars(
            select(ClientPositionRegulation).where(
                ClientPositionRegulation.client_id == client_id,
                ClientPositionRegulation.position_code == position_code,
            )
        ).all()
    )
    for reg in regs:
        db.execute(
            delete(ClientRegulationKpi).where(
                ClientRegulationKpi.client_regulation_id == reg.id
            )
        )
        db.execute(
            delete(ClientRegulationInstruction).where(
                ClientRegulationInstruction.client_regulation_id == reg.id
            )
        )
        db.delete(reg)
    return len(regs)


def _copy_global_as_client_slot(
    db,
    client_id: str,
    glob: PositionRegulation,
    *,
    position_code: str,
    dept_type_code: str,
    client_regulation_code: str,
) -> ClientPositionRegulation:
    rid = new_id32()
    obj = ClientPositionRegulation(
        id=rid,
        client_id=client_id,
        regulation_code=client_regulation_code,
        global_regulation_code=glob.regulation_code,
        is_detached=True,
        position_code=position_code,
        dept_type_code=dept_type_code,
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


def main() -> None:
    db = SessionLocal()
    try:
        client = db.scalar(select(Client).where(Client.code == CLIENT_CODE))
        if not client:
            raise SystemExit(f"Client {CLIENT_CODE} not found")

        glob = db.scalar(
            select(PositionRegulation).where(
                PositionRegulation.template_code == TEMPLATE_CODE,
                PositionRegulation.regulation_code == SOURCE_GLOBAL_CODE,
            )
        )
        if not glob:
            raise SystemExit(f"Global regulation {SOURCE_GLOBAL_CODE} not found for {TEMPLATE_CODE}")

        for position_code, client_reg_code in TARGETS:
            removed = _delete_client_regs_for_position(db, client.id, position_code)
            dup = db.scalar(
                select(ClientPositionRegulation).where(
                    ClientPositionRegulation.client_id == client.id,
                    ClientPositionRegulation.regulation_code == client_reg_code,
                )
            )
            if dup:
                raise SystemExit(f"Client regulation code already exists: {client_reg_code}")

            row = _copy_global_as_client_slot(
                db,
                client.id,
                glob,
                position_code=position_code,
                dept_type_code=DEPT_CODE,
                client_regulation_code=client_reg_code,
            )
            cat = db.get(PositionCatalog, (TEMPLATE_CODE, position_code))
            if cat:
                cat.default_regulation_code = client_reg_code

            print(
                f"{position_code}: removed={removed} -> {client_reg_code} "
                f"(from global {SOURCE_GLOBAL_CODE}, dept={DEPT_CODE})"
            )

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
