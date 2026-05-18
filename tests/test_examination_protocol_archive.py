from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from skill_assessment.domain.examination_entities import ConsentStatus, ExaminationPhase, ExaminationSessionStatus
from skill_assessment.infrastructure.db_models import (
    ExaminationAnswerRow,
    ExaminationProtocolArchiveRow,
    ExaminationQuestionRow,
    ExaminationSessionRow,
)
from skill_assessment.services import examination_protocol_archive as archive_svc
from skill_assessment.services import protocol_storage


def _completed_exam_session(db, *, answer_text: str = "Подробно соблюдаю регламент и фиксирую результат.") -> str:
    db.execute(delete(ExaminationProtocolArchiveRow))
    db.execute(delete(ExaminationAnswerRow))
    db.execute(delete(ExaminationQuestionRow))
    db.execute(delete(ExaminationSessionRow))
    db.commit()
    db.expire_all()
    sid = str(uuid.uuid4())
    qid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(
        ExaminationSessionRow(
            id=sid,
            client_id="archive_client",
            employee_id="archive_employee",
            scenario_id=sid,
            status=ExaminationSessionStatus.COMPLETED.value,
            phase=ExaminationPhase.COMPLETED.value,
            consent_status=ConsentStatus.ACCEPTED.value,
            needs_hr_release=False,
            current_question_index=1,
            started_at=now,
            completed_at=now,
            question_scenario_id=sid,
        )
    )
    db.add(
        ExaminationQuestionRow(
            id=qid,
            scenario_id=sid,
            seq=0,
            text="Опишите порядок работы по регламенту.",
        )
    )
    db.add(
        ExaminationAnswerRow(
            id=str(uuid.uuid4()),
            session_id=sid,
            question_id=qid,
            transcript_text=answer_text,
        )
    )
    db.commit()
    return sid


def test_protocol_storage_rejects_different_overwrite(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    first = protocol_storage.put_immutable_artifact(
        "protocol_archive/test/artifact.txt",
        b"same",
        mime_type="text/plain",
    )
    second = protocol_storage.put_immutable_artifact(
        "protocol_archive/test/artifact.txt",
        b"same",
        mime_type="text/plain",
    )
    assert first.sha256 == second.sha256
    with pytest.raises(FileExistsError):
        protocol_storage.put_immutable_artifact(
            "protocol_archive/test/artifact.txt",
            b"different",
            mime_type="text/plain",
        )


def test_ensure_protocol_archive_writes_snapshot_and_html(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db)
        archive = archive_svc.ensure_examination_protocol_archive(db, session_id)

        assert archive.status == "ready"
        assert archive.immutable is True
        assert archive.snapshot_storage_key.endswith("/snapshot.json")
        assert archive.html_storage_key.endswith("/protocol.html")
        assert archive.snapshot_sha256
        assert archive.html_sha256
        assert archive.snapshot_size_bytes > 0
        assert archive.html_size_bytes > 0
        assert archive.archived_at is not None
        assert archive.retention_class == "standard"
        assert archive.legal_hold is False

        snapshot = archive_svc.read_archive_snapshot(archive)
        assert snapshot["schema_version"] == "examination_protocol_snapshot.v1"
        assert snapshot["session"]["id"] == session_id
        assert snapshot["questions"][0]["answer"]["transcript_text"].startswith("Подробно")
    finally:
        db.close()


def test_protocol_html_route_serves_archived_content_after_live_answer_change(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="ORIGINAL_ARCHIVED_ANSWER")
        archive_svc.ensure_examination_protocol_archive(db, session_id)
        answer = db.query(ExaminationAnswerRow).filter(ExaminationAnswerRow.session_id == session_id).one()
        answer.transcript_text = "LIVE_CHANGED_ANSWER"
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/skill-assessment/examination/sessions/{session_id}/protocol/html")
    assert resp.status_code == 200
    assert "ORIGINAL_ARCHIVED_ANSWER" in resp.text
    assert "LIVE_CHANGED_ANSWER" not in resp.text

    meta = client.get(f"/api/skill-assessment/examination/sessions/{session_id}/protocol/archive")
    assert meta.status_code == 200
    archive_id = meta.json()["id"]
    snapshot = client.get(f"/api/skill-assessment/examination/protocol-archives/{archive_id}/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["questions"][0]["answer"]["transcript_text"] == "ORIGINAL_ARCHIVED_ANSWER"


def test_archive_route_survives_deleted_session_employee_and_regulation(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="ARCHIVE_WITHOUT_LIVE_SESSION")
        archive = archive_svc.ensure_examination_protocol_archive(db, session_id)
        archive_id = archive.id
        session = db.get(ExaminationSessionRow, session_id)
        db.delete(session)
        db.commit()
    finally:
        db.close()

    by_session = client.get(f"/api/skill-assessment/examination/sessions/{session_id}/protocol/html")
    assert by_session.status_code == 200
    assert "ARCHIVE_WITHOUT_LIVE_SESSION" in by_session.text

    by_archive = client.get(f"/api/skill-assessment/examination/protocol-archives/{archive_id}/snapshot")
    assert by_archive.status_code == 200
    assert by_archive.json()["session"]["id"] == session_id


def test_archive_corruption_is_reported_on_route(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="CORRUPTION_ORIGINAL")
        archive = archive_svc.ensure_examination_protocol_archive(db, session_id)
        protocol_storage.artifact_path(archive.html_storage_key).write_text("corrupted", encoding="utf-8")
    finally:
        db.close()

    resp = client.get(f"/api/skill-assessment/examination/sessions/{session_id}/protocol/html")
    assert resp.status_code == 409
    assert "protocol_archive_corrupted" in resp.text


def test_archive_integrity_scan_reports_ok_corruption_and_orphans(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="SCAN_OK")
        archive = archive_svc.ensure_examination_protocol_archive(db, session_id)
        protocol_storage.put_immutable_artifact(
            "protocol_archive/examination/orphan/snapshot.json",
            b"{}",
            mime_type="application/json",
        )

        ok = archive_svc.verify_archive_integrity(db)
        assert ok["checked"] >= 1
        assert ok["ok"] >= 1
        assert ok["corrupted"] == 0
        assert ok["orphan_storage_key_count"] == 1

        protocol_storage.artifact_path(archive.snapshot_storage_key).write_text("corrupted", encoding="utf-8")
        broken = archive_svc.verify_archive_integrity(db)
        assert broken["corrupted"] == 1
        assert broken["corrupted_items"][0]["archive_id"] == archive.id
    finally:
        db.close()


def test_archive_metrics_track_create_corruption_and_recovery(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    before = archive_svc.archive_metrics_snapshot()
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="METRICS_ANSWER")
        first = archive_svc.ensure_examination_protocol_archive(db, session_id)
        db.delete(first)
        db.commit()
        recreated = archive_svc.ensure_examination_protocol_archive(db, session_id)
        protocol_storage.artifact_path(recreated.html_storage_key).write_text("corrupted", encoding="utf-8")
        with pytest.raises(archive_svc.ProtocolArchiveCorruptedError):
            archive_svc.read_archive_html(recreated)
    finally:
        db.close()

    after = archive_svc.archive_metrics_snapshot()
    assert after["archive_create_count"] >= before["archive_create_count"] + 2
    assert after["archive_size_bytes_total"] > before["archive_size_bytes_total"]
    assert after["archive_recovery_count"] >= before["archive_recovery_count"] + 2
    assert after["archive_corruption_count"] >= before["archive_corruption_count"] + 1


def test_archive_creation_reuses_existing_registry_and_orphan_artifacts(client, tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("SKILL_ASSESSMENT_DATA_DIR", str(tmp_path))
    caplog.set_level("INFO", logger="skill_assessment.services.examination_protocol_archive")
    db = SessionLocal()
    try:
        session_id = _completed_exam_session(db, answer_text="ORPHAN_RETRY_ANSWER")
        first = archive_svc.ensure_examination_protocol_archive(db, session_id)
        first_snapshot_sha = first.snapshot_sha256
        first_html_sha = first.html_sha256

        reused = archive_svc.ensure_examination_protocol_archive(db, session_id)
        assert reused.id == first.id

        db.delete(first)
        db.commit()
        caplog.clear()
        recreated = archive_svc.ensure_examination_protocol_archive(db, session_id)

        assert recreated.id != first.id
        assert recreated.snapshot_sha256 == first_snapshot_sha
        assert recreated.html_sha256 == first_html_sha
        snapshot = archive_svc.read_archive_snapshot(recreated)
        assert snapshot["questions"][0]["answer"]["transcript_text"] == "ORPHAN_RETRY_ANSWER"
        assert any("archive.reused" in rec.message for rec in caplog.records)
    finally:
        db.close()
