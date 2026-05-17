"""Compatibility helpers for the local skill assessment module.

The Stage3HR module can build competency/KPI catalog snapshots from the core
regulation registry. The current core does not yet store competency matrices in
regulation text, so skill extraction is intentionally empty and migration-safe.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KpiTemplate, PositionRegulation, RegulationKpi


def extract_all_regulation_table_skills(db: Session) -> list[dict[str, Any]]:
    """Return extracted skill rows from regulation markdown tables.

    This core clone does not have the Stage3HR markdown matrix extractor yet.
    Keeping the function present lets the optional module import and run; future
    extraction can fill the same row shape without changing the plugin contract.
    """

    return []


def list_kpi_rows_from_regulation_registry(db: Session) -> list[dict[str, Any]]:
    """Return KPI rows linked to current global position regulations."""

    stmt = (
        select(PositionRegulation, RegulationKpi, KpiTemplate)
        .join(RegulationKpi, RegulationKpi.regulation_code == PositionRegulation.regulation_code)
        .join(KpiTemplate, KpiTemplate.kpi_code == RegulationKpi.kpi_code, isouter=True)
        .where(PositionRegulation.is_current.is_(True))
        .order_by(PositionRegulation.position_code, PositionRegulation.dept_type_code, RegulationKpi.kpi_code)
    )
    rows: list[dict[str, Any]] = []
    for reg, kpi, template in db.execute(stmt).all():
        rows.append(
            {
                "regulation_code": reg.regulation_code,
                "position_code": reg.position_code,
                "department_code": reg.dept_type_code,
                "kpi_code": kpi.kpi_code,
                "kpi_title_ru": template.kpi_name if template else kpi.kpi_code,
                "unit": template.unit if template else "%",
                "period_type": kpi.period_type or (template.period_type if template else "month"),
                "default_target": kpi.target_value if kpi.target_value is not None else (template.default_target if template else None),
            }
        )
    return rows
