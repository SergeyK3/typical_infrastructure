"""Phase E: export-pdf API, preview, RBAC."""

from __future__ import annotations

import json

import pytest

from tests.conftest import onboarding_payload


from app.routers.psychological_testing import _pdf_content_disposition


def test_pdf_content_disposition_cyrillic_translit() -> None:
    name, header = _pdf_content_disposition("emp123456789012345678901234567890", "Ким Сергей Васильевич")
    assert name == "Kim_Sergey_Vasilevich.pdf"
    assert "filename*=" not in header
    assert "Kim_Sergey_Vasilevich.pdf" in header
    header.encode("latin-1")


def test_report_templates_endpoint(client) -> None:
    r = client.get("/api/psychological-testing/report-templates")
    assert r.status_code == 200
    data = r.json()
    assert data["templates"]
    assert any(t["template_id"] == "legacy_team_assessment_v1" for t in data["templates"])
    assert any(s["section_id"] == "mbti" for s in data["sections"])


def test_export_preview_and_pdf_stream(
    client,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("PSYCH_TESTING_GDRIVE", "0")
    monkeypatch.delenv("PSYCH_TESTING_PDF_AI", raising=False)

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_export_org",
            client_name="Psych Export Org",
            admin_login="psych_export_admin",
        ),
    )
    assert onboard.status_code == 200
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]

    day = tmp_path / "sessions" / "2026-05-20"
    day.mkdir(parents=True)
    session_id = "export-test-session-001"
    (day / f"{session_id}.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "client_id": client_id,
                "employee_id": emp_id,
                "employee_display_name": "Export Test",
                "test_id": "disc",
                "status": "done",
                "completed_at": "2026-05-20T12:00:00+00:00",
                "scores": {
                    "normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
                },
                "responses": [{"item_id": "201", "resolved_value": 4}],
                "report": {"text_telegram": "DISC ok"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    preview = client.get(
        f"/api/psychological-testing/employees/{emp_id}/export-preview",
        params={"client_id": client_id},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["manifest"]["employee_id"] == emp_id
    assert body["available_sessions"]

    export = client.post(
        f"/api/psychological-testing/employees/{emp_id}/export-pdf",
        json={
            "client_id": client_id,
            "sections": [
                {"section_id": "cover", "enabled": True},
                {"section_id": "disc", "enabled": True},
                {"section_id": "mbti", "enabled": False},
                {"section_id": "general_summary", "enabled": False},
            ],
            "regenerate_ai": False,
            "response_mode": "stream",
        },
    )
    assert export.status_code == 200
    assert export.headers.get("content-type", "").startswith("application/pdf")
    assert export.content[:4] == b"%PDF"
    assert len(export.content) > 3000


def test_export_rbac_requires_account_when_enabled(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_RBAC_EXPORT", "1")

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_rbac_org",
            client_name="Psych RBAC",
            admin_login="psych_rbac_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]

    r = client.get(
        f"/api/psychological-testing/employees/{emp_id}/export-preview",
        params={"client_id": client_id},
    )
    assert r.status_code == 403
