r"""Копирование строк матрицы компетенций между шаблонами."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PositionCatalog

try:
    from skill_assessment.infrastructure.db_models import (
        CompetencyCatalogVersionRow,
        CompetencyMatrixRow,
        CompetencySkillDefinitionRow,
    )
except ImportError:
    CompetencyCatalogVersionRow = None  # type: ignore
    CompetencyMatrixRow = None  # type: ignore
    CompetencySkillDefinitionRow = None  # type: ignore


def _det_uuid(seed: str) -> str:
    return uuid5(NAMESPACE_URL, seed).hex


def _get_global_competency_version(db: Session, template_code: str) -> CompetencyCatalogVersionRow | None:
    if CompetencyCatalogVersionRow is None:
        return None
    version = db.scalar(
        select(CompetencyCatalogVersionRow)
        .where(
            CompetencyCatalogVersionRow.client_id.is_(None),
            CompetencyCatalogVersionRow.template_code == template_code,
            CompetencyCatalogVersionRow.status == "active",
        )
        .order_by(CompetencyCatalogVersionRow.created_at.desc())
        .limit(1)
    )
    if version:
        return version
    return db.scalar(
        select(CompetencyCatalogVersionRow)
        .where(
            CompetencyCatalogVersionRow.client_id.is_(None),
            CompetencyCatalogVersionRow.template_code == template_code,
        )
        .order_by(CompetencyCatalogVersionRow.created_at.desc())
        .limit(1)
    )


def _ensure_target_competency_version(
    db: Session, target_template_code: str, source_template_code: str
) -> CompetencyCatalogVersionRow:
    if CompetencyCatalogVersionRow is None:
        raise HTTPException(status_code=501, detail="competency_module_unavailable")
    existing = _get_global_competency_version(db, target_template_code)
    if existing:
        return existing
    source = _get_global_competency_version(db, source_template_code)
    new_code = f"{target_template_code}_competency_v1"
    if db.scalar(
        select(func.count())
        .select_from(CompetencyCatalogVersionRow)
        .where(CompetencyCatalogVersionRow.version_code == new_code)
    ):
        new_code = f"{target_template_code}_competency_{uuid5(NAMESPACE_URL, new_code).hex[:6]}"
    new_version_id = _det_uuid(f"sa_competency_catalog_versions:{new_code}")
    row = CompetencyCatalogVersionRow(
        id=new_version_id,
        client_id=None,
        template_code=target_template_code,
        version_code=new_code,
        title=f"Матрица компетенций ({target_template_code})",
        status="active",
        effective_from=source.effective_from if source else None,
        effective_to=source.effective_to if source else None,
        notes=f"Создана при копировании навыков из {source_template_code}" if source else None,
        source_regulation_code=source.source_regulation_code if source else None,
        source_regulation_version_no=source.source_regulation_version_no if source else None,
        replaces_version_id=None,
        published_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _ensure_skill_definition_in_template(
    db: Session,
    target_template_code: str,
    source_skill: CompetencySkillDefinitionRow,
) -> str:
    existing = db.scalar(
        select(CompetencySkillDefinitionRow).where(
            CompetencySkillDefinitionRow.client_id.is_(None),
            CompetencySkillDefinitionRow.template_code == target_template_code,
            CompetencySkillDefinitionRow.skill_code == source_skill.skill_code,
        )
    )
    if existing:
        return existing.id
    new_id = _det_uuid(f"sa_competency_skill:{target_template_code}:{source_skill.skill_code}")
    db.add(
        CompetencySkillDefinitionRow(
            id=new_id,
            client_id=None,
            template_code=target_template_code,
            skill_code=source_skill.skill_code,
            title_ru=source_skill.title_ru,
            description=source_skill.description,
            is_active=source_skill.is_active,
        )
    )
    db.flush()
    return new_id


@dataclass
class CompetencyMatrixRowCopyResult:
    row_id: str
    created: bool
    skill_definition_created: bool


def copy_competency_matrix_row_global_to_global(
    db: Session,
    source_template_code: str,
    target_template_code: str,
    position_code: str,
    department_code: str,
    skill_rank: int,
    *,
    target_department_code: str | None = None,
) -> CompetencyMatrixRowCopyResult:
    if CompetencyMatrixRow is None:
        raise HTTPException(status_code=501, detail="competency_module_unavailable")
    if not db.get(PositionCatalog, (target_template_code, position_code)):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "position_not_in_target_template",
                "message": "Должность отсутствует в целевом шаблоне.",
            },
        )
    from app.catalog_copy_ops import resolve_dept_type_for_target

    source_version = _get_global_competency_version(db, source_template_code)
    if not source_version:
        raise HTTPException(status_code=404, detail="source_competency_version_not_found")
    source_row = db.scalar(
        select(CompetencyMatrixRow).where(
            CompetencyMatrixRow.version_id == source_version.id,
            CompetencyMatrixRow.position_code == position_code,
            CompetencyMatrixRow.department_code == department_code,
            CompetencyMatrixRow.skill_rank == skill_rank,
        )
    )
    if not source_row:
        raise HTTPException(status_code=404, detail="competency_matrix_row_not_found")
    source_skill = db.get(CompetencySkillDefinitionRow, source_row.skill_definition_id)
    if not source_skill:
        raise HTTPException(status_code=404, detail="competency_skill_not_found")

    target_version = _ensure_target_competency_version(db, target_template_code, source_template_code)
    dept = target_department_code or resolve_dept_type_for_target(
        db, target_template_code, source_row.department_code
    )
    exists = db.scalar(
        select(CompetencyMatrixRow.id).where(
            CompetencyMatrixRow.version_id == target_version.id,
            CompetencyMatrixRow.position_code == position_code,
            CompetencyMatrixRow.department_code == dept,
            CompetencyMatrixRow.skill_rank == skill_rank,
        )
    )
    if exists:
        return CompetencyMatrixRowCopyResult(row_id=exists, created=False, skill_definition_created=False)

    before_skill = db.scalar(
        select(func.count())
        .select_from(CompetencySkillDefinitionRow)
        .where(
            CompetencySkillDefinitionRow.client_id.is_(None),
            CompetencySkillDefinitionRow.template_code == target_template_code,
            CompetencySkillDefinitionRow.skill_code == source_skill.skill_code,
        )
    )
    skill_id = _ensure_skill_definition_in_template(db, target_template_code, source_skill)
    skill_created = not before_skill
    new_row_id = _det_uuid(
        f"sa_competency_matrix:{target_version.id}:{position_code}:{dept}:{skill_rank}"
    )
    db.add(
        CompetencyMatrixRow(
            id=new_row_id,
            version_id=target_version.id,
            position_code=position_code,
            department_code=dept,
            skill_definition_id=skill_id,
            skill_rank=skill_rank,
            is_active=source_row.is_active,
        )
    )
    db.flush()
    return CompetencyMatrixRowCopyResult(
        row_id=new_row_id, created=True, skill_definition_created=bool(skill_created)
    )


def copy_position_competency_matrix_global_to_global(
    db: Session,
    source_template_code: str,
    target_template_code: str,
    source_position_code: str,
    target_position_code: str,
) -> int:
    if CompetencyMatrixRow is None:
        return 0
    from app.catalog_copy_ops import resolve_dept_type_for_target

    source_version = _get_global_competency_version(db, source_template_code)
    if not source_version:
        return 0
    target_version = _ensure_target_competency_version(db, target_template_code, source_template_code)
    created = 0
    for matrix_row in db.scalars(
        select(CompetencyMatrixRow).where(
            CompetencyMatrixRow.version_id == source_version.id,
            CompetencyMatrixRow.position_code == source_position_code,
        )
    ).all():
        source_skill = db.get(CompetencySkillDefinitionRow, matrix_row.skill_definition_id)
        if not source_skill:
            continue
        dept = resolve_dept_type_for_target(db, target_template_code, matrix_row.department_code)
        exists = db.scalar(
            select(CompetencyMatrixRow.id).where(
                CompetencyMatrixRow.version_id == target_version.id,
                CompetencyMatrixRow.position_code == target_position_code,
                CompetencyMatrixRow.department_code == dept,
                CompetencyMatrixRow.skill_rank == matrix_row.skill_rank,
            )
        )
        if exists:
            continue
        skill_id = _ensure_skill_definition_in_template(db, target_template_code, source_skill)
        db.add(
            CompetencyMatrixRow(
                id=_det_uuid(
                    f"sa_competency_matrix:{target_version.id}:"
                    f"{target_position_code}:{dept}:{matrix_row.skill_rank}"
                ),
                version_id=target_version.id,
                position_code=target_position_code,
                department_code=dept,
                skill_definition_id=skill_id,
                skill_rank=matrix_row.skill_rank,
                is_active=matrix_row.is_active,
            )
        )
        created += 1
    db.flush()
    return created


def _ensure_client_matrix_row(db: Session, client_id: str, row_id: str) -> CompetencyMatrixRow:
    row = db.get(CompetencyMatrixRow, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="competency_matrix_row_not_found")
    version = db.get(CompetencyCatalogVersionRow, row.version_id)
    if version is None or version.client_id != client_id:
        raise HTTPException(status_code=400, detail="competency_matrix_row_not_for_client")
    return row


def _strip_client_skill_suffix(skill_code: str) -> str:
    idx = skill_code.rfind("_")
    if idx > 0 and len(skill_code) - idx - 1 == 8 and skill_code[idx + 1 :].isalnum():
        return skill_code[:idx]
    return skill_code


def _upsert_global_skill_from_client(
    db: Session,
    target_template_code: str,
    source_skill: CompetencySkillDefinitionRow,
) -> tuple[str, bool]:
    by_title = db.scalar(
        select(CompetencySkillDefinitionRow).where(
            CompetencySkillDefinitionRow.client_id.is_(None),
            CompetencySkillDefinitionRow.template_code == target_template_code,
            CompetencySkillDefinitionRow.title_ru == source_skill.title_ru,
        )
    )
    if by_title:
        return by_title.id, False

    skill_code = _strip_client_skill_suffix(source_skill.skill_code.strip())
    existing = db.scalar(
        select(CompetencySkillDefinitionRow).where(
            CompetencySkillDefinitionRow.client_id.is_(None),
            CompetencySkillDefinitionRow.template_code == target_template_code,
            CompetencySkillDefinitionRow.skill_code == skill_code,
        )
    )
    if existing:
        return existing.id, False

    new_id = _det_uuid(f"sa_competency_skill:{target_template_code}:{skill_code}")
    db.add(
        CompetencySkillDefinitionRow(
            id=new_id,
            client_id=None,
            template_code=target_template_code,
            skill_code=skill_code,
            title_ru=source_skill.title_ru,
            description=source_skill.description,
            is_active=source_skill.is_active,
        )
    )
    db.flush()
    return new_id, True


def copy_competency_matrix_row_local_to_global(
    db: Session,
    client_id: str,
    source_row_id: str,
    target_template_code: str,
) -> CompetencyMatrixRowCopyResult:
    if CompetencyMatrixRow is None:
        raise HTTPException(status_code=501, detail="competency_module_unavailable")
    source_row = _ensure_client_matrix_row(db, client_id, source_row_id)
    source_skill = db.get(CompetencySkillDefinitionRow, source_row.skill_definition_id)
    if not source_skill:
        raise HTTPException(status_code=404, detail="competency_skill_not_found")

    position_code = source_row.position_code.strip()
    if not db.get(PositionCatalog, (target_template_code, position_code)):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "position_not_in_target_template",
                "message": f"Должность «{position_code}» отсутствует в глобальном справочнике шаблона «{target_template_code}».",
            },
        )

    from app.catalog_copy_ops import resolve_dept_type_for_target

    target_version = _ensure_target_competency_version(db, target_template_code, target_template_code)
    dept = resolve_dept_type_for_target(db, target_template_code, source_row.department_code)
    exists = db.scalar(
        select(CompetencyMatrixRow.id).where(
            CompetencyMatrixRow.version_id == target_version.id,
            CompetencyMatrixRow.position_code == position_code,
            CompetencyMatrixRow.department_code == dept,
            CompetencyMatrixRow.skill_rank == source_row.skill_rank,
        )
    )
    if exists:
        return CompetencyMatrixRowCopyResult(row_id=exists, created=False, skill_definition_created=False)

    skill_id, skill_created = _upsert_global_skill_from_client(db, target_template_code, source_skill)
    new_row_id = _det_uuid(
        f"sa_competency_matrix:{target_version.id}:{position_code}:{dept}:{source_row.skill_rank}"
    )
    db.add(
        CompetencyMatrixRow(
            id=new_row_id,
            version_id=target_version.id,
            position_code=position_code,
            department_code=dept,
            skill_definition_id=skill_id,
            skill_rank=source_row.skill_rank,
            is_active=source_row.is_active,
        )
    )
    db.flush()
    return CompetencyMatrixRowCopyResult(
        row_id=new_row_id, created=True, skill_definition_created=skill_created
    )
