"""Phase 1 — shared_engine + test registry + MBTI plugin."""

from __future__ import annotations

import pytest

from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.domain.test_registry import discover_plugins
from psychological_testing.shared_engine.answer_resolver import resolve_answer
from psychological_testing.shared_engine.dichotomy_scorer import VALID_TYPE_CODES
from psychological_testing.shared_engine.interpretation_engine import evaluate, interpret, load_type_profiles
from psychological_testing.shared_engine.item_bank_loader import load_mbti_items
from psychological_testing.shared_engine.question_selector import select_from_definition
from psychological_testing.shared_engine.report_builder import build_text_report
from psychological_testing.shared_engine.scoring_pipeline import score


class TestMbtiPluginRegistry:
    def test_discovers_mbti_plugin(self) -> None:
        plugins = discover_plugins()
        assert "mbti" in plugins
        definition = plugins["mbti"]
        assert definition.scoring_type == "dichotomy_weighted_choice"
        assert definition.item_bank == "data/banks/v1/mbti_items.yaml"
        assert definition.interpretation == "data/interpretations/v1/mbti_16_types.yaml"

    def test_registry_get(self) -> None:
        registry = PluginRegistry()
        assert registry.get("mbti").version == "1.0.0"


class TestMbtiScoringPipeline:
    @pytest.fixture
    def mbti_definition(self):
        return PluginRegistry().get("mbti")

    def test_intj_from_eight_answers(self, mbti_definition) -> None:
        answers = [
            ("E/I", "I"),
            ("S/N", "N"),
            ("T/F", "T"),
            ("J/P", "J"),
        ] * 2
        result = score(mbti_definition, answers)
        assert result.typology_code == "INTJ"
        assert result.axis_details["E/I"]["dominant"] == "I"
        assert result.axis_details["S/N"]["dominant"] == "N"
        assert result.metadata["scoring_type"] == "dichotomy_weighted_choice"

    @pytest.mark.parametrize(
        "type_code,answers",
        [
            (
                "ENFP",
                [
                    ("E/I", "E"),
                    ("S/N", "N"),
                    ("T/F", "F"),
                    ("J/P", "P"),
                ]
                * 3,
            ),
            (
                "ESTJ",
                [
                    ("E/I", "E"),
                    ("S/N", "S"),
                    ("T/F", "T"),
                    ("J/P", "J"),
                ]
                * 3,
            ),
            (
                "INFJ",
                [
                    ("E/I", "I"),
                    ("S/N", "N"),
                    ("T/F", "F"),
                    ("J/P", "J"),
                ]
                * 2,
            ),
        ],
    )
    def test_sample_type_codes(self, mbti_definition, type_code: str, answers: list) -> None:
        result = score(mbti_definition, answers)
        assert result.typology_code == type_code
        assert result.typology_code in VALID_TYPE_CODES


class TestMbtiItemBankAndSelection:
    @pytest.fixture
    def mbti_definition(self):
        return PluginRegistry().get("mbti")

    def test_load_48_items(self, mbti_definition) -> None:
        items = load_mbti_items(mbti_definition.item_bank)  # type: ignore[arg-type]
        assert len(items) == 48

    def test_select_per_definition(self, mbti_definition) -> None:
        items = load_mbti_items(mbti_definition.item_bank)  # type: ignore[arg-type]
        picked = select_from_definition(items, mbti_definition.selection)
        assert len(picked) == 16
        assert {q.axis for q in picked} == {"E/I", "S/N", "T/F", "J/P"}


class TestMbtiInterpretation:
    @pytest.fixture
    def mbti_definition(self):
        return PluginRegistry().get("mbti")

    def test_intj_report_contains_type_and_strengths(self, mbti_definition) -> None:
        answers = [
            ("E/I", "I"),
            ("S/N", "N"),
            ("T/F", "T"),
            ("J/P", "J"),
        ] * 2
        result = evaluate(mbti_definition, answers)
        assert result.typology_code == "INTJ"
        assert result.profile is not None
        assert result.profile.archetype_ru == "Стратег"
        assert "Архитектор" in result.profile.alt_names_ru
        assert "INTJ" in result.report_text
        assert "Стратег" in result.report_text
        assert "Альтернативные названия" in result.report_text
        assert "Сильные стороны" in result.report_text
        assert "Зоны роста" in result.report_text
        assert "не является единственным критерием" in result.report_text

    def test_profile_to_dict_for_session_json(self, mbti_definition) -> None:
        from psychological_testing.shared_engine.interpretation_engine import profile_to_dict

        answers = [("E/I", "I"), ("S/N", "N"), ("T/F", "F"), ("J/P", "J")] * 2
        result = evaluate(mbti_definition, answers)
        assert result.profile is not None
        payload = profile_to_dict(result.profile)
        assert payload["code"] == "INFJ"
        assert payload["archetype_ru"] == "Наставник"
        assert payload["alt_names_ru"] == ["Провидец", "Советник"]
        assert payload["summary_ru"]
        assert payload["strengths"]
        assert payload["growth_areas"]

    def test_all_16_types_in_interpretation_file(self, mbti_definition) -> None:
        profiles = load_type_profiles(mbti_definition.interpretation)  # type: ignore[arg-type]
        assert len(profiles) == 16
        for code in VALID_TYPE_CODES:
            assert code in profiles

    def test_interpret_via_report_builder(self, mbti_definition) -> None:
        score_result = score(mbti_definition, [("E/I", "E"), ("S/N", "N"), ("T/F", "F"), ("J/P", "P")] * 2)
        interp = interpret(mbti_definition, score_result)
        text = build_text_report(interp)
        assert interp.typology_code == "ENFP"
        assert text == interp.report_text


class TestMbtiAnswerResolverProduction:
    def test_voice_to_pole(self) -> None:
        resolved = resolve_answer("mbti", "вариант а", option_a_pole="I", option_b_pole="E")
        assert resolved is not None
        assert resolved.value == "I"
        assert resolved.confidence >= 0.85
