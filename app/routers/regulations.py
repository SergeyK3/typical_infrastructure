# route: /api/regulations | file: app/routers/regulations.py
r"""API для справочника регламентов должностей."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import (
    KpiTemplate,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
    TemplateOrgUnitRow,
)
from app.template_constants import DEFAULT_TEMPLATE_CODE
from app.catalog_copy_ops import clone_regulation
from app.regulation_ops import (
    ensure_regulation_position_code,
    ensure_regulation_slot_available,
    rename_regulation_code,
)
from app.position_catalog_ops import get_primary_dept_type_code, is_template_dept_or_segment_code
from app.schemas import (
    ListEnvelope,
    PositionRegulationCreate,
    PositionRegulationDetailOut,
    PositionRegulationOut,
    PositionRegulationPatch,
    RegulationCloneOut,
    RegulationFromWebIn,
    RegulationFromWebOut,
    RegulationInstructionOut,
    RegulationKpiOut,
)

router = APIRouter(prefix="/regulations", tags=["regulations"])


def _regulation_out(db: Session, row: PositionRegulation) -> PositionRegulationOut:
    base = PositionRegulationOut.model_validate(row)
    catalog_dept = get_primary_dept_type_code(db, row.template_code, row.position_code)
    return base.model_copy(update={"catalog_dept_type_code": catalog_dept})


def _id(prefix: str, code: str) -> str:
    return uuid5(NAMESPACE_URL, f"seed:{prefix}:{code}").hex


def _ilike_any_regulation_column(raw: str):
    """Подстроковый поиск по основным полям (без %/_ как масок — экранируем)."""
    frag = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{frag}%"
    return or_(
        PositionRegulation.regulation_code.ilike(pat, escape="\\"),
        PositionRegulation.regulation_name.ilike(pat, escape="\\"),
        PositionRegulation.position_code.ilike(pat, escape="\\"),
        PositionRegulation.dept_type_code.ilike(pat, escape="\\"),
        func.coalesce(PositionRegulation.goal_summary, "").ilike(pat, escape="\\"),
        func.coalesce(PositionRegulation.notes, "").ilike(pat, escape="\\"),
    )


@router.get("", response_model=ListEnvelope[PositionRegulationOut])
def list_regulations(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    position_code: str | None = Query(None, description="Фильтр по должности"),
    dept_type_code: str | None = Query(None, description="Фильтр по типу подразделения"),
    status: str | None = Query(None, description="Фильтр по статусу"),
    is_current: bool | None = Query(None, description="Только действующие"),
    search: str | None = Query(
        None,
        max_length=200,
        description="Поиск по коду, названию, должности, типу подразделения, цели, заметкам (общесистемный реестр)",
    ),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PositionRegulationOut]:
    filters: list = [PositionRegulation.template_code == template_code]
    if position_code:
        filters.append(PositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(PositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(PositionRegulation.status == status)
    if is_current is not None:
        filters.append(PositionRegulation.is_current == is_current)
    if search and (s := search.strip()):
        filters.append(_ilike_any_regulation_column(s))

    q = select(PositionRegulation)
    count_q = select(func.count()).select_from(PositionRegulation)
    for f in filters:
        q = q.where(f)
        count_q = count_q.where(f)

    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(PositionRegulation.position_code, PositionRegulation.dept_type_code, PositionRegulation.version_no)
        .limit(limit)
        .offset(offset)
    ).all()
    return ListEnvelope[PositionRegulationOut](
        items=[_regulation_out(db, r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# Статические маршруты — до {regulation_code}, иначе "kpi-templates" и "positions" матчатся как regulation_code
@router.get("/dept-types/list", response_model=list[str])
def list_dept_types_for_regulations(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[str]:
    """Коды типов подразделения для фильтра: регламенты, оргструктура, справочник должностей, сегменты."""
    from app.models import TemplateSegmentCode

    codes: set[str] = set()
    for row in db.scalars(
        select(PositionRegulation.dept_type_code).where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.dept_type_code.isnot(None),
            PositionRegulation.dept_type_code != "",
        )
    ).all():
        if row:
            codes.add(row)
    for row in db.scalars(
        select(TemplateOrgUnitRow.code).where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.unit_type == "department",
        )
    ).all():
        if row:
            codes.add(row)
    for row in db.scalars(
        select(TemplateSegmentCode.code).where(TemplateSegmentCode.template_code == template_code)
    ).all():
        if row:
            codes.add(row)
    for pc in db.scalars(
        select(PositionCatalog.position_code).where(PositionCatalog.template_code == template_code)
    ).all():
        dept = get_primary_dept_type_code(db, template_code, pc)
        if dept:
            codes.add(dept)
    return sorted(codes)


@router.get("/kpi-templates/list", response_model=list[dict])
def list_kpi_templates(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Список KPI-шаблонов для выбора при создании регламента."""
    rows = db.scalars(
        select(KpiTemplate).where(
            KpiTemplate.template_code == template_code,
            KpiTemplate.is_active == True,
        )
    ).all()
    out: list[dict] = []
    for r in rows:
        dept = None
        pos_name = None
        if r.position_code:
            dept = db.scalar(
                select(PositionDeptType.dept_type_code).where(
                    PositionDeptType.template_code == template_code,
                    PositionDeptType.position_code == r.position_code,
                    PositionDeptType.is_primary == True,
                ).limit(1)
            )
            pc = db.get(PositionCatalog, (template_code, r.position_code))
            if pc:
                pos_name = pc.position_name_ru
        out.append(
            {
                "kpi_code": r.kpi_code,
                "kpi_name": r.kpi_name,
                "unit": r.unit,
                "period_type": r.period_type,
                "default_target": r.default_target,
                "position_code": r.position_code,
                "primary_dept_type_code": dept,
                "position_name_ru": pos_name,
            }
        )
    return out


@router.get("/positions/list", response_model=list[dict])
def list_positions_for_regulation(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Список должностей из справочника для выбора при создании регламента."""
    rows = db.scalars(
        select(PositionCatalog)
        .where(PositionCatalog.template_code == template_code, PositionCatalog.is_active == True)
        .order_by(PositionCatalog.position_code)
    ).all()
    out: list[dict] = []
    for r in rows:
        dept = db.scalar(
            select(PositionDeptType.dept_type_code).where(
                PositionDeptType.template_code == template_code,
                PositionDeptType.position_code == r.position_code,
                PositionDeptType.is_primary == True,
            ).limit(1)
        )
        out.append(
            {
                "position_code": r.position_code,
                "position_name_ru": r.position_name_ru,
                "function_code": r.function_code,
                "primary_dept_type_code": dept,
            }
        )
    return out


@router.post("/generate-from-web", response_model=RegulationFromWebOut)
def generate_regulation_from_web(body: RegulationFromWebIn) -> RegulationFromWebOut:
    """Сгенерировать DOCX-регламент по названию должности (поиск в интернете + шаблон)."""
    from app.services.regulation_from_web import (
        analyze_template_structure,
        generate_regulation_from_web as _generate,
        resolve_template_docx,
    )

    title = body.position_title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="position_title_required")
    try:
        path, draft = _generate(title, body.comment, template_code=body.template_code)
        template_info = analyze_template_structure(resolve_template_docx())
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="regulation_template_docx_not_found") from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"regulation_generation_failed: {exc}") from exc

    return RegulationFromWebOut(
        template_code=body.template_code,
        regulation_code=draft.regulation_code,
        position_code=draft.position_code,
        regulation_name=draft.regulation_name,
        goal_summary=draft.goal_summary or None,
        ckp_short=draft.ckp_short or None,
        ckp_full=draft.ckp_full or None,
        docx_filename=path.name,
        download_url=f"/api/regulations/generated/{path.name}",
        sources=draft.sources,
        notes=draft.notes,
        template_info=template_info,
    )


@router.get("/generated/{filename}")
def download_generated_regulation(filename: str) -> FileResponse:
    """Скачать сгенерированный DOCX (только из каталога generated/)."""
    import re
    from app.services.regulation_from_web import GENERATED_DIR

    safe = Path(filename).name
    if not re.fullmatch(r"Регламент_[\w\-]+_[0-9a-f]{8}\.docx", safe):
        raise HTTPException(status_code=400, detail="invalid_filename")
    path = (GENERATED_DIR / safe).resolve()
    try:
        path.relative_to(GENERATED_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="file_not_found") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file_not_found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe,
    )


@router.get("/export/excel")
def export_regulations_excel(
    position_code: str | None = Query(None),
    dept_type_code: str | None = Query(None),
    status: str | None = Query(None),
    is_current: bool | None = Query(None),
    search: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
) -> Response:
    filters: list = []
    if position_code:
        filters.append(PositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(PositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(PositionRegulation.status == status)
    if is_current is not None:
        filters.append(PositionRegulation.is_current == is_current)
    if search and (s := search.strip()):
        filters.append(_ilike_any_regulation_column(s))
    q = select(PositionRegulation)
    for f in filters:
        q = q.where(f)
    rows = db.scalars(
        q.order_by(
            PositionRegulation.position_code,
            PositionRegulation.dept_type_code,
            PositionRegulation.version_no,
        ).limit(5000)
    ).all()
    headers = [
        "regulation_code",
        "position_code",
        "dept_type_code",
        "regulation_name",
        "goal_summary",
        "ckp_short",
        "ckp_full",
        "google_doc_url",
        "instructions_folder_url",
        "version_no",
        "status",
        "effective_from",
        "effective_to",
        "is_current",
        "owner_unit_code",
        "notes",
        "id",
        "created_at",
        "updated_at",
    ]
    data = []
    for r in rows:
        o = PositionRegulationOut.model_validate(r)
        data.append(
            [
                o.regulation_code,
                o.position_code,
                o.dept_type_code,
                o.regulation_name,
                o.goal_summary,
                o.ckp_short,
                o.ckp_full,
                o.google_doc_url,
                o.instructions_folder_url,
                o.version_no,
                o.status,
                o.effective_from,
                o.effective_to,
                o.is_current,
                o.owner_unit_code,
                o.notes,
                o.id,
                o.created_at,
                o.updated_at,
            ]
        )
    return xlsx_file_response(
        download_name="regulations_global.xlsx",
        sheet_title="regulations",
        headers=headers,
        rows=data,
    )


@router.get("/{regulation_code}", response_model=PositionRegulationDetailOut)
def get_regulation(regulation_code: str, db: Session = Depends(get_db)) -> PositionRegulationDetailOut:
    q = select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code)
    obj = db.scalar(q)
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    kpis = db.scalars(select(RegulationKpi).where(RegulationKpi.regulation_code == regulation_code)).all()
    instructions = db.scalars(
        select(RegulationInstruction)
        .where(RegulationInstruction.regulation_code == regulation_code)
        .order_by(RegulationInstruction.sort_order)
    ).all()
    base = _regulation_out(db, obj)
    return PositionRegulationDetailOut(
        **base.model_dump(),
        kpis=[RegulationKpiOut.model_validate(k) for k in kpis],
        instructions=[RegulationInstructionOut.model_validate(i) for i in instructions],
    )


@router.post("", response_model=PositionRegulationOut, status_code=201)
def create_regulation(body: PositionRegulationCreate, db: Session = Depends(get_db)) -> PositionRegulationOut:
    existing = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == body.template_code,
            PositionRegulation.regulation_code == body.regulation_code,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "regulation_code_already_exists",
                "message": (
                    f"Код регламента «{body.regulation_code}» уже занят в шаблоне "
                    f"«{body.template_code}» (карточка «{existing.regulation_name}»). "
                    "Задайте другой код или откройте существующую запись."
                ),
            },
        )
    slot = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == body.template_code,
            PositionRegulation.position_code == body.position_code,
            PositionRegulation.dept_type_code == body.dept_type_code,
            PositionRegulation.version_no == body.version_no,
        )
    )
    if slot:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "regulation_slot_already_exists",
                "message": (
                    f"Для должности «{body.position_code}», типа подразделения «{body.dept_type_code}» "
                    f"и версии «{body.version_no}» регламент уже есть "
                    f"(код «{slot.regulation_code}», «{slot.regulation_name}»). "
                    "Измените версию или откройте существующую карточку."
                ),
            },
        )
    _ensure_dept_type_code(db, body.template_code, body.dept_type_code)
    obj = PositionRegulation(
        id=body.id or _id("regulation", body.regulation_code),
        template_code=body.template_code,
        regulation_code=body.regulation_code,
        position_code=body.position_code,
        dept_type_code=body.dept_type_code.strip(),
        regulation_name=body.regulation_name,
        goal_summary=body.goal_summary,
        ckp_short=body.ckp_short,
        ckp_full=body.ckp_full,
        google_doc_url=body.google_doc_url,
        instructions_folder_url=body.instructions_folder_url,
        version_no=body.version_no,
        status=body.status,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_current=body.is_current,
        owner_unit_code=body.owner_unit_code,
        notes=body.notes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _regulation_out(db, obj)


def _ensure_dept_type_code(db: Session, template_code: str, dept_type_code: str) -> None:
    code = dept_type_code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="invalid_dept_type_code")
    if not is_template_dept_or_segment_code(db, template_code, code):
        raise HTTPException(status_code=400, detail="dept_type_not_found")


@router.post("/sync-dept-from-catalog")
def sync_regulation_dept_from_catalog(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Подтянуть dept_type_code из справочника типовых должностей во все регламенты шаблона."""
    rows = db.scalars(
        select(PositionRegulation).where(PositionRegulation.template_code == template_code)
    ).all()
    updated = 0
    skipped = 0
    for row in rows:
        catalog_dept = get_primary_dept_type_code(db, template_code, row.position_code)
        if not catalog_dept:
            skipped += 1
            continue
        if row.dept_type_code == catalog_dept:
            continue
        _ensure_dept_type_code(db, template_code, catalog_dept)
        row.dept_type_code = catalog_dept
        updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped, "total": len(rows)}


@router.post("/{regulation_code}/clone", response_model=RegulationCloneOut, status_code=201)
def clone_regulation_row(
    regulation_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> RegulationCloneOut:
    obj = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.regulation_code == regulation_code,
        )
    )
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    result = clone_regulation(db, obj)
    db.commit()
    db.refresh(result.row)
    return RegulationCloneOut(
        row=PositionRegulationOut.model_validate(result.row),
        kpis_created=result.kpis_created,
        instructions_created=result.instructions_created,
    )


@router.patch("/{regulation_code}", response_model=PositionRegulationOut)
def patch_regulation(
    regulation_code: str, body: PositionRegulationPatch, db: Session = Depends(get_db)
) -> PositionRegulationOut:
    obj = db.scalar(select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code))
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    data = body.model_dump(exclude_unset=True)
    new_reg_code = data.pop("regulation_code", None)
    new_pos = data.pop("position_code", None)
    new_ver = data.pop("version_no", None)
    dept = data.pop("dept_type_code", None)

    pos = ensure_regulation_position_code(db, obj.template_code, new_pos) if new_pos is not None else obj.position_code
    ver = new_ver.strip() if new_ver is not None else obj.version_no
    dept_val = dept.strip() if dept is not None else obj.dept_type_code
    if dept is not None:
        _ensure_dept_type_code(db, obj.template_code, dept_val)

    ensure_regulation_slot_available(
        db, obj.template_code, pos, dept_val, ver, exclude_regulation_code=obj.regulation_code
    )

    if new_reg_code is not None:
        rename_regulation_code(db, obj, new_reg_code)
    if new_pos is not None:
        obj.position_code = pos
    if dept is not None:
        obj.dept_type_code = dept_val
    if new_ver is not None:
        obj.version_no = ver
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _regulation_out(db, obj)


@router.delete("/{regulation_code}", status_code=204)
def delete_regulation(regulation_code: str, db: Session = Depends(get_db)) -> Response:
    obj = db.scalar(select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code))
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    for rk in db.scalars(select(RegulationKpi).where(RegulationKpi.regulation_code == regulation_code)).all():
        db.delete(rk)
    for ri in db.scalars(select(RegulationInstruction).where(RegulationInstruction.regulation_code == regulation_code)).all():
        db.delete(ri)
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
