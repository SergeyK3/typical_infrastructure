"""Phase D: full template sections, appendix Q&A, layout."""

from __future__ import annotations

import pytest

from psychological_testing.services.interpretation_llm import InterpretationMockLlm
from psychological_testing.shared_engine.item_lookup import load_item_index
from psychological_testing.shared_engine.pdf_export_service import build_pdf_bytes
from psychological_testing.shared_engine.report_contract import build_default_manifest, load_section_registry
from psychological_testing.shared_engine.report_sections.appendix_qa import render_appendix_qa
from psychological_testing.shared_engine.pdf_composer import PdfComposer


@pytest.fixture
def registry():
    return load_section_registry()


def test_item_lookup_disc_bank() -> None:
    index = load_item_index("disc")
    assert "201" in index
    assert "ответственность" in index["201"].text.lower() or len(index["201"].text) > 5


def test_appendix_qa_story_elements(registry) -> None:
    composer = PdfComposer()
    spec = registry.sections["appendix_qa"]
    session = {
        "test_id": "disc",
        "responses": [
            {
                "item_id": "201",
                "resolved_value": 4,
                "raw_input": "4",
            }
        ],
    }
    story = render_appendix_qa(
        composer,
        section=spec,
        sessions_by_test={"disc": session},
    )
    assert len(story) > 3


def test_build_pdf_full_template_with_appendix(
    registry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PDF_AI", "1")

    disc_session = {
        "session_id": "s-disc",
        "employee_id": "e1",
        "employee_display_name": "Тест",
        "test_id": "disc",
        "completed_at": "2026-05-20T08:54:50+00:00",
        "scores": {
            "raw_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
            "normalized_scores": {"D": 4, "I": 3, "S": 4, "C": 4},
        },
        "responses": [
            {"item_id": "201", "resolved_value": 4, "raw_input": "4"},
            {"item_id": "202", "resolved_value": 3, "raw_input": "3"},
        ],
        "report": {"text_telegram": "DISC результат"},
    }
    mbti_session = {
        "session_id": "s-mbti",
        "employee_id": "e1",
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
        "interpretation": {
            "typology_code": "ISTJ",
            "profile": {
                "code": "ISTJ",
                "name_ru": "Логистик",
                "tagline": "Организатор",
                "strengths": ["Системность"],
                "growth_areas": ["Гибкость"],
            },
            "axis_details": {
                "E/I": {"dominant": "I", "level": 3},
            },
        },
        "report": {"text_telegram": "MBTI ISTJ"},
        "responses": [{"item_id": "mbti_ei_001", "resolved_value": "I", "raw_input": "I"}],
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
        if sid in ("paei", "soft_skills", "hexaco"):
            section["enabled"] = False
        if sid == "appendix_qa":
            section["enabled"] = True

    mock = InterpretationMockLlm()
    pdf = build_pdf_bytes(
        manifest,
        sessions_by_test={"disc": disc_session, "mbti": mbti_session},
        registry=registry,
        llm=mock,
        skip_ai_enrichment=False,
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 8000
    assert len(mock.calls) >= 1
