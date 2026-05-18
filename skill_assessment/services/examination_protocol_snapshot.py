# route: (examination) | file: skill_assessment/services/examination_protocol_snapshot.py
"""Canonical immutable JSON snapshot for examination protocol archives."""

from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from skill_assessment.infrastructure.db_models import (
    CompetencyCatalogVersionRow,
    CompetencyMatrixRow,
    ExaminationAnswerRow,
    ExaminationSessionRow,
    KpiCatalogVersionRow,
    KpiMatrixRow,
)
from skill_assessment.integration.hr_core import (
    get_employee,
    get_examination_instructions_folder_url,
    get_examination_kpi_labels,
    get_examination_regulation_reference_text,
)
from skill_assessment.schemas.examination_api import ExaminationProtocolOut

SNAPSHOT_SCHEMA_VERSION = "examination_protocol_snapshot.v1"
PROTOCOL_VERSION = "examination_protocol.v1"
GENERATOR_VERSION = "protocol-engine-1.0.0"
DEFAULT_PROMPT_VERSION = "heuristic_regulation_eval_v1"
DEFAULT_MODEL = "heuristic"


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {k: _json_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _employee_snapshot(db: Session, row: ExaminationSessionRow) -> dict[str, Any]:
    emp = get_employee(db, row.client_id, row.employee_id)
    if emp is None:
        return {
            "id": row.employee_id,
            "client_id": row.client_id,
            "display_name": None,
            "email": None,
            "last_name": None,
            "first_name": None,
            "middle_name": None,
            "position_label": None,
            "position_code": None,
            "department_code": None,
            "org_unit_id": None,
            "manager_employee_id": None,
        }
    return _json_value(emp)


def _matching_catalog_rows(db: Session, emp: dict[str, Any], client_id: str) -> dict[str, Any]:
    position_code = (emp.get("position_code") or "").strip()
    department_code = (emp.get("department_code") or "").strip()
    out: dict[str, Any] = {
        "position_code": position_code or None,
        "department_code": department_code or None,
        "competency_rows": [],
        "kpi_rows": [],
    }
    if not position_code or not department_code:
        return out

    comp_stmt = (
        select(CompetencyMatrixRow)
        .join(CompetencyCatalogVersionRow, CompetencyMatrixRow.version_id == CompetencyCatalogVersionRow.id)
        .where(CompetencyCatalogVersionRow.status == "active")
        .where(CompetencyMatrixRow.position_code == position_code)
        .where(CompetencyMatrixRow.department_code == department_code)
        .where(
            (CompetencyCatalogVersionRow.client_id == client_id)
            | (CompetencyCatalogVersionRow.client_id.is_(None))
        )
        .order_by(CompetencyCatalogVersionRow.client_id.desc(), CompetencyMatrixRow.skill_rank.asc())
    )
    for item in db.scalars(comp_stmt).all():
        version = item.catalog_version
        skill = item.skill_definition
        out["competency_rows"].append(
            {
                "row_id": item.id,
                "version_id": version.id,
                "version_code": version.version_code,
                "catalog_client_id": version.client_id,
                "catalog_status": version.status,
                "source_regulation_code": version.source_regulation_code,
                "source_regulation_version_no": version.source_regulation_version_no,
                "published_at": _json_value(version.published_at),
                "skill_rank": item.skill_rank,
                "skill_code": skill.skill_code if skill else None,
                "skill_title_ru": skill.title_ru if skill else None,
                "is_active": item.is_active,
            }
        )

    kpi_stmt = (
        select(KpiMatrixRow)
        .join(KpiCatalogVersionRow, KpiMatrixRow.version_id == KpiCatalogVersionRow.id)
        .where(KpiCatalogVersionRow.status == "active")
        .where(KpiMatrixRow.position_code == position_code)
        .where(KpiMatrixRow.department_code == department_code)
        .where((KpiCatalogVersionRow.client_id == client_id) | (KpiCatalogVersionRow.client_id.is_(None)))
        .order_by(KpiCatalogVersionRow.client_id.desc(), KpiMatrixRow.kpi_rank.asc())
    )
    for item in db.scalars(kpi_stmt).all():
        version = item.catalog_version
        kpi = item.kpi_definition
        out["kpi_rows"].append(
            {
                "row_id": item.id,
                "version_id": version.id,
                "version_code": version.version_code,
                "catalog_client_id": version.client_id,
                "catalog_status": version.status,
                "source_regulation_code": version.source_regulation_code,
                "source_regulation_version_no": version.source_regulation_version_no,
                "published_at": _json_value(version.published_at),
                "kpi_rank": item.kpi_rank,
                "kpi_code": kpi.kpi_code if kpi else None,
                "kpi_title_ru": kpi.title_ru if kpi else None,
                "unit": kpi.unit if kpi else None,
                "period_type": kpi.period_type if kpi else None,
                "default_target": kpi.default_target if kpi else None,
                "is_active": item.is_active,
            }
        )
    return out


def _client_regulation_rows(db: Session, client_id: str, employee_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from app.models import ClientPositionRegulation
    except Exception:
        return []
    position_code = (employee_snapshot.get("position_code") or "").strip()
    if not position_code:
        return []
    rows = db.scalars(
        select(ClientPositionRegulation)
        .where(ClientPositionRegulation.client_id == client_id)
        .where(ClientPositionRegulation.position_code == position_code)
        .order_by(ClientPositionRegulation.regulation_code)
    ).all()
    out: list[dict[str, Any]] = []
    for reg in rows:
        out.append(
            {
                "id": getattr(reg, "id", None),
                "regulation_code": getattr(reg, "regulation_code", None),
                "global_regulation_code": getattr(reg, "global_regulation_code", None),
                "regulation_name": getattr(reg, "regulation_name", None),
                "version_no": getattr(reg, "version_no", None),
                "position_code": getattr(reg, "position_code", None),
                "dept_type_code": getattr(reg, "dept_type_code", None),
                "status": getattr(reg, "status", None),
                "is_current": getattr(reg, "is_current", None),
                "goal_summary": getattr(reg, "goal_summary", None),
                "ckp_short": getattr(reg, "ckp_short", None),
                "ckp_full": getattr(reg, "ckp_full", None),
                "instructions_folder_url": getattr(reg, "instructions_folder_url", None),
                "updated_at": _json_value(getattr(reg, "updated_at", None)),
            }
        )
    return out


def build_examination_protocol_snapshot(db: Session, session_id: str) -> dict[str, Any]:
    from skill_assessment.services import examination_service as ex

    row = db.get(ExaminationSessionRow, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="examination_session_not_found")

    proto = ex.build_protocol(db, session_id)
    answers = {
        a.question_id: a
        for a in db.scalars(
            select(ExaminationAnswerRow).where(ExaminationAnswerRow.session_id == session_id)
        ).all()
    }
    employee = _employee_snapshot(db, row)
    regulation_reference_text = get_examination_regulation_reference_text(db, row.client_id, row.employee_id)
    kpi_labels = get_examination_kpi_labels(db, row.client_id, row.employee_id)
    instructions_folder_url = get_examination_instructions_folder_url(db, row.client_id, row.employee_id)

    question_items: list[dict[str, Any]] = []
    for item in proto.items:
        answer = answers.get(item.question_id)
        question_items.append(
            {
                "question_id": item.question_id,
                "seq": item.seq,
                "question_text": item.question_text,
                "answer": {
                    "transcript_text": item.transcript_text,
                    "created_at": _json_value(answer.created_at if answer else None),
                },
                "scoring": {
                    "score_4": item.score_4,
                    "score_percent": item.score_percent,
                    "scoring_engine": "semantic_or_heuristic_score_4",
                    "scoring_scale": "1-4; percent 50-100",
                },
            }
        )

    generator = {
        "generator_version": os.getenv("SKILL_ASSESSMENT_PROTOCOL_GENERATOR_VERSION", GENERATOR_VERSION),
        "prompt_version": os.getenv("SKILL_ASSESSMENT_PROTOCOL_PROMPT_VERSION", DEFAULT_PROMPT_VERSION),
        "model": os.getenv("SKILL_ASSESSMENT_PROTOCOL_EVALUATOR_MODEL", DEFAULT_MODEL),
        "stt_provider": os.getenv("SKILL_ASSESSMENT_STT_PROVIDER") or None,
    }
    now = datetime.now(timezone.utc)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "immutable": True,
        "created_at": now.isoformat(),
        "session": {
            "id": row.id,
            "client_id": row.client_id,
            "employee_id": row.employee_id,
            "scenario_id": row.scenario_id,
            "question_scenario_id": row.question_scenario_id,
            "status": row.status,
            "phase": row.phase,
            "consent_status": row.consent_status,
            "started_at": _json_value(row.started_at),
            "completed_at": _json_value(row.completed_at),
            "created_at": _json_value(row.created_at),
            "updated_at": _json_value(row.updated_at),
        },
        "employee_snapshot": employee,
        "regulation_snapshot": {
            "reference_text": regulation_reference_text,
            "instructions_folder_url": instructions_folder_url,
            "client_regulations": _client_regulation_rows(db, row.client_id, employee),
        },
        "kpi_snapshot": {
            "labels": list(kpi_labels or []),
            **_matching_catalog_rows(db, employee, row.client_id),
        },
        "questions": question_items,
        "scoring": {
            "final_score": {
                "average_score_4": proto.average_score_4,
                "average_score_percent": proto.average_score_percent,
            },
            "items": [q["scoring"] | {"question_id": q["question_id"], "seq": q["seq"]} for q in question_items],
            "note": proto.scoring_note,
        },
        "ai_evaluation": {
            "provider": generator["model"],
            "model": generator["model"],
            "prompt_version": generator["prompt_version"],
            "raw_output_storage_key": None,
            "parsed_output": None,
        },
        "generator": generator,
        "timestamps": {
            "started_at": _json_value(row.started_at),
            "completed_at": _json_value(row.completed_at),
            "evaluated_at": _json_value(proto.evaluated_at),
            "archived_at": now.isoformat(),
        },
        "related_assessment": {
            "session_id": proto.related_assessment_session_id,
            "phase": proto.related_assessment_phase,
            "status": proto.related_assessment_status,
            "report_url": proto.related_report_url,
            "report_path": proto.related_report_path,
            "part2_summary": proto.part2_summary,
        },
        "protocol": proto.model_dump(mode="json"),
    }


def protocol_from_snapshot(snapshot: dict[str, Any]) -> ExaminationProtocolOut:
    return ExaminationProtocolOut.model_validate(snapshot["protocol"])
