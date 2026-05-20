"""Shared chart helpers (print palette, normalization, PNG bytes)."""

from __future__ import annotations

import io
from math import log, sqrt
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PRINT_COLORS = {
    "primary": "#2C3E50",
    "secondary": "#34495E",
    "light": "#BDC3C7",
    "accent": "#3498DB",
    "fill": "#ECF0F1",
    "background": "#FFFFFF",
}

PSYCH_COLORS: dict[str, Any] = {
    "PAEI": {
        "P": "#2E4A66",
        "A": "#5B9BD5",
        "E": "#4F81BD",
        "I": "#8FAADC",
    },
    "DISC": {
        "D": "#2E4A66",
        "I": "#4F81BD",
        "S": "#5B9BD5",
        "C": "#8FAADC",
    },
    "HEXACO": {
        "H": "#8064A2",
        "E": "#C55A5A",
        "X": "#4F81BD",
        "A": "#70AD47",
        "C": "#E5B845",
        "O": "#9BBB59",
    },
}


def normalize_chart_values(
    values: list[float],
    method: str = "adaptive",
) -> tuple[list[float], float, str]:
    if not values:
        return values, 10.0, "пустые_данные"

    max_val = max(values)
    min_val = min(v for v in values if v > 0) if any(v > 0 for v in values) else 1.0
    ratio = max_val / min_val if min_val > 0 else float("inf")

    if method == "none" or ratio <= 2.0:
        return values, max(max_val, 10.0), "без_нормализации"

    if method == "adaptive":
        if ratio > 8.0:
            normalized = [log(v + 1, 2) if v > 0 else 0.0 for v in values]
            return normalized, max(normalized), "адаптивный_логарифм"
        if ratio > 4.0:
            normalized = [sqrt(v) if v >= 0 else 0.0 for v in values]
            return normalized, max(normalized), "адаптивный_корень"
        mean_val = sum(values) / len(values)
        normalized = [v * 0.7 + mean_val * 0.3 for v in values]
        return normalized, max(normalized), "адаптивная_мягкая"

    return values, max(max_val, 10.0), "исходные"


def figure_to_png_bytes(fig, *, dpi: int = 150) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="png",
        bbox_inches="tight",
        pad_inches=0.25,
        facecolor=PRINT_COLORS["background"],
        edgecolor="none",
        dpi=dpi,
    )
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def score_values_in_order(
    scores: dict[str, Any],
    keys: list[str],
    *,
    prefer_normalized: bool = True,
) -> list[float]:
    raw = scores.get("raw_scores") or {}
    normalized = scores.get("normalized_scores") or {}
    out: list[float] = []
    for key in keys:
        if prefer_normalized and key in normalized:
            out.append(float(normalized[key]))
        elif key in raw:
            out.append(float(raw[key]))
        else:
            out.append(0.0)
    return out
