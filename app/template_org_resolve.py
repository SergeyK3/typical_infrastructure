r"""Разрешение типовой оргструктуры: БД (template_org_units) или встроенный шаблон."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TemplateOrgUnitRow
from app.org_structures import get_template_structure


def _order_parents_before_children(rows: list[dict]) -> list[dict]:
    """Топологический порядок: родитель всегда раньше потомка (для onboarding / deploy)."""
    by_code = {r["code"]: r for r in rows}
    out: list[dict] = []
    done: set[str] = set()

    def emit(code: str) -> None:
        if code in done or code not in by_code:
            return
        spec = by_code[code]
        p = spec.get("parent_code")
        if p:
            emit(p)
        out.append(spec)
        done.add(code)

    for code in sorted(by_code.keys()):
        emit(code)
    return out


def resolve_template_structure(db: Session, template_code: str) -> list[dict]:
    """Список узлов шаблона для развёртывания и превью. Если в БД есть строки — они, иначе org_structures."""
    cnt = db.scalar(
        select(func.count()).select_from(TemplateOrgUnitRow).where(
            TemplateOrgUnitRow.template_code == template_code
        )
    )
    if cnt and cnt > 0:
        rows = db.scalars(
            select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == template_code)
        ).all()
        specs = [
            {
                "code": r.code,
                "name": r.name,
                "parent_code": r.parent_code,
                "unit_type": r.unit_type,
                "sort_order": r.sort_order,
            }
            for r in rows
        ]
        return _order_parents_before_children(specs)
    return get_template_structure(template_code)
