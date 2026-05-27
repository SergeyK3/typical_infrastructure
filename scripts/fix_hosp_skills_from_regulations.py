#!/usr/bin/env python3
"""
Привести навыки шаблона hosp (ММЦ) в соответствие с DOCX регламентов:

  - hard skills (ранги 1–7): заменить ошибочно скопированные из default (HR и др.)
  - soft job skills (ранги 8–14): точная копия из таблицы Б, код CSOFT_*, description «soft job skill»
  - удалить строки матрицы с неверным department_code (HR, PROD …)
  - убрать лишние KPI_HR_HEAD_* из regulation_kpis медицинских регламентов

Запуск из корня репозитория:
  python scripts/fix_hosp_skills_from_regulations.py
  python scripts/fix_hosp_skills_from_regulations.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import PositionRegulation, RegulationKpi
from scripts.fix_hosp_regulation_codes_and_urls import HOSP_REG_CANON
from scripts.sync_global_regulations_from_sources import (
    SOFT_SKILL_KIND,
    SOFT_SKILL_RANK_BASE,
    _active_competency_version,
    _skill_code,
    _target_position,
    collect_parsed,
    load_url_maps,
)
from skill_assessment.infrastructure.db_models import CompetencyMatrixRow, CompetencySkillDefinitionRow

TEMPLATE_CODE = "hosp"
HOSP_MMC_DEPT: dict[str, str] = {x["position_code"]: x["dept_type_code"] for x in HOSP_REG_CANON}
HOSP_MMC_REG_CODES: set[str] = {x["regulation_code"] for x in HOSP_REG_CANON}
WRONG_KPI_PREFIXES = ("KPI_HR_HEAD_", "KPI_TMPL_")


def _parsed_for_position(by_pos: dict, catalog_pos: str):
    for docx_pos, row in by_pos.items():
        if _target_position(TEMPLATE_CODE, docx_pos) == catalog_pos:
            return row
    return None


def _get_or_create_skill_definition(
    db,
    *,
    skill_code: str,
    title: str,
    description: str | None,
) -> tuple[str, str]:
    """Возвращает (skill_id, action)."""
    existing = db.scalar(
        select(CompetencySkillDefinitionRow).where(
            CompetencySkillDefinitionRow.template_code == TEMPLATE_CODE,
            CompetencySkillDefinitionRow.skill_code == skill_code,
        )
    )
    if existing:
        changed = existing.title_ru != title[:512] or existing.description != description
        if changed:
            existing.title_ru = title[:512]
            existing.description = description
            return existing.id, "rewrite_def"
        return existing.id, "reuse_def"
    sid = str(uuid.uuid4())
    db.add(
        CompetencySkillDefinitionRow(
            id=sid,
            client_id=None,
            template_code=TEMPLATE_CODE,
            skill_code=skill_code,
            title_ru=title[:512],
            description=description,
            is_active=True,
        )
    )
    return sid, "add_def"


def _upsert_matrix_skill(
    db,
    *,
    version_id: str,
    position_code: str,
    department_code: str,
    rank: int,
    title: str,
    is_soft: bool,
) -> str:
    row = db.scalar(
        select(CompetencyMatrixRow).where(
            CompetencyMatrixRow.version_id == version_id,
            CompetencyMatrixRow.position_code == position_code,
            CompetencyMatrixRow.department_code == department_code,
            CompetencyMatrixRow.skill_rank == rank,
        )
    )
    scode = _skill_code(TEMPLATE_CODE, position_code, rank, is_soft=is_soft)
    desc = SOFT_SKILL_KIND if is_soft else None

    if row:
        skill = db.get(CompetencySkillDefinitionRow, row.skill_definition_id)
        if skill and (skill.title_ru != title[:512] or skill.skill_code != scode or skill.description != desc):
            skill.title_ru = title[:512]
            skill.skill_code = scode
            skill.description = desc
            skill.template_code = TEMPLATE_CODE
            action = "rewrite"
        else:
            action = "ok"
    else:
        sid, def_action = _get_or_create_skill_definition(
            db, skill_code=scode, title=title, description=desc
        )
        db.add(
            CompetencyMatrixRow(
                id=str(uuid.uuid4()),
                version_id=version_id,
                position_code=position_code,
                department_code=department_code,
                skill_definition_id=sid,
                skill_rank=rank,
                is_active=True,
            )
        )
        action = f"add_matrix:{def_action}"

    kind = "soft" if is_soft else "hard"
    return f"{action}:{position_code}#{rank}:{kind}:{title[:48]}"


def fix_hosp_skills_and_kpis(*, dry_run: bool = False) -> list[str]:
    by_pos = collect_parsed(load_url_maps())
    log: list[str] = []
    db = SessionLocal()
    try:
        comp_ver = _active_competency_version(db, TEMPLATE_CODE)
        if not comp_ver:
            raise RuntimeError(f"Нет активной версии каталога компетенций для {TEMPLATE_CODE!r}")

        for spec in HOSP_REG_CANON:
            pos = spec["position_code"]
            dept = spec["dept_type_code"]
            parsed = _parsed_for_position(by_pos, pos)
            if not parsed:
                log.append(f"skip:{pos}:no_docx")
                continue

            # Удалить строки с неверным подразделением (клон default → HR/PROD)
            stray = db.scalars(
                select(CompetencyMatrixRow).where(
                    CompetencyMatrixRow.version_id == comp_ver.id,
                    CompetencyMatrixRow.position_code == pos,
                    CompetencyMatrixRow.department_code != dept,
                )
            ).all()
            for row in stray:
                db.delete(row)
                log.append(f"delete_stray:{pos}:{row.department_code}#{row.skill_rank}")

            for rank, title in parsed.hard_skills:
                log.append(
                    _upsert_matrix_skill(
                        db,
                        version_id=comp_ver.id,
                        position_code=pos,
                        department_code=dept,
                        rank=rank,
                        title=title,
                        is_soft=False,
                    )
                )

            for idx, (_table_rank, title) in enumerate(parsed.soft_skills):
                log.append(
                    _upsert_matrix_skill(
                        db,
                        version_id=comp_ver.id,
                        position_code=pos,
                        department_code=dept,
                        rank=SOFT_SKILL_RANK_BASE + idx,
                        title=title,
                        is_soft=True,
                    )
                )

        # KPI: убрать HR-заглушки с медицинских регламентов
        for reg in db.scalars(
            select(PositionRegulation).where(
                PositionRegulation.template_code == TEMPLATE_CODE,
                PositionRegulation.is_current == True,
                PositionRegulation.regulation_code.in_(HOSP_MMC_REG_CODES),
            )
        ).all():
            for rk in db.scalars(
                select(RegulationKpi).where(
                    RegulationKpi.template_code == TEMPLATE_CODE,
                    RegulationKpi.regulation_code == reg.regulation_code,
                )
            ).all():
                if any(rk.kpi_code.startswith(p) for p in WRONG_KPI_PREFIXES):
                    db.delete(rk)
                    log.append(f"delete_kpi:{reg.position_code}:{rk.kpi_code}")

        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    lines = fix_hosp_skills_and_kpis(dry_run=args.dry_run)
    changed = [ln for ln in lines if not ln.startswith(("ok:", "skip:"))]
    print(f"{'Would change' if args.dry_run else 'Changed'} {len(changed)} item(s)")
    for ln in changed:
        print(f"  {ln}")


if __name__ == "__main__":
    main()
