#!/usr/bin/env python3
"""Исправить коды регламентов hosp (COPY_*), URL Google Doc и типы подразделений."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select, update

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import (
    PositionCatalog,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)

TEMPLATE = "hosp"

# position_code в каталоге hosp → канонический regulation_code, URL, dept_type_code
HOSP_REG_CANON: list[dict[str, str]] = [
    {
        "position_code": "ORDINATOR amb",
        "regulation_code": "REG_DOC_AMBUL_V1",
        "google_doc_url": "https://docs.google.com/document/d/1uLsIKwOb2bxSyufuDzw7FGwR9G7PeQiq2FPZ1NyCwG0/edit?usp=sharing",
        "dept_type_code": "POLYCLINNC",
    },
    {
        "position_code": "ORDINATOR hosp",
        "regulation_code": "REG_DOC_INPATIENT_V1",
        "google_doc_url": "https://docs.google.com/document/d/1M3Ax8lzNbWKxJYS8gn5yWwXaRkQzdO-v7BK03o0WMds/edit?usp=sharing",
        "dept_type_code": "STAT",
    },
    {
        "position_code": "ADM_ZAM_LECH",
        "regulation_code": "REG_ADM_ZAM_LECH_V1",
        "google_doc_url": "https://docs.google.com/document/d/1eaDF2bd2iVwnlmcNTO2TMGsBQ8GpS68NxMYIBeWNTb4/edit?usp=sharing",
        "dept_type_code": "OPER",
    },
    {
        "position_code": "ADM_ZAM_POLYCLINIC",
        "regulation_code": "REG_ADM_ZAM_AMBUL_V1",
        "google_doc_url": "https://docs.google.com/document/d/1Ttik1jMEMkGkEzoByt86njDbOTLDqjeNl0N4RPPZprc/edit?usp=sharing",
        "dept_type_code": "POLYCLINNC",
    },
    {
        "position_code": "ADM_ZAM_QM",
        "regulation_code": "REG_ADM_ZAM_QUAL_V1",
        "google_doc_url": "https://docs.google.com/document/d/1u1u41T8g1NhrAAd_Y86TuVpTihP55e1KzKccZBmQ9M4/edit?usp=sharing",
        "dept_type_code": "QUAL",
    },
    {
        "position_code": "HEAD_DEPT",
        "regulation_code": "REG_HEAD_DEPT_V1",
        "google_doc_url": "https://docs.google.com/document/d/1hk__HVerOIbiY32mdrFODLBr8ZKUpVNU4DEAnKOXaOA/edit?usp=sharing",
        "dept_type_code": "STAT",
    },
    {
        "position_code": "NURSE amb",
        "regulation_code": "REG_NURSE_AMBUL_V1",
        "google_doc_url": "https://docs.google.com/document/d/1X9r3KbquRDbzxU1bSJgyTLxLHLAyYf_OTPU69jz5hF4/edit?usp=sharing",
        "dept_type_code": "POLYCLINNC",
    },
    {
        "position_code": "POST_NURSE",
        "regulation_code": "REG_WARD_NURSE_V1",
        "google_doc_url": "https://docs.google.com/document/d/1TYBKxte3xJy68v7HWxAG0caQiuJduA-s-DO15tCXlCw/edit?usp=sharing",
        "dept_type_code": "STAT",
    },
    {
        "position_code": "CALL OPERATOR cold",
        "regulation_code": "REG_CALL_OUTBOUND_V1",
        "google_doc_url": "https://docs.google.com/document/d/1_s77DouzbOQREnU4f5IoR7V7VnrYf3cVqEkROEpHEsY/edit?usp=sharing",
        "dept_type_code": "ADMISSION",
    },
    {
        "position_code": "CALL OPERATOR warm",
        "regulation_code": "REG_CALL_REG_V1",
        "google_doc_url": "https://docs.google.com/document/d/1jVJjUdnRxbBdWfnbcf0IYxWiEkwj57qxeLLGB98nP30/edit?usp=sharing",
        "dept_type_code": "ADMISSION",
    },
    {
        "position_code": "PROCEDURE_NURSE",
        "regulation_code": "REG_NURSE_PROCEDURE_V1",
        "google_doc_url": "https://docs.google.com/document/d/1KNh3eVU-_x6rhGao93pYb0LJHgjugJ3Ad8-GQ5zek2Y/edit?usp=sharing",
        "dept_type_code": "POLYCLINNC",
    },
    {
        "position_code": "ORDERLY",
        "regulation_code": "REG_ORDERLY_V1",
        "google_doc_url": "https://docs.google.com/document/d/1W6PoH4hZ-uhCh16pza5qHmE14eRA1EgQ_LqMP2KBfCM/edit?usp=sharing",
        "dept_type_code": "STAT",
    },
    {
        "position_code": "NURSE_HOUSEKEEP",
        "regulation_code": "REG_NURSE_HOUSEKEEP_V1",
        "google_doc_url": "https://docs.google.com/document/d/1aP3A-GmXINH4vB9lSf95bwKHjxfM6TjLv-Q4Kf_mZRI/edit?usp=sharing",
        "dept_type_code": "FACILITY",
    },
    {
        "position_code": "DEPT_CHIEF_NURSE",
        "regulation_code": "REG_DEPT_CHIEF_NURSE_V1",
        "google_doc_url": "https://docs.google.com/document/d/156M5kG1SI4tGHNlPToGbUaJBxLtuU_GRiGedtlJKda0/edit?usp=sharing",
        "dept_type_code": "STAT",
    },
    {
        "position_code": "ADM_ZAMADM",
        "regulation_code": "REG_ADM_ZAMADM_V1",
        "google_doc_url": "https://docs.google.com/document/d/1CXVKL4i7R1sN5CmcPZUDiE3zUzW2TXyZKa2QhiWl7MM/edit?usp=sharing",
        "dept_type_code": "ADM",
    },
]


def _rename_regulation_code(db, template_code: str, old_code: str, new_code: str) -> None:
    if old_code == new_code:
        return
    conflict = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.regulation_code == new_code,
        )
    )
    if conflict:
        raise RuntimeError(f"Код {new_code} уже занят ({conflict.position_code}), не могу переименовать {old_code}")
    db.execute(
        update(RegulationKpi)
        .where(RegulationKpi.template_code == template_code, RegulationKpi.regulation_code == old_code)
        .values(regulation_code=new_code)
    )
    db.execute(
        update(RegulationInstruction)
        .where(RegulationInstruction.template_code == template_code, RegulationInstruction.regulation_code == old_code)
        .values(regulation_code=new_code)
    )
    db.execute(
        update(PositionRegulation)
        .where(PositionRegulation.template_code == template_code, PositionRegulation.regulation_code == old_code)
        .values(regulation_code=new_code)
    )


def main() -> None:
    db = SessionLocal()
    try:
        for spec in HOSP_REG_CANON:
            pos = spec["position_code"]
            reg = db.scalar(
                select(PositionRegulation).where(
                    PositionRegulation.template_code == TEMPLATE,
                    PositionRegulation.position_code == pos,
                    PositionRegulation.is_current == True,
                )
            )
            if not reg:
                print(f"SKIP no regulation: {pos}")
                continue
            old_code = reg.regulation_code
            new_code = spec["regulation_code"]
            if old_code != new_code:
                print(f"RENAME {pos}: {old_code} -> {new_code}")
                _rename_regulation_code(db, TEMPLATE, old_code, new_code)
                reg = db.scalar(
                    select(PositionRegulation).where(
                        PositionRegulation.template_code == TEMPLATE,
                        PositionRegulation.regulation_code == new_code,
                    )
                )
            reg.google_doc_url = spec["google_doc_url"]
            reg.dept_type_code = spec["dept_type_code"]
            pc = db.get(PositionCatalog, (TEMPLATE, pos))
            if pc:
                pc.default_regulation_code = new_code
            print(f"OK {pos} url+dept")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
