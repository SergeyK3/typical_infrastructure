# route: (examination) | file: skill_assessment/services/examination_protocol_archive.py
"""Archive registry and artifact orchestration for examination protocols."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from skill_assessment.infrastructure.db_models import (
    ExaminationProtocolArchiveRow,
    ExaminationSessionRow,
)
from skill_assessment.schemas.examination_api import ExaminationProtocolOut
from skill_assessment.services import protocol_storage
from skill_assessment.services.examination_protocol_snapshot import (
    PROTOCOL_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    build_examination_protocol_snapshot,
    protocol_from_snapshot,
)

SNAPSHOT_MIME_TYPE = "application/json"
HTML_MIME_TYPE = "text/html; charset=utf-8"


def _storage_prefix(client_id: str, session_id: str) -> str:
    safe_client = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in client_id)
    safe_session = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in session_id)
    return f"protocol_archive/examination/{safe_client}/{safe_session}"


def get_archive_by_session(db: Session, session_id: str) -> ExaminationProtocolArchiveRow | None:
    return db.scalar(
        select(ExaminationProtocolArchiveRow).where(ExaminationProtocolArchiveRow.session_id == session_id)
    )


def get_archive(db: Session, archive_id: str) -> ExaminationProtocolArchiveRow:
    row = db.get(ExaminationProtocolArchiveRow, archive_id)
    if row is None:
        raise HTTPException(status_code=404, detail="protocol_archive_not_found")
    return row


def snapshot_bytes(snapshot: dict) -> bytes:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_archive_snapshot(row: ExaminationProtocolArchiveRow) -> dict:
    data = protocol_storage.read_artifact(row.snapshot_storage_key)
    return json.loads(data.decode("utf-8"))


def read_archive_html(row: ExaminationProtocolArchiveRow) -> str:
    return protocol_storage.read_artifact(row.html_storage_key).decode("utf-8")


def protocol_out_from_archive(row: ExaminationProtocolArchiveRow) -> ExaminationProtocolOut:
    return protocol_from_snapshot(read_archive_snapshot(row))


def render_protocol_html_from_snapshot(snapshot: dict) -> str:
    from skill_assessment.services import examination_service as ex

    return ex.render_examination_protocol_html(protocol_from_snapshot(snapshot))


def ensure_examination_protocol_archive(db: Session, session_id: str) -> ExaminationProtocolArchiveRow:
    existing = get_archive_by_session(db, session_id)
    if existing is not None:
        return existing

    session = db.get(ExaminationSessionRow, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="examination_session_not_found")
    if session.status != "completed" or session.phase != "completed":
        raise HTTPException(status_code=400, detail="protocol_archive_requires_completed_session")

    snapshot = build_examination_protocol_snapshot(db, session_id)
    html = render_protocol_html_from_snapshot(snapshot)
    prefix = _storage_prefix(session.client_id, session.id)
    snapshot_artifact = protocol_storage.put_immutable_artifact(
        f"{prefix}/snapshot.json",
        snapshot_bytes(snapshot),
        mime_type=SNAPSHOT_MIME_TYPE,
    )
    html_artifact = protocol_storage.put_immutable_artifact(
        f"{prefix}/protocol.html",
        html.encode("utf-8"),
        mime_type=HTML_MIME_TYPE,
    )

    generator = snapshot.get("generator") if isinstance(snapshot.get("generator"), dict) else {}
    row = ExaminationProtocolArchiveRow(
        id=str(uuid.uuid4()),
        session_id=session.id,
        client_id=session.client_id,
        employee_id=session.employee_id,
        status="ready",
        immutable=True,
        schema_version=str(snapshot.get("schema_version") or SNAPSHOT_SCHEMA_VERSION),
        protocol_version=str(snapshot.get("protocol_version") or PROTOCOL_VERSION),
        generator_version=generator.get("generator_version"),
        prompt_version=generator.get("prompt_version"),
        model=generator.get("model"),
        snapshot_storage_key=snapshot_artifact.storage_key,
        snapshot_sha256=snapshot_artifact.sha256,
        snapshot_size_bytes=snapshot_artifact.size_bytes,
        snapshot_mime_type=snapshot_artifact.mime_type,
        html_storage_key=html_artifact.storage_key,
        html_sha256=html_artifact.sha256,
        html_size_bytes=html_artifact.size_bytes,
        html_mime_type=html_artifact.mime_type,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_archive_snapshot(db: Session, session_id: str) -> dict:
    return read_archive_snapshot(ensure_examination_protocol_archive(db, session_id))
