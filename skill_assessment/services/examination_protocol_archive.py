# route: (examination) | file: skill_assessment/services/examination_protocol_archive.py
"""Archive registry and artifact orchestration for examination protocols."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

_log = logging.getLogger(__name__)


class ProtocolArchiveCorruptedError(RuntimeError):
    """Stored artifact no longer matches registry metadata."""


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
    _verify_archive_artifact(
        row.snapshot_storage_key,
        expected_sha256=row.snapshot_sha256,
        expected_size=row.snapshot_size_bytes,
        archive_id=row.id,
        artifact_kind="snapshot",
    )
    data = protocol_storage.read_artifact(row.snapshot_storage_key)
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        _log.error(
            "archive.corrupted archive_id=%s session_id=%s artifact=snapshot reason=json_decode_failed",
            row.id,
            row.session_id,
        )
        raise ProtocolArchiveCorruptedError("snapshot_json_decode_failed") from e


def read_archive_html(row: ExaminationProtocolArchiveRow) -> str:
    _verify_archive_artifact(
        row.html_storage_key,
        expected_sha256=row.html_sha256,
        expected_size=row.html_size_bytes,
        archive_id=row.id,
        artifact_kind="html",
    )
    return protocol_storage.read_artifact(row.html_storage_key).decode("utf-8")


def protocol_out_from_archive(row: ExaminationProtocolArchiveRow) -> ExaminationProtocolOut:
    return protocol_from_snapshot(read_archive_snapshot(row))


def render_protocol_html_from_snapshot(snapshot: dict) -> str:
    from skill_assessment.services import examination_service as ex

    return ex.render_examination_protocol_html(protocol_from_snapshot(snapshot))


def _verify_archive_artifact(
    storage_key: str,
    *,
    expected_sha256: str,
    expected_size: int,
    archive_id: str,
    artifact_kind: str,
) -> None:
    try:
        meta = protocol_storage.artifact_metadata(storage_key, mime_type="application/octet-stream")
    except FileNotFoundError as e:
        _log.error(
            "archive.corrupted archive_id=%s artifact=%s storage_key=%s reason=missing",
            archive_id,
            artifact_kind,
            storage_key,
        )
        raise ProtocolArchiveCorruptedError(f"{artifact_kind}_missing") from e
    if meta.sha256 != expected_sha256 or meta.size_bytes != expected_size:
        _log.error(
            "archive.corrupted archive_id=%s artifact=%s storage_key=%s reason=checksum_or_size_mismatch",
            archive_id,
            artifact_kind,
            storage_key,
        )
        raise ProtocolArchiveCorruptedError(f"{artifact_kind}_checksum_or_size_mismatch")


def verify_archive_artifacts(row: ExaminationProtocolArchiveRow) -> None:
    _verify_archive_artifact(
        row.snapshot_storage_key,
        expected_sha256=row.snapshot_sha256,
        expected_size=row.snapshot_size_bytes,
        archive_id=row.id,
        artifact_kind="snapshot",
    )
    _verify_archive_artifact(
        row.html_storage_key,
        expected_sha256=row.html_sha256,
        expected_size=row.html_size_bytes,
        archive_id=row.id,
        artifact_kind="html",
    )


def ensure_examination_protocol_archive(db: Session, session_id: str) -> ExaminationProtocolArchiveRow:
    existing = get_archive_by_session(db, session_id)
    if existing is not None:
        verify_archive_artifacts(existing)
        _log.info("archive.reused archive_id=%s session_id=%s", existing.id, session_id)
        return existing

    session = db.get(ExaminationSessionRow, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="examination_session_not_found")
    if session.status != "completed" or session.phase != "completed":
        raise HTTPException(status_code=400, detail="protocol_archive_requires_completed_session")

    prefix = _storage_prefix(session.client_id, session.id)
    snapshot_key = f"{prefix}/snapshot.json"
    html_key = f"{prefix}/protocol.html"
    try:
        snapshot_raw = protocol_storage.read_artifact(snapshot_key)
        snapshot = json.loads(snapshot_raw.decode("utf-8"))
        snapshot_artifact = protocol_storage.artifact_metadata(snapshot_key, mime_type=SNAPSHOT_MIME_TYPE)
        _log.info("archive.reused session_id=%s reason=orphan_snapshot", session_id)
    except FileNotFoundError:
        snapshot = build_examination_protocol_snapshot(db, session_id)
        snapshot_artifact = protocol_storage.put_immutable_artifact(
            snapshot_key,
            snapshot_bytes(snapshot),
            mime_type=SNAPSHOT_MIME_TYPE,
        )
    except Exception as e:
        _log.error(
            "archive.corrupted session_id=%s artifact=snapshot storage_key=%s reason=orphan_snapshot_unreadable",
            session_id,
            snapshot_key,
        )
        raise ProtocolArchiveCorruptedError("orphan_snapshot_unreadable") from e

    try:
        html_artifact = protocol_storage.artifact_metadata(html_key, mime_type=HTML_MIME_TYPE)
        _log.info("archive.reused session_id=%s reason=orphan_html", session_id)
    except FileNotFoundError:
        try:
            html = render_protocol_html_from_snapshot(snapshot)
        except Exception:
            _log.exception("archive.render_failed session_id=%s", session_id)
            raise
        html_artifact = protocol_storage.put_immutable_artifact(
            html_key,
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
    try:
        db.commit()
        db.refresh(row)
        _log.info("archive.created archive_id=%s session_id=%s", row.id, session_id)
        return row
    except IntegrityError:
        db.rollback()
        existing_after_race = get_archive_by_session(db, session_id)
        if existing_after_race is None:
            raise
        verify_archive_artifacts(existing_after_race)
        _log.info("archive.reused archive_id=%s session_id=%s reason=integrity_race", existing_after_race.id, session_id)
        return existing_after_race


def ensure_archive_snapshot(db: Session, session_id: str) -> dict:
    return read_archive_snapshot(ensure_examination_protocol_archive(db, session_id))
