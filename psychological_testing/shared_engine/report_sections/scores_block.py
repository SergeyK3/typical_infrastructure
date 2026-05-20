"""Score summary bullets (legacy PDF structure)."""

from __future__ import annotations

from typing import Any

from psychological_testing.shared_engine.item_lookup import LEGACY_EXPECTED_ITEMS
from psychological_testing.shared_engine.report_sections.constants import (
    DISC_STYLE_NAMES,
    HEXACO_FACTOR_NAMES,
    PAEI_ROLE_NAMES,
)


def _numeric_scores(session: dict[str, Any]) -> dict[str, float]:
    scores = session.get("scores") or {}
    if not isinstance(scores, dict):
        return {}
    block = scores.get("normalized_scores") or scores.get("raw_scores") or {}
    if not isinstance(block, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in block.items():
        try:
            out[str(key)] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _dominant_key(scores: dict[str, float]) -> str | None:
    if not scores:
        return None
    return max(scores.items(), key=lambda x: x[1])[0]


def mini_bank_footnote(test_id: str, response_count: int) -> str | None:
    expected = LEGACY_EXPECTED_ITEMS.get(test_id)
    if expected and response_count < expected:
        return (
            f"Примечание: в отчёте {response_count} из {expected} вопросов банка v1 "
            f"(legacy — {expected}). Расширение банка: PT-BANK-01."
        )
    return None


def score_bullets_for_test(test_id: str, session: dict[str, Any]) -> list[str]:
    """Return bullet lines describing numeric results."""
    scores = _numeric_scores(session)
    if not scores:
        return []

    bullets: list[str] = []
    if test_id == "paei":
        for key in ("P", "A", "E", "I"):
            if key in scores:
                name = PAEI_ROLE_NAMES.get(key, key)
                bullets.append(f"{name}: {scores[key]:.0f} баллов")
        dom = _dominant_key(scores)
        if dom:
            bullets.insert(
                0,
                f"Преобладает роль {PAEI_ROLE_NAMES.get(dom, dom)} — {scores[dom]:.0f} баллов",
            )
    elif test_id == "disc":
        for key in ("D", "I", "S", "C"):
            if key in scores:
                bullets.append(f"{DISC_STYLE_NAMES.get(key, key)}: {scores[key]:.1f}")
        dom = _dominant_key(scores)
        if dom:
            bullets.insert(
                0,
                f"Преобладающий стиль: {DISC_STYLE_NAMES.get(dom, dom)} ({scores[dom]:.1f})",
            )
    elif test_id == "hexaco":
        for key in ("H", "E", "X", "A", "C", "O"):
            if key in scores:
                bullets.append(f"{HEXACO_FACTOR_NAMES.get(key, key)}: {scores[key]:.1f}")
        dom = _dominant_key(scores)
        if dom:
            bullets.insert(
                0,
                f"Наиболее выраженный фактор: {HEXACO_FACTOR_NAMES.get(dom, dom)} ({scores[dom]:.1f})",
            )
    elif test_id == "soft_skills":
        dom = _dominant_key(scores)
        for key, val in sorted(scores.items(), key=lambda x: -x[1]):
            bullets.append(f"{key}: {val:.1f}")
        if dom:
            bullets.insert(0, f"Наиболее развитый навык: {dom} — {scores[dom]:.1f}")
    return bullets
