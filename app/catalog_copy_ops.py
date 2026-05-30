r"""Копирование отдельных записей между глобальными шаблонами и локальными справочниками."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.client_catalog_sync import copy_global_regulation_to_client
from app.models import (
    Client,
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    ClientStandaloneKpi,
    KpiTemplate,
    OrgUnit,
    Position,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
    TemplateOrgUnitRow,
)
from app.org_unit_ops import PROTECTED_ORG_CODES, format_org_unit_name, normalize_template_log_group
from app.position_catalog_ops import PositionCatalogCloneResult, _unique_code, clone_position_catalog
from app.template_bundle_clone import resolve_client_template_code
from app.utils import new_id32

DEFAULT_FALLBACK_DEPT = "HR"


def _template_department_codes(db: Session, template_code: str) -> set[str]:
    return set(
        db.scalars(
            select(TemplateOrgUnitRow.code).where(
                TemplateOrgUnitRow.template_code == template_code,
                TemplateOrgUnitRow.unit_type == "department",
            )
        ).all()
    )


def resolve_dept_type_for_target(db: Session, target_template_code: str, preferred: str) -> str:
    """Подобрать тип подразделения в целевом шаблоне; при отсутствии — HR."""
    depts = _template_department_codes(db, target_template_code)
    pref = (preferred or "").strip()
    if pref in depts:
        return pref
    if DEFAULT_FALLBACK_DEPT in depts:
        return DEFAULT_FALLBACK_DEPT
    raise HTTPException(
        status_code=400,
        detail={
            "code": "dept_type_not_found",
            "message": (
                f"Тип подразделения «{pref}» отсутствует в шаблоне {target_template_code}, "
                f"резерв «{DEFAULT_FALLBACK_DEPT}» тоже не найден."
            ),
        },
    )


def _assert_template_dept(db: Session, template_code: str, dept_code: str) -> None:
    ok = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.code == dept_code,
            TemplateOrgUnitRow.unit_type == "department",
        )
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "dept_type_not_found", "message": f"Тип подразделения {dept_code} не найден в шаблоне {template_code}."},
        )


def _existing_regulation_codes(db: Session, template_code: str) -> set[str]:
    return set(
        db.scalars(
            select(PositionRegulation.regulation_code).where(PositionRegulation.template_code == template_code)
        ).all()
    )


@dataclass
class RegulationCloneResult:
    row: PositionRegulation
    kpis_created: int
    instructions_created: int


def clone_regulation(db: Session, source: PositionRegulation) -> RegulationCloneResult:
    tpl = source.template_code
    codes = _existing_regulation_codes(db, tpl)
    new_code = _unique_code(codes, source.regulation_code)

    copy_name = source.regulation_name
    if "Копия" not in copy_name:
        copy_name = f"{copy_name} (Копия)"

    obj = PositionRegulation(
        id=new_id32(),
        template_code=tpl,
        regulation_code=new_code,
        position_code=source.position_code,
        dept_type_code=source.dept_type_code,
        regulation_name=copy_name,
        goal_summary=source.goal_summary,
        ckp_short=source.ckp_short,
        ckp_full=source.ckp_full,
        google_doc_url=source.google_doc_url,
        instructions_folder_url=source.instructions_folder_url,
        version_no=source.version_no,
        status=source.status,
        effective_from=source.effective_from,
        effective_to=source.effective_to,
        is_current=source.is_current,
        owner_unit_code=source.owner_unit_code,
        notes=source.notes,
    )
    db.add(obj)
    db.flush()

    kpis_created = 0
    for rk in db.scalars(
        select(RegulationKpi).where(
            RegulationKpi.template_code == tpl,
            RegulationKpi.regulation_code == source.regulation_code,
        )
    ).all():
        db.add(
            RegulationKpi(
                id=new_id32(),
                template_code=tpl,
                regulation_code=new_code,
                kpi_code=rk.kpi_code,
                target_value=rk.target_value,
                period_type=rk.period_type,
                weight=rk.weight,
                is_required=rk.is_required,
            )
        )
        kpis_created += 1

    instructions_created = 0
    for ri in db.scalars(
        select(RegulationInstruction)
        .where(
            RegulationInstruction.template_code == tpl,
            RegulationInstruction.regulation_code == source.regulation_code,
        )
        .order_by(RegulationInstruction.sort_order)
    ).all():
        db.add(
            RegulationInstruction(
                id=new_id32(),
                template_code=tpl,
                regulation_code=new_code,
                instruction_code=ri.instruction_code,
                instruction_name=ri.instruction_name,
                instruction_url=ri.instruction_url,
                is_required=ri.is_required,
                sort_order=ri.sort_order,
            )
        )
        instructions_created += 1

    db.flush()
    return RegulationCloneResult(row=obj, kpis_created=kpis_created, instructions_created=instructions_created)


def copy_regulation_global_to_global(
    db: Session,
    source_template_code: str,
    target_template_code: str,
    source_regulation_code: str,
    target_regulation_code: str | None = None,
) -> PositionRegulation:
    src = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == source_template_code,
            PositionRegulation.regulation_code == source_regulation_code,
        )
    )
    if not src:
        raise HTTPException(status_code=404, detail="global_regulation_not_found")
    if source_template_code == target_template_code:
        return clone_regulation(db, src).row
    target_dept = resolve_dept_type_for_target(db, target_template_code, src.dept_type_code)
    if not db.get(PositionCatalog, (target_template_code, src.position_code)):
        raise HTTPException(
            status_code=400,
            detail={"code": "position_not_in_target_template", "message": "Должность отсутствует в целевом шаблоне."},
        )
    codes = _existing_regulation_codes(db, target_template_code)
    new_code = (target_regulation_code or source_regulation_code).strip()
    if new_code in codes:
        raise HTTPException(status_code=409, detail="regulation_code_already_exists")
    obj = PositionRegulation(
        id=new_id32(),
        template_code=target_template_code,
        regulation_code=new_code,
        position_code=src.position_code,
        dept_type_code=target_dept,
        regulation_name=src.regulation_name,
        goal_summary=src.goal_summary,
        ckp_short=src.ckp_short,
        ckp_full=src.ckp_full,
        google_doc_url=src.google_doc_url,
        instructions_folder_url=src.instructions_folder_url,
        version_no=src.version_no,
        status=src.status,
        effective_from=src.effective_from,
        effective_to=src.effective_to,
        is_current=src.is_current,
        owner_unit_code=src.owner_unit_code,
        notes=src.notes,
    )
    db.add(obj)
    db.flush()
    for rk in db.scalars(
        select(RegulationKpi).where(
            RegulationKpi.template_code == source_template_code,
            RegulationKpi.regulation_code == source_regulation_code,
        )
    ).all():
        db.add(
            RegulationKpi(
                id=new_id32(),
                template_code=target_template_code,
                regulation_code=new_code,
                kpi_code=rk.kpi_code,
                target_value=rk.target_value,
                period_type=rk.period_type,
                weight=rk.weight,
                is_required=rk.is_required,
            )
        )
    for ri in db.scalars(
        select(RegulationInstruction)
        .where(
            RegulationInstruction.template_code == source_template_code,
            RegulationInstruction.regulation_code == source_regulation_code,
        )
        .order_by(RegulationInstruction.sort_order)
    ).all():
        db.add(
            RegulationInstruction(
                id=new_id32(),
                template_code=target_template_code,
                regulation_code=new_code,
                instruction_code=ri.instruction_code,
                instruction_name=ri.instruction_name,
                instruction_url=ri.instruction_url,
                is_required=ri.is_required,
                sort_order=ri.sort_order,
            )
        )
    db.flush()
    return obj


def copy_regulation_local_to_global(
    db: Session,
    client_regulation_id: str,
    target_template_code: str | None = None,
    target_regulation_code: str | None = None,
) -> PositionRegulation:
    client_reg = db.get(ClientPositionRegulation, client_regulation_id)
    if not client_reg:
        raise HTTPException(status_code=404, detail="client_regulation_not_found")
    tpl = target_template_code or resolve_client_template_code(db, client_reg.client_id)
    target_dept = resolve_dept_type_for_target(db, tpl, client_reg.dept_type_code)
    if not db.get(PositionCatalog, (tpl, client_reg.position_code)):
        raise HTTPException(
            status_code=400,
            detail={"code": "position_not_in_target_template", "message": "Должность отсутствует в целевом шаблоне."},
        )
    codes = _existing_regulation_codes(db, tpl)
    new_code = (target_regulation_code or client_reg.regulation_code).strip()
    if new_code in codes:
        raise HTTPException(status_code=409, detail="regulation_code_already_exists")
    obj = PositionRegulation(
        id=new_id32(),
        template_code=tpl,
        regulation_code=new_code,
        position_code=client_reg.position_code,
        dept_type_code=target_dept,
        regulation_name=client_reg.regulation_name,
        goal_summary=client_reg.goal_summary,
        ckp_short=client_reg.ckp_short,
        ckp_full=client_reg.ckp_full,
        google_doc_url=client_reg.google_doc_url,
        instructions_folder_url=client_reg.instructions_folder_url,
        version_no=client_reg.version_no,
        status=client_reg.status,
        effective_from=client_reg.effective_from,
        effective_to=client_reg.effective_to,
        is_current=client_reg.is_current,
        owner_unit_code=client_reg.owner_unit_code,
        notes=client_reg.notes,
    )
    db.add(obj)
    db.flush()
    for k in db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == client_regulation_id)
    ).all():
        db.add(
            RegulationKpi(
                id=new_id32(),
                template_code=tpl,
                regulation_code=new_code,
                kpi_code=k.kpi_code,
                target_value=k.target_value,
                period_type=k.period_type,
                weight=k.weight,
                is_required=k.is_required,
            )
        )
    for ins in db.scalars(
        select(ClientRegulationInstruction)
        .where(ClientRegulationInstruction.client_regulation_id == client_regulation_id)
        .order_by(ClientRegulationInstruction.sort_order)
    ).all():
        db.add(
            RegulationInstruction(
                id=new_id32(),
                template_code=tpl,
                regulation_code=new_code,
                instruction_code=ins.instruction_code,
                instruction_name=ins.instruction_name,
                instruction_url=ins.instruction_url,
                is_required=ins.is_required,
                sort_order=ins.sort_order,
            )
        )
    db.flush()
    return obj


def copy_regulation_global_to_local(
    db: Session,
    client_id: str,
    source_template_code: str,
    source_regulation_code: str,
    target_regulation_code: str | None = None,
) -> ClientPositionRegulation:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client_not_found")
    client_tpl = resolve_client_template_code(db, client_id)
    glob = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == source_template_code,
            PositionRegulation.regulation_code == source_regulation_code,
        )
    )
    if not glob:
        raise HTTPException(status_code=404, detail="global_regulation_not_found")
    if source_template_code != client_tpl:
        exists_in_client_tpl = db.scalar(
            select(func.count())
            .select_from(PositionRegulation)
            .where(
                PositionRegulation.template_code == client_tpl,
                PositionRegulation.regulation_code == source_regulation_code,
            )
        )
        if not exists_in_client_tpl:
            copy_regulation_global_to_global(db, source_template_code, client_tpl, source_regulation_code)
            db.flush()
        glob = db.scalar(
            select(PositionRegulation).where(
                PositionRegulation.template_code == client_tpl,
                PositionRegulation.regulation_code == source_regulation_code,
            )
        )
        if not glob:
            raise HTTPException(status_code=500, detail="regulation_copy_failed")
    target_code = (target_regulation_code or source_regulation_code).strip()
    existing = db.scalar(
        select(ClientPositionRegulation).where(
            ClientPositionRegulation.client_id == client_id,
            ClientPositionRegulation.global_regulation_code == source_regulation_code,
        )
    )
    if not existing:
        existing = db.scalar(
            select(ClientPositionRegulation).where(
                ClientPositionRegulation.client_id == client_id,
                ClientPositionRegulation.regulation_code == target_code,
            )
        )
    if existing:
        from app.client_catalog_sync import sync_client_regulation_children_from_global

        sync_client_regulation_children_from_global(db, existing.id)
        db.flush()
        return existing
    obj = copy_global_regulation_to_client(db, client_id, glob, target_regulation_code)
    if not obj:
        raise HTTPException(status_code=409, detail="client_regulation_code_exists")
    return obj


def copy_position_catalog_global_to_global(
    db: Session,
    source_template_code: str,
    target_template_code: str,
    source_position_code: str,
    target_position_code: str | None = None,
) -> PositionCatalogCloneResult:
    source = db.get(PositionCatalog, (source_template_code, source_position_code))
    if not source:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    if source_template_code == target_template_code:
        return clone_position_catalog(db, source)

    position_codes = set(
        db.scalars(select(PositionCatalog.position_code).where(PositionCatalog.template_code == target_template_code)).all()
    )
    new_code = (target_position_code or source_position_code).strip()
    if new_code in position_codes:
        raise HTTPException(status_code=409, detail="position_code_already_exists")

    links = db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == source_template_code,
            PositionDeptType.position_code == source_position_code,
        )
    ).all()

    row = PositionCatalog(
        template_code=target_template_code,
        position_code=new_code,
        position_name_ru=source.position_name_ru,
        position_name_en=source.position_name_en,
        function_code=source.function_code,
        position_level=source.position_level,
        is_managerial=source.is_managerial,
        position_family=source.position_family,
        is_active=source.is_active,
        default_regulation_code=None,
        notes=source.notes,
        sort_order=source.sort_order,
    )
    db.add(row)
    db.flush()

    dept_links_created = 0
    resolved_links: list[tuple[str, bool]] = [
        (resolve_dept_type_for_target(db, target_template_code, link.dept_type_code), bool(link.is_primary))
        for link in links
    ]
    if not resolved_links:
        resolved_links = [
            (resolve_dept_type_for_target(db, target_template_code, DEFAULT_FALLBACK_DEPT), True)
        ]
    added_depts: set[str] = set()
    primary_set = False
    for dept, is_primary in resolved_links:
        if dept in added_depts:
            continue
        want_primary = is_primary and not primary_set
        if db.get(PositionDeptType, (target_template_code, new_code, dept)):
            added_depts.add(dept)
            continue
        db.add(
            PositionDeptType(
                template_code=target_template_code,
                position_code=new_code,
                dept_type_code=dept,
                is_primary=want_primary,
            )
        )
        if want_primary:
            primary_set = True
        added_depts.add(dept)
        dept_links_created += 1
    if dept_links_created and not primary_set:
        first_link = db.scalars(
            select(PositionDeptType).where(
                PositionDeptType.template_code == target_template_code,
                PositionDeptType.position_code == new_code,
            ).limit(1)
        ).first()
        if first_link:
            first_link.is_primary = True

    regulations_created = 0
    reg_code_map: dict[str, str] = {}
    regulation_codes = _existing_regulation_codes(db, target_template_code)
    source_regs = db.scalars(
        select(PositionRegulation).where(
            PositionRegulation.template_code == source_template_code,
            PositionRegulation.position_code == source_position_code,
        )
    ).all()
    for reg in source_regs:
        target_dept = resolve_dept_type_for_target(db, target_template_code, reg.dept_type_code)
        if reg.regulation_code not in reg_code_map:
            reg_code_map[reg.regulation_code] = _unique_code(regulation_codes | set(reg_code_map.values()), reg.regulation_code)
        new_reg_code = reg_code_map[reg.regulation_code]
        if db.scalar(
            select(func.count())
            .select_from(PositionRegulation)
            .where(
                PositionRegulation.template_code == target_template_code,
                PositionRegulation.regulation_code == new_reg_code,
            )
        ):
            continue
        db.add(
            PositionRegulation(
                id=new_id32(),
                template_code=target_template_code,
                regulation_code=new_reg_code,
                position_code=new_code,
                dept_type_code=target_dept,
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
                RegulationKpi.template_code == source_template_code,
                RegulationKpi.regulation_code == old_code,
            )
        ).all():
            db.add(
                RegulationKpi(
                    id=new_id32(),
                    template_code=target_template_code,
                    regulation_code=new_reg_code,
                    kpi_code=rk.kpi_code,
                    target_value=rk.target_value,
                    period_type=rk.period_type,
                    weight=rk.weight,
                    is_required=rk.is_required,
                )
            )

    kpi_codes = set(
        db.scalars(select(KpiTemplate.kpi_code).where(KpiTemplate.template_code == target_template_code)).all()
    )
    kpi_templates_created = 0
    for kpi in db.scalars(
        select(KpiTemplate).where(
            KpiTemplate.template_code == source_template_code,
            KpiTemplate.position_code == source_position_code,
        )
    ).all():
        new_kpi_code = _unique_code(kpi_codes, kpi.kpi_code)
        kpi_codes.add(new_kpi_code)
        db.add(
            KpiTemplate(
                template_code=target_template_code,
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

    from app.competency_copy_ops import copy_position_competency_matrix_global_to_global

    competency_matrix_rows_created = copy_position_competency_matrix_global_to_global(
        db,
        source_template_code,
        target_template_code,
        source_position_code,
        new_code,
    )

    db.flush()
    return PositionCatalogCloneResult(
        row=row,
        dept_links_created=dept_links_created,
        regulations_created=regulations_created,
        kpi_templates_created=kpi_templates_created,
        competency_matrix_rows_created=competency_matrix_rows_created,
    )


@dataclass
class KpiTemplateCopyResult:
    row: KpiTemplate
    created: bool


def clone_kpi_template(db: Session, source: KpiTemplate) -> KpiTemplate:
    tpl = source.template_code
    codes = set(db.scalars(select(KpiTemplate.kpi_code).where(KpiTemplate.template_code == tpl)).all())
    new_code = _unique_code(codes, source.kpi_code)

    copy_name = source.kpi_name
    if "Копия" not in copy_name:
        copy_name = f"{copy_name} (Копия)"

    row = KpiTemplate(
        template_code=tpl,
        kpi_code=new_code,
        kpi_name=copy_name,
        unit=source.unit,
        period_type=source.period_type,
        formula_or_rule=source.formula_or_rule,
        default_target=source.default_target,
        is_active=source.is_active,
        position_code=source.position_code,
    )
    db.add(row)
    db.flush()
    return row


def copy_kpi_template_global_to_global(
    db: Session,
    source_template_code: str,
    target_template_code: str,
    source_kpi_code: str,
    target_kpi_code: str | None = None,
) -> KpiTemplateCopyResult:
    src = db.get(KpiTemplate, (source_template_code, source_kpi_code))
    if not src:
        raise HTTPException(status_code=404, detail="kpi_template_not_found")
    if source_template_code == target_template_code:
        return KpiTemplateCopyResult(row=clone_kpi_template(db, src), created=True)
    if src.position_code:
        if not db.get(PositionCatalog, (target_template_code, src.position_code)):
            raise HTTPException(
                status_code=400,
                detail={"code": "position_not_in_target_template", "message": "Должность KPI отсутствует в целевом шаблоне."},
            )
    codes = set(db.scalars(select(KpiTemplate.kpi_code).where(KpiTemplate.template_code == target_template_code)).all())
    new_code = (target_kpi_code or source_kpi_code).strip()
    if new_code in codes:
        raise HTTPException(status_code=409, detail="kpi_code_already_exists")
    row = KpiTemplate(
        template_code=target_template_code,
        kpi_code=new_code,
        kpi_name=src.kpi_name,
        unit=src.unit,
        period_type=src.period_type,
        formula_or_rule=src.formula_or_rule,
        default_target=src.default_target,
        is_active=src.is_active,
        position_code=src.position_code,
    )
    db.add(row)
    db.flush()
    return KpiTemplateCopyResult(row=row, created=True)


@dataclass
class TemplateOrgUnitCopyResult:
    row: TemplateOrgUnitRow
    created: bool


@dataclass
class PositionLocalToGlobalResult:
    row: PositionCatalog
    created: bool
    dept_links_created: int


def _ensure_template_parent_exists(db: Session, template_code: str, parent_code: str | None) -> None:
    if not parent_code:
        return
    ok = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.code == parent_code,
        )
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "template_org_parent_not_found",
                "message": f"Родительский узел «{parent_code}» отсутствует в целевом шаблоне — скопируйте его сначала.",
            },
        )


def copy_org_unit_local_to_global(
    db: Session,
    client_id: str,
    source_org_unit_id: str,
    target_template_code: str,
    target_code: str | None = None,
) -> TemplateOrgUnitCopyResult:
    ou = db.get(OrgUnit, source_org_unit_id)
    if not ou or ou.client_id != client_id:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    if ou.code in PROTECTED_ORG_CODES:
        raise HTTPException(status_code=400, detail="org_unit_copy_not_allowed")

    code = (target_code or ou.code).strip()
    existing = db.scalar(
        select(TemplateOrgUnitRow).where(
            TemplateOrgUnitRow.template_code == target_template_code,
            TemplateOrgUnitRow.code == code,
        )
    )
    if existing:
        return TemplateOrgUnitCopyResult(row=existing, created=False)

    parent_code: str | None = None
    if ou.parent_id:
        parent = db.get(OrgUnit, ou.parent_id)
        if parent:
            parent_code = parent.code
    _ensure_template_parent_exists(db, target_template_code, parent_code)

    row = TemplateOrgUnitRow(
        id=new_id32(),
        template_code=target_template_code,
        code=code,
        name=format_org_unit_name(ou.name, ou.unit_type),
        parent_code=parent_code,
        unit_type=ou.unit_type,
        sort_order=ou.sort_order,
        log_group=normalize_template_log_group(ou.unit_type, ou.code if ou.unit_type == "department" else None),
    )
    db.add(row)
    db.flush()
    return TemplateOrgUnitCopyResult(row=row, created=True)


def _dept_type_hint_for_position(db: Session, pos: Position) -> str:
    ou = db.get(OrgUnit, pos.org_unit_id)
    if not ou:
        return (pos.function_code or "").strip()
    if ou.unit_type == "department":
        return ou.code
    if ou.parent_id:
        parent = db.get(OrgUnit, ou.parent_id)
        if parent and parent.unit_type == "department":
            return parent.code
    return (pos.function_code or ou.code or "").strip()


def copy_position_local_to_global(
    db: Session,
    client_id: str,
    source_position_id: str,
    target_template_code: str,
    target_position_code: str | None = None,
) -> PositionLocalToGlobalResult:
    pos = db.get(Position, source_position_id)
    if not pos or pos.client_id != client_id:
        raise HTTPException(status_code=404, detail="position_not_found")

    new_code = (target_position_code or pos.position_catalog_code or pos.code).strip()
    existing = db.get(PositionCatalog, (target_template_code, new_code))
    if existing:
        return PositionLocalToGlobalResult(row=existing, created=False, dept_links_created=0)

    dept_hint = _dept_type_hint_for_position(db, pos)
    function_code = (pos.function_code or dept_hint or DEFAULT_FALLBACK_DEPT).strip()
    dept_type = resolve_dept_type_for_target(db, target_template_code, dept_hint or function_code)

    row = PositionCatalog(
        template_code=target_template_code,
        position_code=new_code,
        position_name_ru=pos.name,
        position_name_en=None,
        function_code=function_code,
        position_level=pos.position_level or "SPEC",
        is_managerial=bool(pos.is_managerial) if pos.is_managerial is not None else False,
        position_family=None,
        is_active=pos.is_active,
        default_regulation_code=None,
        notes=None,
        sort_order=0,
    )
    db.add(row)
    db.flush()

    dept_links_created = 0
    if not db.get(PositionDeptType, (target_template_code, new_code, dept_type)):
        db.add(
            PositionDeptType(
                template_code=target_template_code,
                position_code=new_code,
                dept_type_code=dept_type,
                is_primary=True,
            )
        )
        dept_links_created = 1

    return PositionLocalToGlobalResult(row=row, created=True, dept_links_created=dept_links_created)


def copy_kpi_local_to_global(
    db: Session,
    *,
    client_id: str,
    target_template_code: str,
    source_client_regulation_kpi_id: str | None = None,
    source_client_standalone_kpi_id: str | None = None,
    target_kpi_code: str | None = None,
) -> KpiTemplateCopyResult:
    kpi_code: str | None = None
    target_value: float | None = None
    period_type = "month"
    position_code: str | None = None

    if source_client_regulation_kpi_id:
        ck = db.get(ClientRegulationKpi, source_client_regulation_kpi_id)
        if not ck:
            raise HTTPException(status_code=404, detail="client_regulation_kpi_not_found")
        cr = db.get(ClientPositionRegulation, ck.client_regulation_id)
        if not cr or cr.client_id != client_id:
            raise HTTPException(status_code=400, detail="client_regulation_kpi_not_for_client")
        kpi_code = ck.kpi_code
        target_value = ck.target_value
        period_type = ck.period_type
        position_code = cr.position_code
    elif source_client_standalone_kpi_id:
        sk = db.get(ClientStandaloneKpi, source_client_standalone_kpi_id)
        if not sk or sk.client_id != client_id:
            raise HTTPException(status_code=404, detail="client_standalone_kpi_not_found")
        kpi_code = sk.kpi_code
        target_value = sk.target_value
        period_type = sk.period_type
        position_code = sk.position_code
    else:
        raise HTTPException(status_code=422, detail="kpi_source_required")

    final_code = (target_kpi_code or kpi_code or "").strip()
    existing = db.get(KpiTemplate, (target_template_code, final_code))
    if existing:
        return KpiTemplateCopyResult(row=existing, created=False)

    client_tpl = resolve_client_template_code(db, client_id)
    meta = db.get(KpiTemplate, (client_tpl, kpi_code))
    if not meta:
        meta = db.scalar(select(KpiTemplate).where(KpiTemplate.kpi_code == kpi_code).limit(1))

    if position_code and not db.get(PositionCatalog, (target_template_code, position_code)):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "position_not_in_target_template",
                "message": f"Должность «{position_code}» отсутствует в глобальном справочнике шаблона «{target_template_code}».",
            },
        )

    row = KpiTemplate(
        template_code=target_template_code,
        kpi_code=final_code,
        kpi_name=meta.kpi_name if meta else final_code,
        unit=meta.unit if meta else "%",
        period_type=period_type or (meta.period_type if meta else "month"),
        formula_or_rule=meta.formula_or_rule if meta else None,
        default_target=target_value if target_value is not None else (meta.default_target if meta else None),
        is_active=True,
        position_code=position_code,
    )
    db.add(row)
    db.flush()
    return KpiTemplateCopyResult(row=row, created=True)


def clone_skills_matrix_global_to_local(
    db: Session, client_id: str, source_template_code: str | None = None
) -> dict:
    from skill_assessment.services.client_matrix_clone import clone_global_matrices_to_client

    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client_not_found")
    return clone_global_matrices_to_client(db, client_id, source_template_code=source_template_code)
