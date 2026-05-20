# route: /api/psychological-testing | file: app/routers/psychological_testing.py
"""Psychological testing: sessions (JSON), assignments, programs (Phase 4a)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Employee
from app.schemas import ListEnvelope
from app.services import psych_test_assignments as assign_svc
from psychological_testing.integration.session_repository import (
    get_session_document,
    list_session_summaries,
    module_status,
)

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


class PsychAssignmentCreateIn(BaseModel):
    client_id: str
    employee_id: str
    program_id: str = "standard_hr_v1"
    due_at: datetime | None = None
    notify: bool = False


class PsychAssignmentPatchIn(BaseModel):
    due_at: datetime | None = None


class PsychAssignmentOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    client_id: str
    employee_id: str
    employee_display_name: str | None = None
    employee_telegram_id: str | None = None
    program_id: str = "standard_hr_v1"
    program_title_ru: str | None = None
    status: str
    completed_tests: list[str] = Field(default_factory=list)
    due_at: str | None = None
    due_date: str | None = None
    notified_at: str | None = None
    total_steps: int | None = None
    completed_steps: int | None = None
    is_complete: bool | None = None
    allowed_test_ids: list[str] = Field(default_factory=list)
    next_test_id: str | None = None


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
    if code.startswith("telegram_send_failed") or code == "telegram_send_failed":
        status = 502
    return HTTPException(status_code=status, detail=code)


@router.get("/status", response_model=PsychModuleStatusOut)
def get_psych_testing_status() -> PsychModuleStatusOut:
    return PsychModuleStatusOut.model_validate(module_status())


@router.get("/programs")
def list_psych_programs() -> dict:
    return {"items": assign_svc.programs_payload()}


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
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PsychAssignmentOut]:
    _assert_client(db, client_id)
    items, total = assign_svc.list_assignments(db, client_id=client_id, limit=limit, offset=offset)
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
    try:
        row = assign_svc.create_assignment(
            db,
            client_id=body.client_id,
            employee_id=body.employee_id,
            program_id=body.program_id,
            due_at=body.due_at,
        )
    except ValueError as e:
        raise _value_error_to_http(e) from e
    if body.notify:
        try:
            data = assign_svc.notify_assignment(db, row.id)
            return PsychAssignmentOut.model_validate(data)
        except ValueError as e:
            raise _value_error_to_http(e) from e
    emp = db.get(Employee, row.employee_id)
    name = None
    if emp:
        name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
    return PsychAssignmentOut.model_validate(assign_svc.assignment_to_dict(row, employee_name=name))


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
