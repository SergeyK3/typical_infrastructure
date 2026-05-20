"""Charts for PAEI, DISC, HEXACO, Soft Skills (ported from legacy psytest.charts)."""

from __future__ import annotations

from math import pi

import matplotlib.pyplot as plt
import numpy as np

from psychological_testing.shared_engine.charts.common import (
    PRINT_COLORS,
    PSYCH_COLORS,
    figure_to_png_bytes,
    normalize_chart_values,
)


def paei_combined_png(labels: list[str], values: list[float], *, title: str = "") -> bytes:
    colors = PSYCH_COLORS["PAEI"]
    total = sum(values) or 1.0
    percentages = [(value / total) * 100 for value in values]
    label_mapping = {
        "P": "Производитель",
        "A": "Администратор",
        "E": "Предприниматель",
        "I": "Интегратор",
    }
    russian_labels = [label_mapping.get(label, label) for label in labels]
    chart_colors = [colors.get(label, "#4F81BD") for label in labels]

    fig, ax = plt.subplots(1, 1, figsize=(6, 6), facecolor="white")
    wedges, _texts = ax.pie(
        values,
        labels=None,
        colors=chart_colors,
        startangle=90,
        wedgeprops={"linewidth": 2, "edgecolor": "white"},
    )
    ax.set_aspect("equal")
    ax.set_title("PAEI - Распределение ролей", fontsize=14, fontweight="bold", color="#2C3E50", pad=16)
    for wedge, label, value, percentage, rus_label in zip(
        wedges, labels, values, percentages, russian_labels
    ):
        angle = (wedge.theta2 + wedge.theta1) / 2
        radius_factor = 0.7 if percentage > 15 else 0.8
        x = radius_factor * wedge.r * np.cos(np.radians(angle))
        y = radius_factor * wedge.r * np.sin(np.radians(angle))
        if percentage > 8:
            ax.text(
                x,
                y,
                f"{rus_label}\n{label} - {value:.0f}\n{percentage:.1f}%",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="white" if label == "E" else "black",
            )
    if title:
        fig.suptitle(title, fontsize=16, fontweight="bold", color="#2C3E50", y=0.95)
    plt.tight_layout()
    return figure_to_png_bytes(fig, dpi=150)


def disc_combined_png(labels: list[str], values: list[float], *, title: str = "") -> bytes:
    colors = PSYCH_COLORS["DISC"]
    chart_colors = [colors.get(label, "#3498DB") for label in labels]
    max_val = max(values) if values else 1.0

    fig, ax = plt.subplots(1, 1, figsize=(5, 6), facecolor="white")
    bars = ax.bar(labels, values, color=chart_colors, edgecolor="white", linewidth=1.5, alpha=0.9)
    ax.set_ylim(0, max_val * 1.2)
    ax.set_ylabel("Средний балл (1-5)", fontsize=12, color="#2C3E50", fontweight="bold")
    ax.set_title("DISC - Уровни по типам", fontsize=14, fontweight="bold", color="#2C3E50", pad=16)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + max_val * 0.02,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#2C3E50",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.3, color="#BDC3C7", linewidth=0.5)
    ax.set_axisbelow(True)
    if title:
        fig.suptitle(title, fontsize=16, fontweight="bold", color="#2C3E50", y=0.95)
    plt.tight_layout()
    return figure_to_png_bytes(fig, dpi=150)


def hexaco_radar_png(labels: list[str], values: list[float], *, title: str = "") -> bytes:
    mapping = {
        "H": "H - Честность",
        "E": "E - Эмоциональность",
        "X": "X - Экстраверсия",
        "A": "A - Доброжелательность",
        "C": "C - Добросовестность",
        "O": "O - Открытость",
    }
    extended_labels = [mapping.get(label, label) for label in labels]
    norm_values, max_norm, method_used = normalize_chart_values(values, "adaptive")
    actual_max = max_norm * 1.1
    if method_used not in ("без_нормализации", "исходные") and title:
        title = f"{title} (норм: {method_used})"

    n = len(extended_labels)
    angles = [i / float(n) * 2 * pi for i in range(n)]
    angles += angles[:1]
    vals = list(norm_values) + norm_values[:1]

    fig = plt.figure(figsize=(3, 3), facecolor=PRINT_COLORS["background"])
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(extended_labels, fontsize=8, color=PRINT_COLORS["primary"])
    ax.set_ylim(0, actual_max)
    ax.grid(True, color=PRINT_COLORS["light"], linewidth=0.6, alpha=0.8)
    color = PSYCH_COLORS["HEXACO"].get("H", PRINT_COLORS["accent"])
    ax.plot(angles, vals, color=color, linewidth=2.5, marker="o", markersize=5)
    ax.fill(angles, vals, color=color, alpha=0.15)
    if title:
        plt.title(title, pad=20, fontsize=10, fontweight="bold", color=PRINT_COLORS["primary"])
    return figure_to_png_bytes(fig, dpi=200)


def soft_skills_radar_png(labels: list[str], values: list[float], *, title: str = "") -> bytes:
    norm_values, max_norm, _method = normalize_chart_values(values, "none")
    actual_max = max(max_norm * 1.1, 5.0)
    n = len(labels)
    angles = [i / float(n) * 2 * pi for i in range(n)]
    angles += angles[:1]
    vals = list(norm_values) + norm_values[:1]

    fig = plt.figure(figsize=(3.2, 3.2), facecolor=PRINT_COLORS["background"])
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=7, color=PRINT_COLORS["primary"])
    ax.set_ylim(0, actual_max)
    ax.grid(True, color=PRINT_COLORS["light"], linewidth=0.6, alpha=0.8)
    color = PRINT_COLORS["accent"]
    ax.plot(angles, vals, color=color, linewidth=2.5, marker="o", markersize=5)
    ax.fill(angles, vals, color=color, alpha=0.15)
    if title:
        plt.title(title, pad=20, fontsize=10, fontweight="bold", color=PRINT_COLORS["primary"])
    return figure_to_png_bytes(fig, dpi=200)
