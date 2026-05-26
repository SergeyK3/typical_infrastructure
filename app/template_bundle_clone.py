r"""Клонирование изолированного bundle шаблона предприятия (оргструктура + справочники)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    EnterpriseTemplate,
    KpiTemplate,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
    TemplateOrgUnitRow,
)
from app.template_constants import DEFAULT_TEMPLATE_CODE
from app.utils import new_id32

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


@dataclass
class CloneOptions:
    copy_positions: bool = True
    copy_kpi: bool = True
    copy_regulations: bool = True
    copy_skills: bool = True


@dataclass
class CloneCounts:
    org_units: int = 0
    positions: int = 0
    position_links: int = 0
    kpi: int = 0
    regulations: int = 0
    regulation_kpis: int = 0
    regulation_instructions: int = 0
    skill_definitions: int = 0
    competency_matrix_rows: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "org_units": self.org_units,
            "positions": self.positions,
            "position_links": self.position_links,
            "kpi": self.kpi,
            "regulations": self.regulations,
            "regulation_kpis": self.regulation_kpis,
            "regulation_instructions": self.regulation_instructions,
            "skill_definitions": self.skill_definitions,
            "competency_matrix_rows": self.competency_matrix_rows,
        }


def _det_uuid(seed: str) -> str:
    return str(uuid5(NAMESPACE_URL, seed))


def _map_code(code: str, code_map: dict[str, str]) -> str:
    return code_map.get(code, code)


def _build_code_map(rows: list[TemplateOrgUnitRow], code_prefix: str | None) -> dict[str, str]:
    prefix = (code_prefix or "").strip()
    out: dict[str, str] = {}
    for r in rows:
        out[r.code] = f"{prefix}{r.code}" if prefix else r.code
    return out


def _allocate_new_code(db: Session, base_code: str, explicit: str | None) -> str:
    if explicit:
        if db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == explicit)):
            raise HTTPException(status_code=409, detail="template_code_exists")
        return explicit
    n = 1
    new_code = f"{base_code}_copy"
    while db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == new_code)):
        n += 1
        new_code = f"{base_code}_copy_{n}"
    return new_code


def _dept_codes(rows: list[TemplateOrgUnitRow]) -> set[str]:
    return {r.code for r in rows if r.unit_type == "department"}


def clone_template_bundle(
    db: Session,
    *,
    source: EnterpriseTemplate,
    new_code: str | None = None,
    new_name: str | None = None,
    code_prefix: str | None = None,
    options: CloneOptions | None = None,
) -> tuple[EnterpriseTemplate, CloneCounts]:
    opts = options or CloneOptions()
    src = source.code
    target_code = _allocate_new_code(db, source.code, new_code)

    tpl = EnterpriseTemplate(
        id=new_id32(),
        code=target_code,
        name=new_name or f"{source.name} (копия)",
        version=source.version,
        description=source.description,
        is_active=True,
        status="draft",
        author=source.author,
        comment=f"Клон bundle {source.code}",
        cloned_from_id=source.id,
    )
    db.add(tpl)
    db.flush()

    counts = CloneCounts()
    rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == src)
    ).all()
    code_map = _build_code_map(rows, code_prefix)

    for r in rows:
        new_node_code = code_map[r.code]
        if db.scalar(
            select(func.count())
            .select_from(TemplateOrgUnitRow)
            .where(
                TemplateOrgUnitRow.template_code == target_code,
                TemplateOrgUnitRow.code == new_node_code,
            )
        ):
            new_node_code = f"{new_node_code}_{new_id32()[:6]}"
            code_map[r.code] = new_node_code
        parent = code_map.get(r.parent_code) if r.parent_code else None
        db.add(
            TemplateOrgUnitRow(
                id=new_id32(),
                template_code=target_code,
                code=new_node_code,
                name=format_org_unit_name(r.name, r.unit_type),
                parent_code=parent,
                unit_type=r.unit_type,
                sort_order=r.sort_order,
                log_group=r.log_group,
            )
        )
        counts.org_units += 1

    dept_codes = _dept_codes(rows)
    position_codes: set[str] = set()

    if opts.copy_positions:
        position_codes, counts.position_links = _clone_positions(
            db, src, target_code, dept_codes, code_map, code_prefix, counts
        )

    if opts.copy_kpi:
        counts.kpi, _ = _clone_kpi_templates(
            db, src, target_code, position_codes, code_map, code_prefix
        )

    if opts.copy_regulations:
        reg_counts, _ = _clone_regulations(
            db, src, target_code, dept_codes, position_codes, code_map, code_prefix
        )
        counts.regulations = reg_counts.regulations
        counts.regulation_kpis = reg_counts.regulation_kpis
        counts.regulation_instructions = reg_counts.regulation_instructions

    if opts.copy_skills and CompetencyCatalogVersionRow is not None:
        skill_counts = _clone_competency_bundle(
            db, src, target_code, dept_codes, position_codes, code_map, code_prefix
        )
        counts.skill_definitions = skill_counts.skill_definitions
        counts.competency_matrix_rows = skill_counts.competency_matrix_rows

    db.flush()
    return tpl, counts


def _remap_entity_code(code: str | None, code_prefix: str | None, code_map: dict[str, str]) -> str | None:
    if not code:
        return None
    if code in code_map:
        return code_map[code]
    prefix = (code_prefix or "").strip()
    if prefix:
        return f"{prefix}{code}"
    return code


def _clone_positions(
    db: Session,
    src: str,
    target_code: str,
    dept_codes: set[str],
    code_map: dict[str, str],
    code_prefix: str | None,
    counts: CloneCounts,
) -> tuple[set[str], int]:
    position_codes: set[str] = set()
    links_created = 0
    for link in db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == src,
            PositionDeptType.dept_type_code.in_(dept_codes),
        )
    ).all():
        position_codes.add(link.position_code)
        new_dept = _map_code(link.dept_type_code, code_map)
        new_pos = _remap_entity_code(link.position_code, code_prefix, code_map) or link.position_code
        if db.get(PositionDeptType, (target_code, new_pos, new_dept)):
            continue
        db.add(
            PositionDeptType(
                template_code=target_code,
                position_code=new_pos,
                dept_type_code=new_dept,
                is_primary=link.is_primary,
            )
        )
        links_created += 1

    for pc in position_codes:
        cat = db.get(PositionCatalog, (src, pc))
        if not cat:
            continue
        new_pc = _remap_entity_code(pc, code_prefix, code_map) or pc
        if db.get(PositionCatalog, (target_code, new_pc)):
            continue
        db.add(
            PositionCatalog(
                template_code=target_code,
                position_code=new_pc,
                position_name_ru=cat.position_name_ru,
                position_name_en=cat.position_name_en,
                function_code=cat.function_code,
                position_level=cat.position_level,
                is_managerial=cat.is_managerial,
                position_family=cat.position_family,
                is_active=cat.is_active,
                default_regulation_code=_remap_entity_code(
                    cat.default_regulation_code, code_prefix, code_map
                ),
                notes=cat.notes,
                sort_order=cat.sort_order,
            )
        )
        counts.positions += 1

    return {_remap_entity_code(pc, code_prefix, code_map) or pc for pc in position_codes}, links_created


def _clone_kpi_templates(
    db: Session,
    src: str,
    target_code: str,
    position_codes: set[str],
    code_map: dict[str, str],
    code_prefix: str | None,
) -> tuple[int, set[str]]:
    created = 0
    kpi_codes: set[str] = set()
    for row in db.scalars(select(KpiTemplate).where(KpiTemplate.template_code == src)).all():
        if row.position_code:
            src_pos = row.position_code
            mapped = _remap_entity_code(src_pos, code_prefix, code_map) or src_pos
            if src_pos not in position_codes and mapped not in position_codes:
                continue
        new_kpi_code = _remap_entity_code(row.kpi_code, code_prefix, code_map) or row.kpi_code
        if db.get(KpiTemplate, (target_code, new_kpi_code)):
            continue
        new_pos = _remap_entity_code(row.position_code, code_prefix, code_map)
        db.add(
            KpiTemplate(
                template_code=target_code,
                kpi_code=new_kpi_code,
                kpi_name=row.kpi_name,
                unit=row.unit,
                period_type=row.period_type,
                formula_or_rule=row.formula_or_rule,
                default_target=row.default_target,
                is_active=row.is_active,
                position_code=new_pos,
            )
        )
        kpi_codes.add(new_kpi_code)
        created += 1
    return created, kpi_codes


@dataclass
class _RegCloneCounts:
    regulations: int = 0
    regulation_kpis: int = 0
    regulation_instructions: int = 0


def _clone_regulations(
    db: Session,
    src: str,
    target_code: str,
    dept_codes: set[str],
    position_codes: set[str],
    code_map: dict[str, str],
    code_prefix: str | None,
) -> tuple[_RegCloneCounts, set[str]]:
    counts = _RegCloneCounts()
    regulation_codes: set[str] = set()
    reg_code_map: dict[str, str] = {}

    for reg in db.scalars(select(PositionRegulation).where(PositionRegulation.template_code == src)).all():
        if reg.dept_type_code not in dept_codes:
            continue
        if reg.position_code not in position_codes:
            mapped_pos = _remap_entity_code(reg.position_code, code_prefix, code_map)
            if not mapped_pos or mapped_pos not in position_codes:
                continue
        new_reg_code = _remap_entity_code(reg.regulation_code, code_prefix, code_map) or reg.regulation_code
        reg_code_map[reg.regulation_code] = new_reg_code
        if db.scalar(
            select(func.count())
            .select_from(PositionRegulation)
            .where(
                PositionRegulation.template_code == target_code,
                PositionRegulation.regulation_code == new_reg_code,
            )
        ):
            continue
        db.add(
            PositionRegulation(
                id=new_id32(),
                template_code=target_code,
                regulation_code=new_reg_code,
                position_code=_remap_entity_code(reg.position_code, code_prefix, code_map) or reg.position_code,
                dept_type_code=_map_code(reg.dept_type_code, code_map),
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
                owner_unit_code=_map_code(reg.owner_unit_code, code_map) if reg.owner_unit_code else None,
                notes=reg.notes,
            )
        )
        regulation_codes.add(new_reg_code)
        counts.regulations += 1

    for old_code, new_reg_code in reg_code_map.items():
        for rk in db.scalars(
            select(RegulationKpi).where(
                RegulationKpi.template_code == src,
                RegulationKpi.regulation_code == old_code,
            )
        ).all():
            db.add(
                RegulationKpi(
                    id=new_id32(),
                    template_code=target_code,
                    regulation_code=new_reg_code,
                    kpi_code=_remap_entity_code(rk.kpi_code, code_prefix, code_map) or rk.kpi_code,
                    target_value=rk.target_value,
                    period_type=rk.period_type,
                    weight=rk.weight,
                    is_required=rk.is_required,
                )
            )
            counts.regulation_kpis += 1
        for ri in db.scalars(
            select(RegulationInstruction).where(
                RegulationInstruction.template_code == src,
                RegulationInstruction.regulation_code == old_code,
            )
        ).all():
            db.add(
                RegulationInstruction(
                    id=new_id32(),
                    template_code=target_code,
                    regulation_code=new_reg_code,
                    instruction_code=_remap_entity_code(ri.instruction_code, code_prefix, code_map)
                    or ri.instruction_code,
                    instruction_name=ri.instruction_name,
                    instruction_url=ri.instruction_url,
                    is_required=ri.is_required,
                    sort_order=ri.sort_order,
                )
            )
            counts.regulation_instructions += 1

    return counts, regulation_codes


@dataclass
class _SkillCloneCounts:
    skill_definitions: int = 0
    competency_matrix_rows: int = 0


def _clone_competency_bundle(
    db: Session,
    src: str,
    target_code: str,
    dept_codes: set[str],
    position_codes: set[str],
    code_map: dict[str, str],
    code_prefix: str | None,
) -> _SkillCloneCounts:
    counts = _SkillCloneCounts()
    if CompetencyCatalogVersionRow is None:
        return counts

    version = db.scalar(
        select(CompetencyCatalogVersionRow)
        .where(
            CompetencyCatalogVersionRow.client_id.is_(None),
            CompetencyCatalogVersionRow.template_code == src,
            CompetencyCatalogVersionRow.status == "active",
        )
        .order_by(CompetencyCatalogVersionRow.created_at.desc())
        .limit(1)
    )
    if not version:
        version = db.scalar(
            select(CompetencyCatalogVersionRow)
            .where(
                CompetencyCatalogVersionRow.client_id.is_(None),
                CompetencyCatalogVersionRow.template_code == src,
            )
            .order_by(CompetencyCatalogVersionRow.created_at.desc())
            .limit(1)
        )
    if not version:
        return counts

    new_version_code = f"{target_code}_competency_v1"
    if db.scalar(
        select(func.count())
        .select_from(CompetencyCatalogVersionRow)
        .where(CompetencyCatalogVersionRow.version_code == new_version_code)
    ):
        new_version_code = f"{target_code}_competency_{new_id32()[:6]}"

    new_version_id = _det_uuid(f"sa_competency_catalog_versions:{new_version_code}")
    new_version = CompetencyCatalogVersionRow(
        id=new_version_id,
        client_id=None,
        template_code=target_code,
        version_code=new_version_code,
        title=f"Матрица компетенций ({target_code})",
        status="active",
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        notes=f"Клон из {version.version_code}",
        source_regulation_code=version.source_regulation_code,
        source_regulation_version_no=version.source_regulation_version_no,
        replaces_version_id=None,
        published_at=datetime.now(timezone.utc),
    )
    db.add(new_version)
    db.flush()

    skill_id_map: dict[str, str] = {}
    matrix_rows = db.scalars(
        select(CompetencyMatrixRow).where(CompetencyMatrixRow.version_id == version.id)
    ).all()

    for row in matrix_rows:
        if row.department_code not in dept_codes:
            continue
        if row.position_code not in position_codes:
            mapped_pos = _remap_entity_code(row.position_code, code_prefix, code_map)
            if not mapped_pos or mapped_pos not in position_codes:
                continue
        old_skill = db.get(CompetencySkillDefinitionRow, row.skill_definition_id)
        if not old_skill:
            continue
        new_skill_code = _remap_entity_code(old_skill.skill_code, code_prefix, code_map) or old_skill.skill_code
        if old_skill.id not in skill_id_map:
            existing = db.scalar(
                select(CompetencySkillDefinitionRow).where(
                    CompetencySkillDefinitionRow.client_id.is_(None),
                    CompetencySkillDefinitionRow.template_code == target_code,
                    CompetencySkillDefinitionRow.skill_code == new_skill_code,
                )
            )
            if existing:
                skill_id_map[old_skill.id] = existing.id
            else:
                new_skill_id = _det_uuid(f"sa_competency_skill:{target_code}:{new_skill_code}")
                db.add(
                    CompetencySkillDefinitionRow(
                        id=new_skill_id,
                        client_id=None,
                        template_code=target_code,
                        skill_code=new_skill_code,
                        title_ru=old_skill.title_ru,
                        description=old_skill.description,
                        is_active=old_skill.is_active,
                    )
                )
                skill_id_map[old_skill.id] = new_skill_id
                counts.skill_definitions += 1

        db.add(
            CompetencyMatrixRow(
                id=_det_uuid(
                    f"sa_competency_matrix:{new_version_id}:"
                    f"{_remap_entity_code(row.position_code, code_prefix, code_map)}:"
                    f"{_map_code(row.department_code, code_map)}:{row.skill_rank}"
                ),
                version_id=new_version_id,
                position_code=_remap_entity_code(row.position_code, code_prefix, code_map) or row.position_code,
                department_code=_map_code(row.department_code, code_map),
                skill_definition_id=skill_id_map[old_skill.id],
                skill_rank=row.skill_rank,
                is_active=row.is_active,
            )
        )
        counts.competency_matrix_rows += 1

    return counts


def resolve_client_template_code(db: Session, client_id: str) -> str:
    from app.models import Client

    client = db.get(Client, client_id)
    if not client or not client.template_id:
        return DEFAULT_TEMPLATE_CODE
    tpl = db.get(EnterpriseTemplate, client.template_id)
    return tpl.code if tpl else DEFAULT_TEMPLATE_CODE
