"""Google Drive report storage (mocked; no real API calls)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from psychological_testing.integration.report_storage import (
    artifact_open_url,
    artifact_link_label,
    client_drive_folder_name,
    download_pdf,
    drive_export_path_parts,
    export_artifact_metadata,
    gdrive_enabled,
    is_gdrive_ref,
    make_gdrive_ref,
    parse_gdrive_file_id,
    storage_kind_for_ref,
    sync_pdf_ref_to_sessions,
    upload_pdf_to_drive,
)


def test_artifact_open_url_local_and_gdrive() -> None:
    assert storage_kind_for_ref("gdrive:abc") == "gdrive"
    assert storage_kind_for_ref("data/report_exports/x.pdf") == "local"
    gurl = artifact_open_url("gdrive:abc123")
    assert gurl and "drive.google.com" in gurl
    local = artifact_open_url(
        "data/report_exports/c1/report.pdf", client_id="org-1"
    )
    assert local and "export-pdf/file" in local and "client_id=org-1" in local
    meta = export_artifact_metadata("gdrive:xyz", client_id="c1")
    assert meta["storage_kind"] == "gdrive"
    assert meta["pdf_open_url"]
    assert artifact_link_label("gdrive") == "Открыть в Google Drive"


def test_gdrive_ref_parse() -> None:
    assert parse_gdrive_file_id("gdrive:abc123") == "abc123"
    assert parse_gdrive_file_id(
        "https://drive.google.com/file/d/xyz/view?usp=sharing"
    ) == "xyz"
    assert is_gdrive_ref("gdrive:abc")
    assert not is_gdrive_ref("data/report_exports/x.pdf")


def test_drive_export_path_parts_day_then_client() -> None:
    assert drive_export_path_parts(
        "org-1",
        "2026-05-21",
        client_name="ТОО Второе",
    ) == [
        "2026-05-21",
        "TOO_Vtoroe",
    ]


def test_client_drive_folder_name_from_hr_title() -> None:
    assert client_drive_folder_name(
        "75688147cef140a18403f71b4cd5def1",
        client_name="ТОО Один",
    ) == "TOO_Odin"
    with patch(
        "psychological_testing.integration.report_storage._resolve_client_display_name",
        return_value="ТОО Второе",
    ):
        assert client_drive_folder_name("75688147cef140a18403f71b4cd5def1") == "TOO_Vtoroe"


def test_client_drive_folder_name_fallback_to_client_id() -> None:
    with patch(
        "psychological_testing.integration.report_storage._resolve_client_display_name",
        return_value="75688147cef140a18403f71b4cd5def1",
    ):
        assert (
            client_drive_folder_name("75688147cef140a18403f71b4cd5def1")
            == "75688147cef140a18403f71b4cd5def1"
        )


def test_gdrive_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PSYCH_TESTING_GDRIVE", raising=False)
    monkeypatch.setattr(
        "psychological_testing.integration.report_storage._load_gdrive_env",
        lambda: None,
    )
    assert gdrive_enabled() is False


def test_upload_pdf_returns_gdrive_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_GDRIVE", "1")

    with (
        patch(
            "psychological_testing.integration.report_storage._drive_target_folder",
            return_value="folder-1",
        ) as target_folder,
        patch(
            "psychological_testing.integration.google_drive_client.upload_bytes",
            return_value={"file_id": "file-99", "web_view_link": "https://example/view"},
        ),
    ):
        ref = upload_pdf_to_drive(
            b"%PDF-1.4",
            filename="t.pdf",
            client_id="org-1",
            day="2026-05-21",
        )

    assert ref == make_gdrive_ref("file-99")
    target_folder.assert_called_once_with("org-1", "2026-05-21", client_name=None)


def test_download_pdf_from_gdrive_ref() -> None:
    with patch(
        "psychological_testing.integration.google_drive_client.download_bytes",
        return_value=b"%PDF-mock",
    ):
        data = download_pdf("gdrive:file-99")
    assert data == b"%PDF-mock"


def test_sync_pdf_ref_to_sessions(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path))

    session_id = "sess-sync-001"
    day = tmp_path / "2026-05-20"
    day.mkdir(parents=True)
    doc = {
        "session_id": session_id,
        "client_id": "c1",
        "employee_id": "e1",
        "test_id": "disc",
        "completed_at": "2026-05-20T10:00:00+00:00",
        "report": {"text_telegram": "ok", "pdf_ref": None},
    }
    (day / f"{session_id}.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8"
    )

    manifest = {
        "session_refs": [{"test_id": "disc", "session_id": session_id}],
    }
    pdf_ref = make_gdrive_ref("pdf-file-1")
    n = sync_pdf_ref_to_sessions(manifest, pdf_ref)
    assert n == 1

    updated = json.loads((day / f"{session_id}.json").read_text(encoding="utf-8"))
    assert updated["report"]["pdf_ref"] == pdf_ref
