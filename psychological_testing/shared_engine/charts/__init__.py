"""Dynamic chart rendering from session scores (PNG bytes)."""

from __future__ import annotations

from typing import Any

from psychological_testing.shared_engine.charts import mbti_charts, test_charts
from psychological_testing.shared_engine.charts.common import score_values_in_order

PAEI_KEYS = ["P", "A", "E", "I"]
DISC_KEYS = ["D", "I", "S", "C"]
HEXACO_KEYS = ["H", "E", "X", "A", "C", "O"]


def _soft_skills_radar(scores: dict[str, Any], axis_details: dict[str, Any] | None, title: str) -> bytes:
    raw = scores.get("raw_scores") or {}
    metadata = scores.get("metadata") or {}
    skills = metadata.get("skills") or {}
    keys = sorted(raw.keys())
    labels = [str(skills.get(k, k))[:18] for k in keys]
    values = [float(raw[k]) for k in keys]
    return test_charts.soft_skills_radar_png(labels, values, title=title)


def _mbti_decision_tree(scores: dict[str, Any], axis_details: dict[str, Any] | None, title: str) -> bytes:
    details = axis_details or scores.get("axis_details") or {}
    code = str(scores.get("typology_code") or "")
    return mbti_charts.mbti_decision_tree_png(
        typology_code=code,
        axis_details=dict(details),
        title=title or "MBTI — маршрут профиля",
    )


def _mbti_axis_bars(scores: dict[str, Any], axis_details: dict[str, Any] | None, title: str) -> bytes:
    details = axis_details or scores.get("axis_details") or {}
    return mbti_charts.mbti_axis_bars_png(
        axis_details=dict(details),
        title=title or "MBTI — выраженность полюсов",
    )


CHART_RENDERERS = {
    ("paei", "combined"): lambda scores, axis_details, title: test_charts.paei_combined_png(
        PAEI_KEYS,
        score_values_in_order(scores, PAEI_KEYS, prefer_normalized=True),
        title=title,
    ),
    ("disc", "combined"): lambda scores, axis_details, title: test_charts.disc_combined_png(
        DISC_KEYS,
        score_values_in_order(scores, DISC_KEYS, prefer_normalized=True),
        title=title,
    ),
    ("hexaco", "radar"): lambda scores, axis_details, title: test_charts.hexaco_radar_png(
        HEXACO_KEYS,
        score_values_in_order(scores, HEXACO_KEYS, prefer_normalized=True),
        title=title,
    ),
    ("soft_skills", "radar"): _soft_skills_radar,
    ("mbti", "decision_tree"): _mbti_decision_tree,
    ("mbti", "axis_bars"): _mbti_axis_bars,
}


def render_chart_bytes(
    chart_type: str,
    *,
    test_id: str,
    scores: dict[str, Any] | None,
    axis_details: dict[str, Any] | None = None,
    title: str = "",
) -> bytes:
    """Render a chart to PNG bytes. Raises KeyError if chart_type unsupported for test."""
    if scores is None:
        raise ValueError("scores required for chart rendering")
    key = (test_id, chart_type)
    renderer = CHART_RENDERERS.get(key)
    if renderer is None:
        raise KeyError(f"unsupported chart: {test_id}/{chart_type}")
    return renderer(scores, axis_details, title)


__all__ = ["render_chart_bytes", "CHART_RENDERERS"]
