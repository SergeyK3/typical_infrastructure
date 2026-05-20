"""PDF export contract — registry, manifest, ai_enrichment (Phase A–B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psychological_testing.domain.test_programs import STANDARD_HR_V1
from psychological_testing.integration.session_persistence import (
    SCHEMA_VERSION,
    SESSION_SCHEMA_VERSION_WITH_AI,
    apply_ai_enrichment,
    build_session_result_document,
    persist_session_result,
    update_session_ai_enrichment,
    validate_session_ai_enrichment,
)
from psychological_testing.integration.session_repository import (
    build_session_refs_for_employee,
    get_session_document,
)
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.shared_engine.charts import render_chart_bytes
from psychological_testing.shared_engine.pdf_export_service import build_pdf_bytes
from psychological_testing.shared_engine.report_contract import (
    AI_ENRICHMENT_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    build_default_manifest,
    get_ai_section_text,
    load_section_registry,
    merge_ai_enrichment,
    validate_manifest,
)
from psychological_testing.shared_engine.session_state_machine import SessionEngine


@pytest.fixture
def registry():
    return load_section_registry()


def test_load_section_registry_covers_five_tests(registry) -> None:
    test_sections = {
        spec.test_id
        for spec in registry.sections.values()
        if spec.test_id
    }
    for test_id in ("mbti", "paei", "disc", "hexaco", "soft_skills"):
        assert test_id in test_sections


def test_legacy_template_default_sections(registry) -> None:
    template = registry.templates["legacy_team_assessment_v1"]
    section_ids = {s.section_id for s in template.default_sections}
    assert "mbti" in section_ids
    assert "appendix_qa" in section_ids
    appendix = next(s for s in template.default_sections if s.section_id == "appendix_qa")
    assert appendix.enabled is False


def test_build_default_manifest_matches_program(registry) -> None:
    manifest = build_default_manifest(
        client_id="c1",
        employee_id="e1",
        registry=registry,
    )
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["template_id"] == "legacy_team_assessment_v1"
    assert manifest["program_id"] == STANDARD_HR_V1.program_id
    result = validate_manifest(manifest, registry=registry)
    assert result.ok, result.errors


def test_validate_manifest_rejects_unknown_section(registry) -> None:
    manifest = build_default_manifest(client_id="c1", employee_id="e1", registry=registry)
    manifest["sections"] = [{"section_id": "unknown_section", "enabled": True}]
    result = validate_manifest(manifest, registry=registry)
    assert not result.ok
    assert any("unknown section_id" in e for e in result.errors)


def test_validate_manifest_warns_missing_session_non_strict(registry) -> None:
    manifest = build_default_manifest(client_id="c1", employee_id="e1", registry=registry)
    for section in manifest["sections"]:
        if section.get("section_id") == "mbti":
            section["enabled"] = True
    result = validate_manifest(manifest, registry=registry, strict=False)
    assert result.ok
    assert any("mbti" in w for w in result.warnings)


def test_validate_manifest_errors_missing_session_strict(registry) -> None:
    manifest = build_default_manifest(client_id="c1", employee_id="e1", registry=registry)
    result = validate_manifest(manifest, registry=registry, strict=True)
    assert not result.ok


def test_validate_manifest_rejects_invalid_chart(registry) -> None:
    manifest = build_default_manifest(client_id="c1", employee_id="e1", registry=registry)
    manifest["session_refs"] = [{"test_id": "mbti", "session_id": "s1"}]
    for section in manifest["sections"]:
        if section.get("section_id") == "mbti":
            section["enabled"] = True
            section["charts"] = ["radar"]
    result = validate_manifest(manifest, registry=registry)
    assert not result.ok
    assert any("charts not allowed" in e for e in result.errors)


def test_ai_enrichment_round_trip() -> None:
    paei = TestRegistry().get("paei")
    engine = SessionEngine.start(paei, client_id="c1", employee_id="e1")
    for text in ("p", "a", "e", "i", "p"):
        engine.submit_text(text)
    doc = build_session_result_document(
        engine,
        telegram_chat_id="100",
        report_text="report",
    )
    assert doc["schema_version"] == SCHEMA_VERSION
    assert "ai_enrichment" not in doc

    enrichment = {
        "schema_version": AI_ENRICHMENT_SCHEMA_VERSION,
        "generated_at": "2026-05-20T10:00:00+00:00",
        "provider": "mock",
        "model": "mock",
        "prompt_version": "paei_interpretation_v1",
        "sections": {"interpretation": "Текст AI по PAEI."},
        "usage": {"input_tokens": 1, "output_tokens": 2},
    }
    ok, errors = validate_session_ai_enrichment(enrichment)
    assert ok, errors

    merged = apply_ai_enrichment(doc, enrichment)
    assert merged["schema_version"] == SESSION_SCHEMA_VERSION_WITH_AI
    assert get_ai_section_text(merged, "interpretation") == "Текст AI по PAEI."

    merged_again = merge_ai_enrichment(
        merged,
        {
            **enrichment,
            "sections": {"career_hints": "Подсказки."},
        },
    )
    assert get_ai_section_text(merged_again, "interpretation") == "Текст AI по PAEI."
    assert get_ai_section_text(merged_again, "career_hints") == "Подсказки."


def test_update_session_ai_enrichment_persists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path))

    doc = {
        "schema_version": SCHEMA_VERSION,
        "session_id": "persist-ai-1",
        "employee_id": "e1",
        "client_id": "c1",
        "test_id": "paei",
        "status": "done",
        "completed_at": "2026-05-20T12:00:00+00:00",
    }
    persist_session_result(doc)

    enrichment = {
        "schema_version": AI_ENRICHMENT_SCHEMA_VERSION,
        "generated_at": "2026-05-20T10:00:00+00:00",
        "provider": "mock",
        "model": "mock",
        "prompt_version": "paei_interpretation_v1",
        "sections": {"interpretation": "Cached text."},
    }
    path = update_session_ai_enrichment("persist-ai-1", enrichment)
    assert path is not None

    loaded = get_session_document("persist-ai-1")
    assert loaded is not None
    assert loaded["schema_version"] == SESSION_SCHEMA_VERSION_WITH_AI
    assert get_ai_section_text(loaded, "interpretation") == "Cached text."


def test_build_session_refs_for_employee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path))

    persist_session_result(
        {
            "schema_version": SCHEMA_VERSION,
            "session_id": "old-mbti",
            "employee_id": "e1",
            "test_id": "mbti",
            "status": "done",
            "completed_at": "2026-05-19T12:00:00+00:00",
        }
    )
    persist_session_result(
        {
            "schema_version": SCHEMA_VERSION,
            "session_id": "new-mbti",
            "employee_id": "e1",
            "test_id": "mbti",
            "status": "done",
            "completed_at": "2026-05-20T12:00:00+00:00",
        }
    )

    refs = build_session_refs_for_employee("e1", ["mbti", "paei"])
    assert refs == [{"test_id": "mbti", "session_id": "new-mbti"}]


def test_example_manifest_json_validates(registry) -> None:
    example_path = (
        Path(__file__).resolve().parents[1]
        / "psychological_testing"
        / "data"
        / "report_examples"
        / "manifest_v1_example.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    manifest = payload["manifest"]
    result = validate_manifest(manifest, registry=registry, strict=False)
    assert result.ok, result.errors


@pytest.mark.parametrize(
    ("test_id", "chart_type", "scores"),
    [
        (
            "paei",
            "combined",
            {"raw_scores": {"P": 0, "A": 3, "E": 1, "I": 1}, "normalized_scores": {"P": 0, "A": 60, "E": 20, "I": 20}},
        ),
        (
            "disc",
            "combined",
            {"raw_scores": {"D": 4, "I": 3, "S": 4, "C": 4}, "normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4}},
        ),
        (
            "hexaco",
            "radar",
            {"raw_scores": {"H": 4, "E": 2, "X": 3, "A": 3, "C": 3, "O": 3}, "normalized_scores": {"H": 4, "E": 2, "X": 3, "A": 3, "C": 3, "O": 3}},
        ),
    ],
)
def test_chart_render_returns_png(test_id, chart_type, scores) -> None:
    png = render_chart_bytes(chart_type, test_id=test_id, scores=scores)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500


def test_mbti_charts_from_axis_details() -> None:
    scores = {
        "typology_code": "ISTJ",
        "axis_details": {
            "E/I": {"dominant": "I", "counts": {"E": 0, "I": 4}},
            "S/N": {"dominant": "S", "counts": {"S": 3, "N": 1}},
            "T/F": {"dominant": "T", "counts": {"T": 2, "F": 2}},
            "J/P": {"dominant": "J", "counts": {"J": 2, "P": 2}},
        },
    }
    for chart_type in ("decision_tree", "axis_bars"):
        png = render_chart_bytes(chart_type, test_id="mbti", scores=scores)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_build_pdf_bytes_from_manifest_and_sessions(
    registry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PSYCH_TESTING_PDF_AI", raising=False)
    monkeypatch.delenv("PSYCH_TESTING_AI_ENABLED", raising=False)
    disc_session = {
        "session_id": "s-disc",
        "employee_id": "e1",
        "employee_display_name": "Тест Тестов",
        "test_id": "disc",
        "completed_at": "2026-05-20T08:54:50+00:00",
        "scores": {
            "raw_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
            "normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
        },
        "report": {"text_telegram": "=== РЕЗУЛЬТАТ DISC ===\n\nD=4"},
    }
    mbti_session = {
        "session_id": "s-mbti",
        "employee_id": "e1",
        "employee_display_name": "Тест Тестов",
        "test_id": "mbti",
        "completed_at": "2026-05-20T09:10:08+00:00",
        "scores": {
            "typology_code": "ISTJ",
            "axis_details": {
                "E/I": {"dominant": "I", "counts": {"E": 0, "I": 4}},
                "S/N": {"dominant": "S", "counts": {"S": 3, "N": 1}},
                "T/F": {"dominant": "T", "counts": {"T": 2, "F": 2}},
                "J/P": {"dominant": "J", "counts": {"J": 2, "P": 2}},
            },
        },
        "report": {"text_telegram": "=== ИТОГОВЫЙ ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ ===\n\nISTJ"},
    }
    manifest = build_default_manifest(
        client_id="c1",
        employee_id="e1",
        registry=registry,
        session_refs=[
            {"test_id": "disc", "session_id": "s-disc"},
            {"test_id": "mbti", "session_id": "s-mbti"},
        ],
    )
    for section in manifest["sections"]:
        sid = section.get("section_id")
        if sid in ("paei", "soft_skills", "hexaco", "appendix_qa"):
            section["enabled"] = False

    pdf = build_pdf_bytes(
        manifest,
        sessions_by_test={"disc": disc_session, "mbti": mbti_session},
        registry=registry,
        skip_ai_enrichment=True,
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000
