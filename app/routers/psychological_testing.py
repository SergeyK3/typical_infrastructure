# route: /api/psychological-testing | file: app/routers/psychological_testing.py
"""Psychological testing: sessions (JSON), HR assignments (один test_id)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Employee
from app.schemas import ListEnvelope
from app.services import psych_test_assignments as assign_svc
from app.services.psych_rbac import assert_can_export_pdf
from psychological_testing.integration.manifest_store import resolve_pdf_ref
from psychological_testing.integration.report_storage import export_artifact_metadata
from psychological_testing.integration.pdf_export_api import (
    build_export_manifest,
    export_employee_pdf,
    export_preview,
    load_cached_pdf,
    sections_catalog,
)
from psychological_testing.integration.session_repository import (
    get_session_document,
    list_session_summaries,
    module_status,
)
from psychological_testing.shared_engine.report_contract import DEFAULT_TEMPLATE_ID

router = APIRouter(prefix="/psychological-testing", tags=["psychological-testing"])


class PsychSessionSummaryOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    client_id: str | None = None
    employee_id: str | None = None
    employee_display_name: str | None = None
    test_id: str | None = None
    test_version: str | None = None
    delivery_mode: str | None = None
    status: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    typology_code: str | None = None
    report_preview: str = ""


class PsychTestInfoOut(BaseModel):
    test_id: str
    display_name: str | None = None


class PsychModuleStatusOut(BaseModel):
    persist_json_enabled: bool
    sessions_dir: str
    session_count: int
    available_tests: list[PsychTestInfoOut]
    telegram_commands: list[str] = Field(default_factory=list)
    pdf_cache_mode: str = "off"
    pdf_renderer_version: str = ""
    gdrive_enabled: bool = False
    gdrive_configured: bool = False
    gdrive_upload_sessions: bool = False
    gdrive_upload_manifest: bool = False
    storage_label: str = ""


class PsychAssignmentCreateIn(BaseModel):
    client_id: str
    employee_id: str
    test_id: str = Field(description="Код теста из /status → available_tests")
    due_at: datetime | None = None
    notify: bool = False
    replace_active: bool = Field(
        default=False,
        description="Заменить текущее активное назначение другим тестом (иначе — ошибка active_assignment_exists)",
    )


class PsychAssignmentPatchIn(BaseModel):
    due_at: datetime | None = None


class PsychSectionOverrideIn(BaseModel):
    section_id: str
    enabled: bool = True
    charts: list[str] | None = None
    requires_ai: bool | None = None


class PsychExportPdfIn(BaseModel):
    client_id: str
    template_id: str = DEFAULT_TEMPLATE_ID
    sections: list[PsychSectionOverrideIn] | None = None
    session_refs: list[dict[str, str]] | None = None
    regenerate_ai: bool = False
    force_regenerate: bool = Field(
        default=False,
        description="Игнорировать PDF-кэш и пересобрать отчёт (после обновления шаблона/графиков)",
    )
    strict: bool = False
    response_mode: str = Field(
        default="stream",
        description="stream — PDF bytes; json — metadata + pdf_ref",
    )
    account_id: str | None = Field(
        default=None,
        description="Для RBAC hr.psych_testing.export при PSYCH_TESTING_RBAC_EXPORT=1",
    )


class PsychExportPdfOut(BaseModel):
    manifest_id: str
    pdf_ref: str | None = None
    pdf_open_url: str | None = None
    storage_kind: str | None = None
    size_bytes: int
    cache_hit: bool = False
    manifest_path: str | None = None
    manifest_drive_ref: str | None = None
    pdf_local_ref: str | None = None
    download_filename: str | None = None
    pdf_renderer_version: str | None = None


class PsychAssignmentOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    client_id: str
    employee_id: str
    employee_display_name: str | None = None
    employee_telegram_id: str | None = None
    test_id: str = ""
    test_label_ru: str = ""
    status: str
    due_at: str | None = None
    due_date: str | None = None
    notified_at: str | None = None
    completed_at: str | None = None
    session_id: str | None = None
    is_complete: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _assert_client(db: Session, client_id: str) -> None:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")


def _value_error_to_http(exc: ValueError) -> HTTPException:
    code = str(exc)
    status = 400
    if code in ("assignment_not_found", "employee_not_found"):
        status = 404
    if code == "telegram_bot_token_missing":
        status = 503
        code = "telegram_bot_token_missing: задайте TELEGRAM_BOT_TOKEN в .env"
    if code in ("telegram_chat_not_found", "employee_no_telegram"):
        status = 400
    if code.startswith("unknown_test_id"):
        status = 400
    if code.startswith("telegram_send_failed") or code == "telegram_send_failed":
        status = 502
    if code == "assignment_terminal":
        code = (
            "Назначение завершено или заменено. Создайте новое назначение "
            "и нажмите «Уведомить» у активной строки."
        )
    if code == "assignment_no_active":
        code = (
            "Нет активного назначения для уведомления. "
            "Создайте новое назначение теста для сотрудника."
        )
    if code == "active_assignment_exists":
        code = (
            "У сотрудника уже есть активное назначение другого теста. "
            "Дождитесь завершения, отмените его в HR или создайте с replace_active=true."
        )
    return HTTPException(status_code=status, detail=code)


@router.get("/status", response_model=PsychModuleStatusOut)
def get_psych_testing_status() -> PsychModuleStatusOut:
    return PsychModuleStatusOut.model_validate(module_status())


@router.get("/sessions", response_model=ListEnvelope[PsychSessionSummaryOut])
def list_psych_sessions(
    client_id: str | None = Query(None, description="Фильтр по организации"),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PsychSessionSummaryOut]:
    if client_id:
        _assert_client(db, client_id)
    items, total = list_session_summaries(client_id=client_id, limit=limit, offset=offset)
    return ListEnvelope[PsychSessionSummaryOut](
        items=[PsychSessionSummaryOut.model_validate(x) for x in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}")
def get_psych_session(session_id: str) -> dict:
    doc = get_session_document(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="psych_session_not_found")
    return doc


@router.get("/assignments", response_model=ListEnvelope[PsychAssignmentOut])
def list_psych_assignments(
    client_id: str = Query(..., description="Организация"),
    employee_id: str | None = Query(None, description="Фильтр по сотруднику (история назначений)"),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PsychAssignmentOut]:
    _assert_client(db, client_id)
    items, total = assign_svc.list_assignments(
        db,
        client_id=client_id,
        employee_id=employee_id,
        limit=limit,
        offset=offset,
    )
    return ListEnvelope[PsychAssignmentOut](
        items=[PsychAssignmentOut.model_validate(x) for x in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/assignments", response_model=PsychAssignmentOut)
def create_psych_assignment(
    body: PsychAssignmentCreateIn,
    db: Session = Depends(get_db),
) -> PsychAssignmentOut:
    _assert_client(db, body.client_id)
    existing_before = assign_svc.get_active_assignment(
        db, client_id=body.client_id, employee_id=body.employee_id
    )
    try:
        row = assign_svc.create_assignment(
            db,
            client_id=body.client_id,
            employee_id=body.employee_id,
            test_id=body.test_id,
            due_at=body.due_at,
            replace_active=body.replace_active,
        )
    except ValueError as e:
        raise _value_error_to_http(e) from e
    created_new = existing_before is None or row.id != existing_before.id
    if body.notify:
        try:
            data = assign_svc.notify_assignment(db, row.id)
            return PsychAssignmentOut.model_validate(data)
        except ValueError as e:
            if created_new:
                db.delete(row)
                db.commit()
            raise _value_error_to_http(e) from e
    emp = db.get(Employee, row.employee_id)
    name = None
    if emp:
        name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
    return PsychAssignmentOut.model_validate(
        assign_svc.assignment_to_dict(row, employee_name=name, db=db)
    )


@router.patch("/assignments/{assignment_id}", response_model=PsychAssignmentOut)
def patch_psych_assignment(
    assignment_id: str,
    body: PsychAssignmentPatchIn,
    db: Session = Depends(get_db),
) -> PsychAssignmentOut:
    try:
        data = assign_svc.update_assignment_due_at(
            db, assignment_id, due_at=body.due_at
        )
    except ValueError as e:
        raise _value_error_to_http(e) from e
    return PsychAssignmentOut.model_validate(data)


def _employee_display_name(db: Session, employee_id: str) -> str | None:
    emp = db.get(Employee, employee_id)
    if not emp:
        return None
    return " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))


def _assert_employee_client(db: Session, client_id: str, employee_id: str) -> Employee:
    emp = db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="employee_not_found")
    if str(emp.client_id) != str(client_id):
        raise HTTPException(status_code=400, detail="employee_client_mismatch")
    return emp


def _sections_from_body(
    overrides: list[PsychSectionOverrideIn] | None,
) -> list[dict[str, Any]] | None:
    if overrides is None:
        return None
    out: list[dict[str, Any]] = []
    for item in overrides:
        entry: dict[str, Any] = {
            "section_id": item.section_id,
            "enabled": item.enabled,
        }
        if item.charts is not None:
            entry["charts"] = item.charts
        if item.requires_ai is not None:
            entry["requires_ai"] = item.requires_ai
        out.append(entry)
    return out


@router.get("/report-templates")
def get_report_templates() -> dict:
    templates, sections = sections_catalog()
    return {"templates": templates, "sections": sections}


@router.get("/employees/{employee_id}/export-preview")
def get_export_preview(
    employee_id: str,
    client_id: str = Query(...),
    template_id: str = Query(DEFAULT_TEMPLATE_ID),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    _assert_client(db, client_id)
    _assert_employee_client(db, client_id, employee_id)
    assert_can_export_pdf(
        db, account_id=account_id, client_id=client_id, employee_id=employee_id
    )
    return export_preview(
        client_id=client_id,
        employee_id=employee_id,
        template_id=template_id,
    )


from psychological_testing.integration.filename_translit import ascii_slug_from_name


def _pdf_download_filename(employee_id: str, display_name: str | None) -> str:
    """ASCII filename safe for HTTP headers and Windows paths."""
    raw = (display_name or "").strip()
    if raw:
        base = ascii_slug_from_name(raw, max_len=60, fallback="")
        if not base:
            base = f"psych_report_{employee_id[:8]}"
    else:
        base = f"psych_report_{employee_id[:8]}"
    return base if base.lower().endswith(".pdf") else f"{base}.pdf"


def _pdf_content_disposition(employee_id: str, display_name: str | None) -> tuple[str, str]:
    filename = _pdf_download_filename(employee_id, display_name)
    header = f'attachment; filename="{filename}"'
    return filename, header


def _latin1_http_header(value: str) -> str:
    try:
        value.encode("latin-1")
        return value
    except UnicodeEncodeError:
        return quote(value, safe="/:/?&=#")


@router.post("/employees/{employee_id}/export-pdf")
def post_export_pdf(
    employee_id: str,
    body: PsychExportPdfIn,
    db: Session = Depends(get_db),
):
    _assert_client(db, body.client_id)
    _assert_employee_client(db, body.client_id, employee_id)
    assert_can_export_pdf(
        db,
        account_id=body.account_id,
        client_id=body.client_id,
        employee_id=employee_id,
    )

    sections = _sections_from_body(body.sections)
    client = db.get(Client, body.client_id)
    manifest = build_export_manifest(
        client_id=body.client_id,
        employee_id=employee_id,
        template_id=body.template_id,
        created_by=body.account_id,
        session_refs=body.session_refs,
        sections=sections,
        client_name=(client.name or "").strip() if client else None,
    )
    if body.strict:
        from psychological_testing.shared_engine.report_contract import (
            load_section_registry,
            validate_manifest,
        )

        reg = load_section_registry()
        result = validate_manifest(manifest, registry=reg, strict=True)
        if not result.ok:
            raise HTTPException(status_code=400, detail=list(result.errors))

    display_name = _employee_display_name(db, employee_id)
    try:
        result = export_employee_pdf(
            manifest,
            employee_display_name=display_name,
            regenerate_ai=body.regenerate_ai,
            force_regenerate=body.force_regenerate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf_bytes = result["pdf_bytes"]
    pdf_ref = result.get("pdf_ref")
    artifact = export_artifact_metadata(pdf_ref, client_id=body.client_id)
    from psychological_testing.shared_engine.pdf_render_version import PDF_RENDERER_VERSION

    mode = (body.response_mode or "stream").strip().lower()
    download_filename = _pdf_download_filename(employee_id, display_name)
    if mode == "json":
        return PsychExportPdfOut(
            manifest_id=str(result["manifest"].get("manifest_id") or ""),
            pdf_ref=artifact["pdf_ref"],
            pdf_open_url=artifact["pdf_open_url"],
            storage_kind=artifact["storage_kind"],
            size_bytes=len(pdf_bytes),
            cache_hit=bool(result.get("cache_hit")),
            manifest_path=result.get("manifest_path"),
            manifest_drive_ref=result.get("manifest_drive_ref"),
            pdf_local_ref=result.get("pdf_local_ref"),
            download_filename=download_filename,
            pdf_renderer_version=PDF_RENDERER_VERSION,
        )

    filename, disposition = _pdf_content_disposition(employee_id, display_name)
    headers: dict[str, str] = {
        "Content-Disposition": disposition,
        "X-Psych-Pdf-Renderer-Version": PDF_RENDERER_VERSION,
    }
    if pdf_ref:
        headers["X-Psych-Pdf-Ref"] = _latin1_http_header(str(pdf_ref))
    open_url = artifact.get("pdf_open_url")
    if open_url:
        headers["X-Psych-Pdf-Open-Url"] = _latin1_http_header(str(open_url))
    if artifact.get("storage_kind"):
        headers["X-Psych-Storage-Kind"] = str(artifact["storage_kind"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


@router.get("/export-pdf/file")
def get_export_pdf_file(
    pdf_ref: str = Query(..., description="Относительный pdf_ref из export-pdf json"),
    client_id: str = Query(...),
    account_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    _assert_client(db, client_id)
    assert_can_export_pdf(db, account_id=account_id, client_id=client_id)
    data = load_cached_pdf(pdf_ref)
    if data is None:
        path = resolve_pdf_ref(pdf_ref)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="pdf_not_found")
        data = path.read_bytes()
    return Response(content=data, media_type="application/pdf")


@router.post("/assignments/{assignment_id}/notify", response_model=PsychAssignmentOut)
def notify_psych_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
) -> PsychAssignmentOut:
    try:
        data = assign_svc.notify_assignment(db, assignment_id)
    except assign_svc.NotifyTelegramError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": e.code,
                "message": e.message,
                "stored_telegram_id": e.stored_telegram_id,
                "session_telegram_chat_id": e.session_telegram_chat_id,
            },
        ) from e
    except ValueError as e:
        raise _value_error_to_http(e) from e
    return PsychAssignmentOut.model_validate(data)

