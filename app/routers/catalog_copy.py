# route: /api/catalog-copy | file: app/routers/catalog_copy.py
r"""Копирование отдельных записей справочников между шаблонами и организациями."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.competency_copy_ops import (
    copy_competency_matrix_row_global_to_global,
    copy_competency_matrix_row_local_to_global,
)
from app.catalog_copy_ops import (
    clone_skills_matrix_global_to_local,
    copy_kpi_local_to_global,
    copy_kpi_template_global_to_global,
    copy_org_unit_local_to_global,
    copy_position_catalog_global_to_global,
    copy_position_local_to_global,
    copy_regulation_global_to_global,
    copy_regulation_global_to_local,
    copy_regulation_local_to_global,
)
from app.db import get_db
from app.models import OrgUnit, Position, PositionCatalog
from app.schemas import (
    CatalogCopyKpiIn,
    CatalogCopyOrgUnitIn,
    CatalogCopyPositionIn,
    CatalogCopyRegulationIn,
    CatalogCopySkillIn,
    CatalogCopySkillsIn,
    KpiTemplateOut,
    PositionCatalogOut,
    PositionOut,
    PositionRegulationOut,
    TemplateOrgUnitOut,
)
from app.template_bundle_clone import resolve_client_template_code
from app.utils import new_id32

router = APIRouter(prefix="/catalog-copy", tags=["catalog_copy"])


@router.post("/regulation")
def copy_regulation(body: CatalogCopyRegulationIn, db: Session = Depends(get_db)):
    mode = body.mode.strip()
    if mode == "global_to_global":
        if not body.target_template_code:
            raise HTTPException(status_code=422, detail="target_template_code_required")
        if not body.source_regulation_code:
            raise HTTPException(status_code=422, detail="source_regulation_code_required")
        obj = copy_regulation_global_to_global(
            db,
            body.source_template_code,
            body.target_template_code,
            body.source_regulation_code,
            body.target_regulation_code,
        )
        db.commit()
        db.refresh(obj)
        return PositionRegulationOut.model_validate(obj)
    if mode == "global_to_local":
        if not body.client_id or not body.source_regulation_code:
            raise HTTPException(status_code=422, detail="client_id_and_source_regulation_code_required")
        obj = copy_regulation_global_to_local(
            db,
            body.client_id,
            body.source_template_code,
            body.source_regulation_code,
            body.target_regulation_code,
        )
        db.commit()
        from app.routers.client_regulations import _load_detail

        return _load_detail(db, obj.id)
    if mode == "local_to_global":
        if not body.source_client_regulation_id:
            raise HTTPException(status_code=422, detail="source_client_regulation_id_required")
        from app.models import ClientPositionRegulation

        cr = db.get(ClientPositionRegulation, body.source_client_regulation_id)
        tpl = body.target_template_code or (resolve_client_template_code(db, cr.client_id) if cr else None)
        if not tpl:
            raise HTTPException(status_code=422, detail="target_template_code_required")
        obj = copy_regulation_local_to_global(
            db,
            body.source_client_regulation_id,
            tpl,
            body.target_regulation_code,
        )
        db.commit()
        db.refresh(obj)
        return PositionRegulationOut.model_validate(obj)
    raise HTTPException(status_code=422, detail="invalid_copy_mode")


@router.post("/position", status_code=201)
def copy_position(body: CatalogCopyPositionIn, db: Session = Depends(get_db)):
    mode = body.mode.strip()
    if mode == "global_to_global":
        if not body.target_template_code or not body.source_position_code:
            raise HTTPException(status_code=422, detail="target_template_code_and_source_position_code_required")
        result = copy_position_catalog_global_to_global(
            db,
            body.source_template_code,
            body.target_template_code,
            body.source_position_code,
            body.target_position_code,
        )
        db.commit()
        db.refresh(result.row)
        return {
            "position": PositionCatalogOut.model_validate(result.row),
            "dept_links_created": result.dept_links_created,
            "regulations_created": result.regulations_created,
            "kpi_templates_created": result.kpi_templates_created,
            "competency_matrix_rows_created": result.competency_matrix_rows_created,
        }
    if mode == "global_to_local":
        if not body.client_id or not body.org_unit_id:
            raise HTTPException(status_code=422, detail="client_id_and_org_unit_id_required")
        if not body.source_position_code:
            raise HTTPException(status_code=422, detail="source_position_code_required")
        tpl = resolve_client_template_code(db, body.client_id)
        cat = db.get(PositionCatalog, (tpl, body.source_position_code))
        if not cat or not cat.is_active:
            if body.source_template_code != tpl:
                interim = copy_position_catalog_global_to_global(
                    db,
                    body.source_template_code,
                    tpl,
                    body.source_position_code,
                    body.target_position_code,
                )
                db.flush()
                cat = interim.row
            else:
                raise HTTPException(status_code=404, detail="position_catalog_not_found")
        ou = db.get(OrgUnit, body.org_unit_id)
        if not ou or ou.client_id != body.client_id:
            raise HTTPException(status_code=404, detail="org_unit_not_found")
        code = (body.target_position_code or cat.position_code).strip()
        obj = Position(
            id=new_id32(),
            client_id=body.client_id,
            org_unit_id=body.org_unit_id,
            code=code,
            name=cat.position_name_ru,
            grade=None,
            is_active=True,
            position_catalog_code=cat.position_code,
            function_code=cat.function_code,
            position_level=cat.position_level,
            is_managerial=cat.is_managerial,
            is_detached=True,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return {"position": PositionOut.model_validate(obj)}
    if mode == "local_to_global":
        if not body.client_id or not body.source_position_id:
            raise HTTPException(status_code=422, detail="client_id_and_source_position_id_required")
        tpl = body.target_template_code or resolve_client_template_code(db, body.client_id.strip())
        if not tpl:
            raise HTTPException(status_code=422, detail="target_template_code_required")
        result = copy_position_local_to_global(
            db,
            body.client_id.strip(),
            body.source_position_id.strip(),
            tpl,
            body.target_position_code,
        )
        db.commit()
        db.refresh(result.row)
        return {
            "position": PositionCatalogOut.model_validate(result.row),
            "created": result.created,
            "dept_links_created": result.dept_links_created,
        }
    raise HTTPException(status_code=422, detail="invalid_copy_mode")


@router.post("/org-unit", status_code=201)
def copy_org_unit(body: CatalogCopyOrgUnitIn, db: Session = Depends(get_db)):
    tpl = body.target_template_code or resolve_client_template_code(db, body.client_id.strip())
    if not tpl:
        raise HTTPException(status_code=422, detail="target_template_code_required")
    result = copy_org_unit_local_to_global(
        db,
        body.client_id.strip(),
        body.source_org_unit_id.strip(),
        tpl,
        body.target_code,
    )
    db.commit()
    db.refresh(result.row)
    return {
        "row": TemplateOrgUnitOut.model_validate(result.row),
        "created": result.created,
    }


@router.post("/kpi", status_code=201)
def copy_kpi(body: CatalogCopyKpiIn, db: Session = Depends(get_db)):
    mode = body.mode.strip()
    if mode == "local_to_global":
        if not body.client_id:
            raise HTTPException(status_code=422, detail="client_id_required")
        tpl = body.target_template_code or resolve_client_template_code(db, body.client_id.strip())
        if not tpl:
            raise HTTPException(status_code=422, detail="target_template_code_required")
        result = copy_kpi_local_to_global(
            db,
            client_id=body.client_id.strip(),
            target_template_code=tpl,
            source_client_regulation_kpi_id=body.source_client_regulation_kpi_id,
            source_client_standalone_kpi_id=body.source_client_standalone_kpi_id,
            target_kpi_code=body.target_kpi_code,
        )
        db.commit()
        db.refresh(result.row)
        return {
            "created": result.created,
            "kpi": KpiTemplateOut.model_validate(result.row),
        }
    if mode != "global_to_global":
        raise HTTPException(status_code=422, detail="invalid_copy_mode")
    if not body.target_template_code or not body.source_kpi_code:
        raise HTTPException(status_code=422, detail="target_template_code_and_source_kpi_code_required")
    result = copy_kpi_template_global_to_global(
        db,
        body.source_template_code,
        body.target_template_code,
        body.source_kpi_code,
        body.target_kpi_code,
    )
    db.commit()
    db.refresh(result.row)
    return KpiTemplateOut.model_validate(result.row)


@router.post("/skills-matrix")
def copy_skills_matrix(body: CatalogCopySkillsIn, db: Session = Depends(get_db)):
    out = clone_skills_matrix_global_to_local(db, body.client_id, body.source_template_code)
    db.commit()
    return out


@router.post("/skill", status_code=201)
def copy_skill_row(body: CatalogCopySkillIn, db: Session = Depends(get_db)):
    mode = body.mode.strip()
    if not body.target_template_code:
        raise HTTPException(status_code=422, detail="target_template_code_required")
    if mode == "local_to_global":
        if not body.client_id or not body.source_matrix_row_id:
            raise HTTPException(status_code=422, detail="client_id_and_source_matrix_row_id_required")
        result = copy_competency_matrix_row_local_to_global(
            db,
            body.client_id.strip(),
            body.source_matrix_row_id.strip(),
            body.target_template_code.strip(),
        )
    elif mode == "global_to_global":
        result = copy_competency_matrix_row_global_to_global(
            db,
            body.source_template_code,
            body.target_template_code.strip(),
            body.position_code.strip(),
            body.department_code.strip(),
            body.skill_rank,
        )
    else:
        raise HTTPException(status_code=422, detail="invalid_copy_mode")
    db.commit()
    return {
        "row_id": result.row_id,
        "created": result.created,
        "skill_definition_created": result.skill_definition_created,
    }
