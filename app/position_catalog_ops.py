r"""Операции клонирования записей глобального каталога типовых должностей."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Client,
    EnterpriseTemplate,
    KpiTemplate,
    Position,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
    TemplateOrgUnitRow,
    TemplateSegmentCode,
)
from app.utils import new_id32

try:
    from skill_assessment.infrastructure.db_models import CompetencyCatalogVersionRow, CompetencyMatrixRow
except ImportError:
    CompetencyCatalogVersionRow = None  # type: ignore
    CompetencyMatrixRow = None  # type: ignore


def get_primary_dept_type_code(db: Session, template_code: str, position_code: str) -> str | None:
    return db.scalar(
        select(PositionDeptType.dept_type_code).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.position_code == position_code,
            PositionDeptType.is_primary == True,
        ).limit(1)
    )


def is_template_dept_or_segment_code(db: Session, template_code: str, code: str) -> bool:
    """Код отделения из оргструктуры или код сегмента из словаря шаблона."""
    dept_ok = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.code == code,
            TemplateOrgUnitRow.unit_type == "department",
        )
    )
    if dept_ok:
        return True
    return db.get(TemplateSegmentCode, (template_code, code)) is not None


def set_primary_dept_type(
    db: Session,
    template_code: str,
    position_code: str,
    dept_type_code: str,
) -> None:
    code = dept_type_code.strip()
    if not code:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_dept_type_code", "message": "Тип подразделения не может быть пустым."},
        )
    dept_ok = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.code == code,
            TemplateOrgUnitRow.unit_type == "department",
        )
    )
    if not dept_ok and not db.get(TemplateSegmentCode, (template_code, code)):
        raise HTTPException(status_code=400, detail="dept_type_not_found")

    links = list(
        db.scalars(
            select(PositionDeptType).where(
                PositionDeptType.template_code == template_code,
                PositionDeptType.position_code == position_code,
            )
        ).all()
    )
    target = next((link for link in links if link.dept_type_code == code), None)
    if target is None:
        target = PositionDeptType(
            template_code=template_code,
            position_code=position_code,
            dept_type_code=code,
            is_primary=True,
        )
        db.add(target)
    for link in links:
        link.is_primary = link.dept_type_code == code
    if target not in links:
        target.is_primary = True


def _unique_code(existing: set[str], base: str) -> str:
    candidate = f"{base}_COPY"
    if candidate not in existing:
        return candidate
    n = 2
    while True:
        candidate = f"{base}_COPY_{n}"
        if candidate not in existing:
            return candidate
        n += 1


def rename_position_catalog_code(db: Session, row: PositionCatalog, new_code: str) -> PositionCatalog:
    """Переименовать код типовой должности и обновить связанные справочники."""
    new_code = new_code.strip()
    if not new_code:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_position_code", "message": "Код должности не может быть пустым."},
        )
    if new_code == row.position_code:
        return row

    tpl = row.template_code
    old_code = row.position_code
    if db.get(PositionCatalog, (tpl, new_code)):
        raise HTTPException(status_code=409, detail="position_code_exists")

    new_row = PositionCatalog(
        template_code=tpl,
        position_code=new_code,
        position_name_ru=row.position_name_ru,
        position_name_en=row.position_name_en,
        function_code=row.function_code,
        position_level=row.position_level,
        is_managerial=row.is_managerial,
        position_family=row.position_family,
        is_active=row.is_active,
        default_regulation_code=row.default_regulation_code,
        notes=row.notes,
        sort_order=row.sort_order,
    )
    db.add(new_row)
    db.flush()

    for link in db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == tpl,
            PositionDeptType.position_code == old_code,
        )
    ).all():
        db.add(
            PositionDeptType(
                template_code=tpl,
                position_code=new_code,
                dept_type_code=link.dept_type_code,
                is_primary=link.is_primary,
            )
        )
        db.delete(link)

    db.execute(
        update(PositionRegulation)
        .where(
            PositionRegulation.template_code == tpl,
            PositionRegulation.position_code == old_code,
        )
        .values(position_code=new_code)
    )
    db.execute(
        update(KpiTemplate)
        .where(
            KpiTemplate.template_code == tpl,
            KpiTemplate.position_code == old_code,
        )
        .values(position_code=new_code)
    )

    if CompetencyMatrixRow is not None and CompetencyCatalogVersionRow is not None:
        version_ids = db.scalars(
            select(CompetencyCatalogVersionRow.id).where(
                CompetencyCatalogVersionRow.client_id.is_(None),
                CompetencyCatalogVersionRow.template_code == tpl,
            )
        ).all()
        if version_ids:
            db.execute(
                update(CompetencyMatrixRow)
                .where(
                    CompetencyMatrixRow.version_id.in_(version_ids),
                    CompetencyMatrixRow.position_code == old_code,
                )
                .values(position_code=new_code)
            )

    client_ids = db.scalars(
        select(Client.id)
        .join(EnterpriseTemplate, Client.template_id == EnterpriseTemplate.id)
        .where(EnterpriseTemplate.code == tpl)
    ).all()
    if client_ids:
        db.execute(
            update(Position)
            .where(
                Position.client_id.in_(client_ids),
                Position.position_catalog_code == old_code,
            )
            .values(position_catalog_code=new_code)
        )

    db.delete(row)
    db.flush()
    return new_row


@dataclass
class PositionCatalogCloneResult:
    row: PositionCatalog
    dept_links_created: int
    regulations_created: int
    kpi_templates_created: int
    competency_matrix_rows_created: int


def clone_position_catalog(db: Session, source: PositionCatalog) -> PositionCatalogCloneResult:
    tpl = source.template_code
    position_codes = set(
        db.scalars(select(PositionCatalog.position_code).where(PositionCatalog.template_code == tpl)).all()
    )
    new_code = _unique_code(position_codes, source.position_code)

    copy_name = source.position_name_ru
    if "Копия" not in copy_name:
        copy_name = f"{copy_name} (Копия)"

    regulation_codes = set(
        db.scalars(
            select(PositionRegulation.regulation_code).where(PositionRegulation.template_code == tpl)
        ).all()
    )
    reg_code_map: dict[str, str] = {}
    source_regs = db.scalars(
        select(PositionRegulation).where(
            PositionRegulation.template_code == tpl,
            PositionRegulation.position_code == source.position_code,
        )
    ).all()
    for reg in source_regs:
        if reg.regulation_code not in reg_code_map:
            reg_code_map[reg.regulation_code] = _unique_code(
                regulation_codes | set(reg_code_map.values()),
                reg.regulation_code,
            )

    new_default_reg = source.default_regulation_code
    if new_default_reg and new_default_reg in reg_code_map:
        new_default_reg = reg_code_map[new_default_reg]

    row = PositionCatalog(
        template_code=tpl,
        position_code=new_code,
        position_name_ru=copy_name,
        position_name_en=source.position_name_en,
        function_code=source.function_code,
        position_level=source.position_level,
        is_managerial=source.is_managerial,
        position_family=source.position_family,
        is_active=source.is_active,
        default_regulation_code=new_default_reg,
        notes=source.notes,
        sort_order=source.sort_order,
    )
    db.add(row)
    db.flush()

    dept_links_created = 0
    for link in db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == tpl,
            PositionDeptType.position_code == source.position_code,
        )
    ).all():
        if db.get(PositionDeptType, (tpl, new_code, link.dept_type_code)):
            continue
        db.add(
            PositionDeptType(
                template_code=tpl,
                position_code=new_code,
                dept_type_code=link.dept_type_code,
                is_primary=link.is_primary,
            )
        )
        dept_links_created += 1

    regulations_created = 0
    for reg in source_regs:
        new_reg_code = reg_code_map[reg.regulation_code]
        db.add(
            PositionRegulation(
                id=new_id32(),
                template_code=tpl,
                regulation_code=new_reg_code,
                position_code=new_code,
                dept_type_code=reg.dept_type_code,
                regulation_name=reg.regulation_name,
                goal_summary=reg.goal_summary,
                ckp_short=reg.ckp_short,
                ckp_full=reg.ckp_full,
                google_doc_url=reg.google_doc_url,
                instructions_folder_url=reg.instructions_folder_url,
                version_no=reg.version_no,
                status=reg.status,
                effective_from=reg.effective_from,
                effective_to=reg.effective_to,
                is_current=reg.is_current,
                owner_unit_code=reg.owner_unit_code,
                notes=reg.notes,
            )
        )
        regulations_created += 1

    for old_code, new_reg_code in reg_code_map.items():
        for rk in db.scalars(
            select(RegulationKpi).where(
                RegulationKpi.template_code == tpl,
                RegulationKpi.regulation_code == old_code,
            )
        ).all():
            db.add(
                RegulationKpi(
                    id=new_id32(),
                    template_code=tpl,
                    regulation_code=new_reg_code,
                    kpi_code=rk.kpi_code,
                    target_value=rk.target_value,
                    period_type=rk.period_type,
                    weight=rk.weight,
                    is_required=rk.is_required,
                )
            )
        for ri in db.scalars(
            select(RegulationInstruction).where(
                RegulationInstruction.template_code == tpl,
                RegulationInstruction.regulation_code == old_code,
            )
        ).all():
            db.add(
                RegulationInstruction(
                    id=new_id32(),
                    template_code=tpl,
                    regulation_code=new_reg_code,
                    instruction_code=ri.instruction_code,
                    instruction_name=ri.instruction_name,
                    instruction_url=ri.instruction_url,
                    is_required=ri.is_required,
                    sort_order=ri.sort_order,
                )
            )

    kpi_codes = set(
        db.scalars(select(KpiTemplate.kpi_code).where(KpiTemplate.template_code == tpl)).all()
    )
    kpi_templates_created = 0
    for kpi in db.scalars(
        select(KpiTemplate).where(
            KpiTemplate.template_code == tpl,
            KpiTemplate.position_code == source.position_code,
        )
    ).all():
        new_kpi_code = _unique_code(kpi_codes, kpi.kpi_code)
        kpi_codes.add(new_kpi_code)
        db.add(
            KpiTemplate(
                template_code=tpl,
                kpi_code=new_kpi_code,
                kpi_name=kpi.kpi_name,
                unit=kpi.unit,
                period_type=kpi.period_type,
                formula_or_rule=kpi.formula_or_rule,
                default_target=kpi.default_target,
                is_active=kpi.is_active,
                position_code=new_code,
            )
        )
        kpi_templates_created += 1

    competency_matrix_rows_created = 0
    if CompetencyMatrixRow is not None and CompetencyCatalogVersionRow is not None:
        version_ids = db.scalars(
            select(CompetencyCatalogVersionRow.id).where(
                CompetencyCatalogVersionRow.client_id.is_(None),
                CompetencyCatalogVersionRow.template_code == tpl,
            )
        ).all()
        if version_ids:
            for matrix_row in db.scalars(
                select(CompetencyMatrixRow).where(
                    CompetencyMatrixRow.version_id.in_(version_ids),
                    CompetencyMatrixRow.position_code == source.position_code,
                )
            ).all():
                exists = db.scalar(
                    select(CompetencyMatrixRow.id).where(
                        CompetencyMatrixRow.version_id == matrix_row.version_id,
                        CompetencyMatrixRow.position_code == new_code,
                        CompetencyMatrixRow.department_code == matrix_row.department_code,
                        CompetencyMatrixRow.skill_rank == matrix_row.skill_rank,
                    )
                )
                if exists:
                    continue
                db.add(
                    CompetencyMatrixRow(
                        id=str(uuid4()),
                        version_id=matrix_row.version_id,
                        position_code=new_code,
                        department_code=matrix_row.department_code,
                        skill_definition_id=matrix_row.skill_definition_id,
                        skill_rank=matrix_row.skill_rank,
                        is_active=matrix_row.is_active,
                    )
                )
                competency_matrix_rows_created += 1

    db.flush()
    return PositionCatalogCloneResult(
        row=row,
        dept_links_created=dept_links_created,
        regulations_created=regulations_created,
        kpi_templates_created=kpi_templates_created,
        competency_matrix_rows_created=competency_matrix_rows_created,
    )
