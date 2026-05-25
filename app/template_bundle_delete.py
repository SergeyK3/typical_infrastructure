r"""Полное удаление bundle шаблона и связанных глобальных записей."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
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
    Client,
)
from app.template_constants import DEFAULT_TEMPLATE_CODE

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
class TemplateDeleteCounts:
    org_units: int = 0
    position_links: int = 0
    positions: int = 0
    kpi: int = 0
    regulations: int = 0
    regulation_kpis: int = 0
    regulation_instructions: int = 0
    competency_matrix_rows: int = 0
    skill_definitions: int = 0
    competency_versions: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "org_units": self.org_units,
            "position_links": self.position_links,
            "positions": self.positions,
            "kpi": self.kpi,
            "regulations": self.regulations,
            "regulation_kpis": self.regulation_kpis,
            "regulation_instructions": self.regulation_instructions,
            "competency_matrix_rows": self.competency_matrix_rows,
            "skill_definitions": self.skill_definitions,
            "competency_versions": self.competency_versions,
        }


def assert_template_can_be_deleted(db: Session, template: EnterpriseTemplate) -> None:
    if template.code == DEFAULT_TEMPLATE_CODE:
        raise HTTPException(status_code=403, detail="template_protected")
    if template.status != "archived":
        raise HTTPException(
            status_code=409,
            detail="template_not_archived",
        )
    clients = db.scalar(
        select(func.count()).select_from(Client).where(Client.template_id == template.id)
    )
    if clients:
        raise HTTPException(status_code=409, detail="template_in_use_by_clients")


def delete_template_bundle(db: Session, template: EnterpriseTemplate) -> TemplateDeleteCounts:
    """Удалить шаблон и все глобальные записи с его template_code (необратимо)."""
    assert_template_can_be_deleted(db, template)
    code = template.code
    counts = TemplateDeleteCounts()

    if CompetencyCatalogVersionRow is not None:
        version_ids = list(
            db.scalars(
                select(CompetencyCatalogVersionRow.id).where(
                    CompetencyCatalogVersionRow.template_code == code,
                    CompetencyCatalogVersionRow.client_id.is_(None),
                )
            ).all()
        )
        if version_ids and CompetencyMatrixRow is not None:
            res = db.execute(
                delete(CompetencyMatrixRow).where(CompetencyMatrixRow.version_id.in_(version_ids))
            )
            counts.competency_matrix_rows = res.rowcount or 0
        if CompetencySkillDefinitionRow is not None:
            res = db.execute(
                delete(CompetencySkillDefinitionRow).where(
                    CompetencySkillDefinitionRow.template_code == code,
                    CompetencySkillDefinitionRow.client_id.is_(None),
                )
            )
            counts.skill_definitions = res.rowcount or 0
        res = db.execute(
            delete(CompetencyCatalogVersionRow).where(
                CompetencyCatalogVersionRow.template_code == code,
                CompetencyCatalogVersionRow.client_id.is_(None),
            )
        )
        counts.competency_versions = res.rowcount or 0

    res = db.execute(delete(RegulationInstruction).where(RegulationInstruction.template_code == code))
    counts.regulation_instructions = res.rowcount or 0

    res = db.execute(delete(RegulationKpi).where(RegulationKpi.template_code == code))
    counts.regulation_kpis = res.rowcount or 0

    res = db.execute(delete(PositionRegulation).where(PositionRegulation.template_code == code))
    counts.regulations = res.rowcount or 0

    res = db.execute(delete(KpiTemplate).where(KpiTemplate.template_code == code))
    counts.kpi = res.rowcount or 0

    res = db.execute(delete(PositionDeptType).where(PositionDeptType.template_code == code))
    counts.position_links = res.rowcount or 0

    res = db.execute(delete(PositionCatalog).where(PositionCatalog.template_code == code))
    counts.positions = res.rowcount or 0

    res = db.execute(delete(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == code))
    counts.org_units = res.rowcount or 0

    db.execute(
        update(EnterpriseTemplate)
        .where(EnterpriseTemplate.cloned_from_id == template.id)
        .values(cloned_from_id=None)
    )

    db.delete(template)
    return counts
