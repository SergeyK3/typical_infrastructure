"""Phase C: AI enrichment — prompts, lazy cache, manifest ai_cache."""

from __future__ import annotations

import pytest

from psychological_testing.services.interpretation_llm import (
    InterpretationMockLlm,
    build_cross_test_user_prompt,
    build_test_user_prompt,
    enrich_manifest_cross_test,
    enrich_session,
    ensure_export_ai_enrichment,
    get_manifest_ai_text,
)
from psychological_testing.services.prompt_loader import (
    load_prompt_text,
    prompt_for_cross_test_slot,
    prompt_for_test,
)
from psychological_testing.shared_engine.pdf_export_service import build_pdf_bytes
from psychological_testing.shared_engine.report_contract import (
    AI_ENRICHMENT_SCHEMA_VERSION,
    build_default_manifest,
    get_ai_section_text,
    load_section_registry,
)


@pytest.fixture
def registry():
    return load_section_registry()


@pytest.fixture
def mock_llm() -> InterpretationMockLlm:
    return InterpretationMockLlm()


@pytest.fixture
def ai_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PDF_AI", "1")


def test_prompts_v1_loaded_from_legacy_port() -> None:
    paei_text, version = prompt_for_test("paei")
    assert version == "paei_interpretation_v1"
    assert "PAEI" in paei_text or "Адизес" in paei_text or "производитель" in paei_text.lower()

    general_text, g_version = prompt_for_cross_test_slot("general_summary")
    assert g_version == "general_summary_v1"
    assert len(general_text) > 500

    mbti_text, _ = prompt_for_test("mbti")
    assert "MBTI" in mbti_text

    career = load_prompt_text("career_recommendations.txt")
    assert "профессиональному развитию" in career.lower()


def test_enrich_session_writes_interpretation(ai_enabled, mock_llm: InterpretationMockLlm) -> None:
    session = {
        "session_id": "s1",
        "test_id": "disc",
        "scores": {
            "normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
        },
        "report": {"text_telegram": "=== DISC ==="},
    }
    updated = enrich_session(
        session,
        ["interpretation"],
        llm=mock_llm,
        persist=False,
    )
    assert get_ai_section_text(updated, "interpretation")
    assert updated["ai_enrichment"]["schema_version"] == AI_ENRICHMENT_SCHEMA_VERSION
    assert mock_llm.calls


def test_lazy_cache_skips_second_llm_call(ai_enabled, mock_llm: InterpretationMockLlm) -> None:
    session = {
        "session_id": "s2",
        "test_id": "paei",
        "scores": {"normalized_scores": {"P": 2, "A": 3, "E": 1, "I": 1}},
    }
    first = enrich_session(session, ["interpretation"], llm=mock_llm, persist=False)
    calls_after_first = len(mock_llm.calls)
    second = enrich_session(first, ["interpretation"], llm=mock_llm, persist=False)
    assert len(mock_llm.calls) == calls_after_first
    assert get_ai_section_text(second, "interpretation") == get_ai_section_text(
        first, "interpretation"
    )


def test_manifest_general_summary_cache(ai_enabled, mock_llm: InterpretationMockLlm) -> None:
    sessions = {
        "disc": {
            "test_id": "disc",
            "scores": {"normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4}},
        },
        "mbti": {
            "test_id": "mbti",
            "scores": {"typology_code": "ISTJ"},
        },
    }
    manifest = build_default_manifest(client_id="c1", employee_id="e1")
    manifest["sections"] = [
        {"section_id": "general_summary", "enabled": True, "requires_ai": True},
        {"section_id": "cover", "enabled": True},
    ]
    out = enrich_manifest_cross_test(
        manifest,
        sessions,
        ["general_summary"],
        llm=mock_llm,
    )
    text = get_manifest_ai_text(out, "general_summary")
    assert text and "mock" in text.lower()
    assert mock_llm.calls

    calls_after = len(mock_llm.calls)
    enrich_manifest_cross_test(out, sessions, ["general_summary"], llm=mock_llm)
    assert len(mock_llm.calls) == calls_after


def test_ensure_export_ai_enrichment_idempotent(
    ai_enabled,
    mock_llm: InterpretationMockLlm,
    registry,
) -> None:
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
        if section.get("section_id") in ("paei", "soft_skills", "hexaco", "appendix_qa"):
            section["enabled"] = False

    sessions = {
        "disc": {
            "session_id": "s-disc",
            "test_id": "disc",
            "employee_display_name": "Тест",
            "completed_at": "2026-05-20T08:00:00+00:00",
            "scores": {"normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4}},
            "report": {"text_telegram": "DISC"},
        },
        "mbti": {
            "session_id": "s-mbti",
            "test_id": "mbti",
            "employee_display_name": "Тест",
            "completed_at": "2026-05-20T09:00:00+00:00",
            "scores": {
                "typology_code": "ISTJ",
                "axis_details": {
                    "E/I": {"dominant": "I", "counts": {"E": 0, "I": 4}},
                    "S/N": {"dominant": "S", "counts": {"S": 3, "N": 1}},
                    "T/F": {"dominant": "T", "counts": {"T": 2, "F": 2}},
                    "J/P": {"dominant": "J", "counts": {"J": 2, "P": 2}},
                },
            },
            "report": {"text_telegram": "MBTI ISTJ"},
        },
    }

    m1, s1 = ensure_export_ai_enrichment(
        manifest, sessions, registry=registry, llm=mock_llm, persist_sessions=False
    )
    calls_first = len(mock_llm.calls)
    assert get_ai_section_text(s1["disc"], "interpretation")
    assert get_manifest_ai_text(m1, "general_summary")

    m2, s2 = ensure_export_ai_enrichment(
        m1, s1, registry=registry, llm=mock_llm, persist_sessions=False
    )
    assert len(mock_llm.calls) == calls_first
    assert get_ai_section_text(s2["mbti"], "interpretation") == get_ai_section_text(
        s1["mbti"], "interpretation"
    )

    pdf = build_pdf_bytes(
        m2,
        sessions_by_test=s2,
        registry=registry,
        skip_ai_enrichment=True,
    )
    assert pdf[:4] == b"%PDF"
    assert b"mock" not in pdf.lower()  # binary may still contain utf16; smoke only


def test_build_user_prompts() -> None:
    session = {
        "test_id": "hexaco",
        "scores": {"normalized_scores": {"H": 4, "E": 2}},
        "interpretation": {"typology_code": None},
    }
    assert "HEXACO" in build_test_user_prompt(session).upper()
    cross = build_cross_test_user_prompt({"disc": session}, slot="general_summary")
    assert "DISC" in cross
