# route: /api/enterprise-templates | file: app/routers/enterprise_templates.py
r"""Enterprise templates API for wizard template selection."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import require_global_admin
from app.db import get_db
from app.models import Client, EnterpriseTemplate, OrgUnit, Position, PositionDeptType, TemplateOrgUnitRow
from app.org_structures import list_positions_from_position_catalog, list_template_bundle_preview
from app.template_bundle_clone import CloneOptions, clone_template_bundle
from app.template_bundle_delete import delete_template_bundle
from app.template_org_resolve import resolve_template_structure
from app.schemas import (
    EnterpriseTemplateCloneCounts,
    EnterpriseTemplateCloneIn,
    EnterpriseTemplateCloneOut,
    EnterpriseTemplateCreate,
    EnterpriseTemplateOut,
    EnterpriseTemplatePatch,
    EnterpriseTemplateSaveFromClient,
)
from app.utils import new_id32

router = APIRouter(
    prefix="/enterprise-templates",
    tags=["enterprise-templates"],
    dependencies=[Depends(require_global_admin)],
)


def _get_template(db: Session, template_id: str) -> EnterpriseTemplate | None:
    obj = db.get(EnterpriseTemplate, template_id)
    if not obj:
        obj = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == template_id))
    return obj


@router.get("", response_model=list[EnterpriseTemplateOut])
def list_enterprise_templates(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[EnterpriseTemplateOut]:
    q = select(EnterpriseTemplate).where(EnterpriseTemplate.is_active == True)
    if not include_archived:
        q = q.where(EnterpriseTemplate.status != "archived")
    rows = db.scalars(q.order_by(EnterpriseTemplate.code)).all()
    return [EnterpriseTemplateOut.model_validate(r) for r in rows]


@router.post("", response_model=EnterpriseTemplateOut, status_code=201)
def create_enterprise_template(
    body: EnterpriseTemplateCreate, db: Session = Depends(get_db)
) -> EnterpriseTemplateOut:
    dup = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == body.code))
    if dup:
        raise HTTPException(status_code=409, detail="template_code_exists")
    obj = EnterpriseTemplate(
        id=new_id32(),
        code=body.code,
        name=body.name,
        version=body.version,
        description=body.description,
        is_active=True,
        status="active",
        author=body.author,
        comment=body.comment,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return EnterpriseTemplateOut.model_validate(obj)


@router.get("/{template_id}", response_model=EnterpriseTemplateOut)
def get_enterprise_template(template_id: str, db: Session = Depends(get_db)) -> EnterpriseTemplateOut:
    obj = _get_template(db, template_id)
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="template_not_found")
    return EnterpriseTemplateOut.model_validate(obj)


@router.patch("/{template_id}", response_model=EnterpriseTemplateOut)
def patch_enterprise_template(
    template_id: str, body: EnterpriseTemplatePatch, db: Session = Depends(get_db)
) -> EnterpriseTemplateOut:
    obj = _get_template(db, template_id)
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="template_not_found")
    if obj.status == "archived":
        raise HTTPException(status_code=409, detail="template_archived")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return EnterpriseTemplateOut.model_validate(obj)


@router.get("/{template_id}/structure-preview")
def get_structure_preview(template_id: str, db: Session = Depends(get_db)) -> dict:
    obj = _get_template(db, template_id)
    if not obj or not obj.is_active:
        raise HTTPException(status_code=404, detail="template_not_found")

    template_code = obj.code
    structure = resolve_template_structure(db, template_code)
    preview = list_template_bundle_preview(db, template_code)

    return {
        "template_id": obj.id,
        "template_code": obj.code,
        "org_units": [
            {
                "code": s["code"],
                "name": s["name"],
                "unit_type": s["unit_type"],
                "parent_code": s["parent_code"],
                "log_group": s.get("log_group"),
            }
            for s in structure
        ],
        "positions": preview["positions"],
        "kpi": preview["kpi"],
        "regulations": preview["regulations"],
        "skills": preview["skills"],
        "counts": preview["counts"],
    }


@router.post("/{template_id}/clone", response_model=EnterpriseTemplateCloneOut, status_code=201)
def clone_enterprise_template(
    template_id: str,
    body: EnterpriseTemplateCloneIn | None = None,
    db: Session = Depends(get_db),
) -> EnterpriseTemplateCloneOut:
    source = _get_template(db, template_id)
    if not source:
        raise HTTPException(status_code=404, detail="template_not_found")

    opts = body or EnterpriseTemplateCloneIn()
    try:
        new_tpl, counts = clone_template_bundle(
            db,
            source=source,
            new_code=opts.new_code,
            new_name=opts.new_name,
            code_prefix=opts.code_prefix,
            options=CloneOptions(
                copy_positions=opts.copy_positions,
                copy_kpi=opts.copy_kpi,
                copy_regulations=opts.copy_regulations,
                copy_skills=opts.copy_skills,
            ),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="bundle_clone_conflict",
        ) from exc
    db.refresh(new_tpl)
    return EnterpriseTemplateCloneOut(
        template=EnterpriseTemplateOut.model_validate(new_tpl),
        counts=EnterpriseTemplateCloneCounts(**counts.as_dict()),
    )


@router.post("/{template_id}/archive", response_model=EnterpriseTemplateOut)
def archive_enterprise_template(template_id: str, db: Session = Depends(get_db)) -> EnterpriseTemplateOut:
    obj = _get_template(db, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="template_not_found")
    obj.status = "archived"
    obj.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return EnterpriseTemplateOut.model_validate(obj)


@router.post("/{template_id}/restore", response_model=EnterpriseTemplateOut)
def restore_enterprise_template(template_id: str, db: Session = Depends(get_db)) -> EnterpriseTemplateOut:
    obj = _get_template(db, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="template_not_found")
    obj.status = "active"
    obj.archived_at = None
    db.commit()
    db.refresh(obj)
    return EnterpriseTemplateOut.model_validate(obj)


@router.delete("/{template_id}")
def delete_enterprise_template(
    template_id: str, db: Session = Depends(get_db)
) -> dict:
    """
    Необратимо удалить архивный шаблон и весь bundle (оргдерево, должности, KPI, регламенты, competency).
    Сначала архивируйте шаблон. ``default`` и шаблоны, привязанные к клиентам, удалить нельзя.
    """
    obj = _get_template(db, template_id)
    if not obj:
        raise HTTPException(status_code=404, detail="template_not_found")
    template_code = obj.code
    counts = delete_template_bundle(db, obj)
    db.commit()
    return {"deleted": True, "template_code": template_code, "counts": counts.as_dict()}


@router.post("/save-from-client", response_model=EnterpriseTemplateOut, status_code=201)
def save_template_from_client(
    body: EnterpriseTemplateSaveFromClient, db: Session = Depends(get_db)
) -> EnterpriseTemplateOut:
    if not db.get(Client, body.client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    if db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == body.code)):
        raise HTTPException(status_code=409, detail="template_code_exists")

    tpl = EnterpriseTemplate(
        id=new_id32(),
        code=body.code,
        name=body.name,
        version=body.version,
        description=body.description,
        is_active=True,
        status="draft",
        author=body.author,
        comment=body.comment,
    )
    db.add(tpl)
    db.flush()

    units = db.scalars(
        select(OrgUnit).where(OrgUnit.client_id == body.client_id).order_by(OrgUnit.sort_order.asc())
    ).all()
    id_to_code = {u.id: u.code for u in units}
    for u in units:
        parent_code = id_to_code.get(u.parent_id) if u.parent_id else None
        exists = db.scalar(
            select(func.count())
            .select_from(TemplateOrgUnitRow)
            .where(
                TemplateOrgUnitRow.template_code == body.code,
                TemplateOrgUnitRow.code == u.code,
            )
        )
        if exists:
            continue
        db.add(
            TemplateOrgUnitRow(
                id=new_id32(),
                template_code=body.code,
                code=u.code,
                name=u.name,
                parent_code=parent_code,
                unit_type=u.unit_type,
                sort_order=u.sort_order,
            )
        )

    dept_codes = {u.code for u in units if u.unit_type == "department"}
    primary_dept_by_pos: dict[str, str] = {}
    for u in units:
        if u.unit_type != "department":
            continue
        for pos in db.scalars(select(Position).where(Position.org_unit_id == u.id)).all():
            pc = (pos.position_catalog_code or pos.code or "").strip()
            if not pc:
                continue
            if pc in primary_dept_by_pos:
                continue
            if db.get(PositionDeptType, (body.code, pc, u.code)):
                continue
            primary_dept_by_pos[pc] = u.code
            db.add(
                PositionDeptType(
                    template_code=body.code,
                    position_code=pc,
                    dept_type_code=u.code,
                    is_primary=True,
                )
            )

    db.commit()
    db.refresh(tpl)
    return EnterpriseTemplateOut.model_validate(tpl)
