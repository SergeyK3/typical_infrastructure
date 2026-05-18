from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db import SessionLocal
from skill_assessment.domain.examination_entities import ConsentStatus, ExaminationPhase, ExaminationSessionStatus
from skill_assessment.infrastructure.db_models import (
    ExaminationAnswerRow,
    ExaminationQuestionRow,
    ExaminationSessionRow,
)
from skill_assessment.services import examination_protocol_archive as archive_svc
from skill_assessment.services import protocol_storage


def _completed_exam_session(db, *, answer_text: str = "Подробно соблюдаю регламент и фиксирую результат.") -> str:
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
