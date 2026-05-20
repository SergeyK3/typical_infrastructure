"""Load AI prompt templates from ``data/prompts/v1/``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from psychological_testing.domain.test_registry import resolve_package_path

PROMPTS_DIR = "data/prompts/v1"

# test_id → (filename, prompt_version id for ai_enrichment)
TEST_PROMPT_MAP: dict[str, tuple[str, str]] = {
    "paei": ("paei_interpretation.txt", "paei_interpretation_v1"),
    "disc": ("disc_interpretation.txt", "disc_interpretation_v1"),
    "hexaco": ("hexaco_interpretation.txt", "hexaco_interpretation_v1"),
    "soft_skills": ("soft_skills_interpretation.txt", "soft_skills_interpretation_v1"),
    "mbti": ("mbti_summary.txt", "mbti_summary_v1"),
}

CROSS_TEST_PROMPT_MAP: dict[str, tuple[str, str]] = {
    "general_summary": ("general_summary.txt", "general_summary_v1"),
    "career_recommendations": ("career_recommendations.txt", "career_recommendations_v1"),
}


@lru_cache(maxsize=32)
def load_prompt_text(filename: str) -> str:
    path = resolve_package_path(f"{PROMPTS_DIR}/{filename}")
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def prompt_for_test(test_id: str) -> tuple[str, str]:
    """Return (system_prompt_text, prompt_version)."""
    try:
        filename, version = TEST_PROMPT_MAP[test_id]
    except KeyError as exc:
        raise KeyError(f"no prompt mapping for test_id={test_id}") from exc
    return load_prompt_text(filename), version


def prompt_for_cross_test_slot(slot: str) -> tuple[str, str]:
    """Return (system_prompt_text, prompt_version) for manifest ``ai_cache`` slots."""
    try:
        filename, version = CROSS_TEST_PROMPT_MAP[slot]
    except KeyError as exc:
        raise KeyError(f"no prompt mapping for cross-test slot={slot}") from exc
    return load_prompt_text(filename), version
