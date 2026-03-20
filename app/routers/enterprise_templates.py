# route: /api/enterprise-templates | file: app/routers/enterprise_templates.py
r"""Enterprise templates API for wizard template selection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EnterpriseTemplate
from app.org_structures import get_template_positions
from app.template_org_resolve import resolve_template_structure
from app.schemas import EnterpriseTemplateOut

router = APIRouter(prefix="/enterprise-templates", tags=["enterprise-templates"])


@router.get("", response_model=list[EnterpriseTemplateOut])
def list_enterprise_templates(db: Session = Depends(get_db)) -> list[EnterpriseTemplateOut]:
    """List active enterprise templates."""
    rows = db.scalars(
        select(EnterpriseTemplate).where(EnterpriseTemplate.is_active == True).order_by(EnterpriseTemplate.code)
    ).all()
    return [EnterpriseTemplateOut.model_validate(r) for r in rows]


@router.get("/{template_id}", response_model=EnterpriseTemplateOut)
def get_enterprise_template(template_id: str, db: Session = Depends(get_db)) -> EnterpriseTemplateOut:
    """Get template by ID or code."""
    obj = db.get(EnterpriseTemplate, template_id)
    if not obj:
        obj = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == template_id))
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="template_not_found")
    return EnterpriseTemplateOut.model_validate(obj)


@router.get("/{template_id}/structure-preview")
def get_structure_preview(template_id: str, db: Session = Depends(get_db)) -> dict:
    """Preview org units and positions for template (for wizard display)."""
    obj = db.get(EnterpriseTemplate, template_id)
    if not obj:
        obj = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == template_id))
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="template_not_found")

    template_code = obj.code
    structure = resolve_template_structure(db, template_code)
    ids_by_code: dict[str, str] = {}
    for s in structure:
        ids_by_code[s["code"]] = s["code"]  # placeholder for preview
    positions = get_template_positions(template_code, ids_by_code)

    return {
        "template_id": obj.id,
        "template_code": obj.code,
        "org_units": [
            {"code": s["code"], "name": s["name"], "unit_type": s["unit_type"], "parent_code": s["parent_code"]}
            for s in structure
        ],
        "positions": [
            {"code": p["code"], "name": p["name"], "org_unit_code": p["org_unit_code"]}
            for p in positions
        ],
    }
