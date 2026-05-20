"""MBTI profile visualizations from axis_details in session JSON."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from psychological_testing.shared_engine.charts.common import PRINT_COLORS, figure_to_png_bytes

AXIS_SEQUENCE = ("E/I", "S/N", "T/F", "J/P")
AXIS_LABELS = {
    "E/I": ("E", "I", "Экстраверсия", "Интроверсия"),
    "S/N": ("S", "N", "Сенсорика", "Интуиция"),
    "T/F": ("T", "F", "Мышление", "Чувство"),
    "J/P": ("J", "P", "Суждение", "Восприятие"),
}


def _axis_detail(axis_details: dict[str, Any], axis: str) -> dict[str, Any]:
    detail = axis_details.get(axis) or {}
    return detail if isinstance(detail, dict) else {}


def mbti_decision_tree_png(
    *,
    typology_code: str,
    axis_details: dict[str, Any],
    title: str = "MBTI — маршрут профиля",
) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=PRINT_COLORS["background"])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    levels = [
        (1.0, 5.0, "E/I"),
        (3.5, 5.0, "S/N"),
        (6.0, 5.0, "T/F"),
        (8.5, 5.0, "J/P"),
    ]
    path_x = [0.8]
    for idx, (x, y, axis) in enumerate(levels):
        pos, neg, pos_ru, neg_ru = AXIS_LABELS[axis]
        detail = _axis_detail(axis_details, axis)
        dominant = str(detail.get("dominant") or typology_code[idx])
        counts = detail.get("counts") or {}
        pos_count = int(counts.get(pos, 0))
        neg_count = int(counts.get(neg, 0))

        ax.text(x, y + 0.55, axis, ha="center", fontsize=10, fontweight="bold")

        for pole, pole_ru, offset, count in (
            (pos, pos_ru, -0.55, pos_count),
            (neg, neg_ru, 0.55, neg_count),
        ):
            active = pole == dominant
            color = PRINT_COLORS["accent"] if active else PRINT_COLORS["light"]
            text_color = "white" if active else PRINT_COLORS["primary"]
            rect = mpatches.FancyBboxPatch(
                (x + offset - 0.45, y - 0.35),
                0.9,
                0.55,
                boxstyle="round,pad=0.02",
                linewidth=1.5 if active else 0.8,
                edgecolor=PRINT_COLORS["primary"] if active else PRINT_COLORS["secondary"],
                facecolor=color,
            )
            ax.add_patch(rect)
            ax.text(
                x + offset,
                y - 0.08,
                f"{pole}\n{count}",
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold" if active else "normal",
                color=text_color,
            )
        path_x.append(x + (-0.55 if dominant == pos else 0.55))

        if idx < len(levels) - 1:
            next_x = levels[idx + 1][0]
            ax.annotate(
                "",
                xy=(next_x - 0.8, y - 0.15),
                xytext=(x + (0.55 if dominant == neg else -0.55), y - 0.35),
                arrowprops=dict(arrowstyle="->", color=PRINT_COLORS["secondary"], lw=1.2),
            )

    ax.text(
        5.0,
        0.7,
        f"Итоговый тип: {typology_code}",
        ha="center",
        fontsize=13,
        fontweight="bold",
        color=PRINT_COLORS["primary"],
    )
    ax.set_title(title, fontsize=12, fontweight="bold", color=PRINT_COLORS["primary"], pad=12)
    return figure_to_png_bytes(fig, dpi=150)


def mbti_axis_bars_png(
    *,
    axis_details: dict[str, Any],
    title: str = "MBTI — выраженность полюсов",
) -> bytes:
    rows: list[tuple[str, str, int, bool]] = []
    for axis in AXIS_SEQUENCE:
        pos, neg, pos_ru, neg_ru = AXIS_LABELS[axis]
        detail = _axis_detail(axis_details, axis)
        dominant = str(detail.get("dominant") or "")
        counts = detail.get("counts") or {}
        rows.append((f"{pos} ({pos_ru[:3]}.)", pos, int(counts.get(pos, 0)), dominant == pos))
        rows.append((f"{neg} ({neg_ru[:3]}.)", neg, int(counts.get(neg, 0)), dominant == neg))

    labels = [r[0] for r in rows]
    values = [r[2] for r in rows]
    colors = [
        PRINT_COLORS["accent"] if r[3] else PRINT_COLORS["light"] for r in rows
    ]

    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=PRINT_COLORS["background"])
    y_pos = range(len(labels))
    ax.barh(list(y_pos), values, color=colors, edgecolor=PRINT_COLORS["background"])
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Количество ответов по полюсу", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", color=PRINT_COLORS["primary"])
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.3)
    return figure_to_png_bytes(fig, dpi=150)
