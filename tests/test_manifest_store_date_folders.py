"""Local export paths: per-date folders under transliterated client name."""

from __future__ import annotations

import json

import pytest

from psychological_testing.integration.manifest_store import (
    export_client_day_dir,
    export_day_string,
    find_cached_pdf_path,
    save_pdf_cache,
)


def test_manifest_cache_key_includes_renderer_version() -> None:
    from psychological_testing.integration import manifest_store as ms
    from psychological_testing.shared_engine import pdf_render_version as prv

    manifest = {
        "schema_version": "1.0.0",
        "template_id": "legacy_team_assessment_v1",
        "session_refs": [{"test_id": "mbti", "session_id": "s1"}],
        "sections": [{"section_id": "cover", "enabled": True}],
        "ai_cache": {},
    }
    key = ms.manifest_cache_key(manifest)
    old = prv.PDF_RENDERER_VERSION
    try:
        prv.PDF_RENDERER_VERSION = "test-bump"
        assert ms.manifest_cache_key(manifest) != key
    finally:
        prv.PDF_RENDERER_VERSION = old


def test_save_export_bundle_writes_paired_pdf(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from psychological_testing.integration.manifest_store import save_export_bundle

    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path))

    manifest = {
        "client_id": "org-1",
        "client_name": "ТОО Один",
        "employee_id": "emp-1",
        "manifest_id": "9334e68a-9610-46ef-9583-29f51b1ee1a2",
        "template_id": "legacy_team_assessment_v1",
        "session_refs": [{"test_id": "disc", "session_id": "s1"}],
        "sections": [{"section_id": "cover", "enabled": True}],
    }
    manifest_path, pdf_path, pdf_ref = save_export_bundle(
        manifest,
        b"%PDF-paired",
        employee_display_name="Kim Sergey Vasilevich",
    )
    assert manifest_path.name == "Kim_Sergey_Vasilevich_9334e68a_manifest.json"
    assert pdf_path.name == "Kim_Sergey_Vasilevich_9334e68a.pdf"
    assert pdf_path.is_file()
    assert pdf_ref.endswith("Kim_Sergey_Vasilevich_9334e68a.pdf")
    wrapper = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert wrapper.get("pdf_filename") == pdf_path.name
    assert wrapper.get("pdf_ref") == pdf_ref


def test_save_pdf_cache_uses_translit_client_folder(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PDF_CACHE", "hash")
    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path))

    manifest = {
        "client_id": "org-1",
        "client_name": "ТОО Второе",
        "employee_id": "emp-1",
        "template_id": "legacy_team_assessment_v1",
        "session_refs": [{"test_id": "disc", "session_id": "s1"}],
        "sections": [{"section_id": "cover", "enabled": True}],
    }
    ref = save_pdf_cache(manifest, b"%PDF-test", employee_display_name="Test User")
    day = export_day_string()
    assert ref.startswith(f"report_exports/TOO_Vtoroe/{day}/Test_User_")
    assert ref.endswith(".pdf")
    assert (tmp_path / "TOO_Vtoroe" / day).is_dir()
    cached = find_cached_pdf_path(manifest, employee_display_name="Test User")
    assert cached is not None
    assert cached.parent.name == day


def test_find_cached_pdf_path_supports_legacy_client_id_layout(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PDF_CACHE", "hash")
    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path))

    manifest = {
        "client_id": "org-1",
        "client_name": "ТОО Второе",
        "employee_id": "emp-1",
        "template_id": "legacy_team_assessment_v1",
        "session_refs": [],
        "sections": [{"section_id": "cover", "enabled": True}],
    }
    cached = find_cached_pdf_path(manifest, employee_display_name="Legacy User")
    assert cached is None

    from psychological_testing.integration.manifest_store import _pdf_cache_basename

    _, filename = _pdf_cache_basename(manifest, employee_display_name="Legacy User")
    legacy = tmp_path / "org-1" / filename
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"%PDF-legacy")

    found = find_cached_pdf_path(manifest, employee_display_name="Legacy User")
    assert found == legacy


def test_save_manifest_resolves_client_name_from_db(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    from psychological_testing.integration.manifest_store import save_manifest

    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path))

    manifest = {
        "client_id": "75688147cef140a18403f71b4cd5def1",
        "employee_id": "emp-1",
        "template_id": "legacy_team_assessment_v1",
        "session_refs": [],
        "sections": [{"section_id": "cover", "enabled": True}],
    }
    with patch(
        "psychological_testing.integration.report_storage._resolve_client_display_name",
        return_value="ТОО Один",
    ):
        path = save_manifest(manifest, employee_display_name="Kim Test")
    assert path.parent.parent.name == "TOO_Odin"
    assert manifest.get("client_name") == "ТОО Один"


def test_export_client_day_dir_creates_nested_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_EXPORTS_DIR", str(tmp_path))
    folder = export_client_day_dir("client-a", "2026-05-21", client_name="ТОО_Бета")
    assert folder == tmp_path / "TOO_Beta" / "2026-05-21"
    assert folder.is_dir()
