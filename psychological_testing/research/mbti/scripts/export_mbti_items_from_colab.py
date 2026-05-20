"""Export QUESTIONS dict from structured_questions_scoring.ipynb → mbti_items.yaml.

Usage (from repo root):
    python -m psychological_testing.research.mbti.scripts.export_mbti_items_from_colab
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_MODULE_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_NOTEBOOK = (
    _MODULE_ROOT / "research" / "mbti" / "colab" / "structured_questions_scoring.ipynb"
)
_DEFAULT_OUTPUT = _MODULE_ROOT / "data" / "banks" / "v1" / "mbti_items.yaml"

_AXIS_SLUG = {"E/I": "ei", "S/N": "sn", "T/F": "tf", "J/P": "jp"}


def _extract_questions_source(notebook_path: Path) -> str:
    data = json.loads(notebook_path.read_text(encoding="utf-8"))
    for cell in data.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", [])
        if isinstance(source, list):
            text = "".join(source)
        else:
            text = str(source)
        if "QUESTIONS = {" in text:
            start = text.index("QUESTIONS = {")
            return text[start:]
    raise ValueError(f"QUESTIONS dict not found in {notebook_path}")


def load_questions_from_notebook(notebook_path: Path) -> dict[str, list[dict[str, Any]]]:
    code = _extract_questions_source(notebook_path)
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 — trusted local notebook export
    questions = namespace.get("QUESTIONS")
    if not isinstance(questions, dict):
        raise ValueError("QUESTIONS must be a dict")
    return questions


def questions_to_item_bank(questions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for axis in ("E/I", "S/N", "T/F", "J/P"):
        slug = _AXIS_SLUG[axis]
        pool = questions.get(axis, [])
        for idx, q in enumerate(pool, start=1):
            items.append(
                {
                    "id": f"mbti_{slug}_{idx:03d}",
                    "axis": axis,
                    "text": q["text"],
                    "option_a": {"text": q["option_a"], "pole": q["key_a"]},
                    "option_b": {"text": q["option_b"], "pole": q["key_b"]},
                    "weight": int(q.get("weight", 1)),
                }
            )
    return {
        "version": "1.0.0",
        "test_id": "mbti",
        "lang": "ru",
        "source_notebook": "research/mbti/colab/structured_questions_scoring.ipynb",
        "items": items,
    }


def export_mbti_items(
    notebook_path: Path = _DEFAULT_NOTEBOOK,
    output_path: Path = _DEFAULT_OUTPUT,
) -> int:
    questions = load_questions_from_notebook(notebook_path)
    bank = questions_to_item_bank(questions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# MBTI item bank v1 — exported from Colab notebook 1\n"
        f"# Items: {len(bank['items'])} (12 per axis × 4 axes)\n"
    )
    body = yaml.dump(
        bank,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    output_path.write_text(header + body, encoding="utf-8")
    return len(bank["items"])


def colab_calculate_type_from_answers(answers: list[tuple[str, str]]) -> dict[str, Any]:
    """Reference implementation copied from structured_questions_scoring.ipynb."""
    axis_counts = {
        "E/I": {"E": 0, "I": 0},
        "S/N": {"S": 0, "N": 0},
        "T/F": {"T": 0, "F": 0},
        "J/P": {"J": 0, "P": 0},
    }
    for axis, key in answers:
        if axis in axis_counts and key in axis_counts[axis]:
            axis_counts[axis][key] += 1

    results: dict[str, Any] = {}
    type_code = ""
    axis_mapping = {
        "E/I": ("E", "I"),
        "S/N": ("S", "N"),
        "T/F": ("T", "F"),
        "J/P": ("J", "P"),
    }
    for axis, (pos_key, neg_key) in axis_mapping.items():
        pos_count = axis_counts[axis][pos_key]
        neg_count = axis_counts[axis][neg_key]
        total = pos_count + neg_count
        dominant_letter = pos_key if pos_count >= neg_count else neg_key
        type_code += dominant_letter
        diff = abs(pos_count - neg_count)
        if total == 0:
            level = 1
        else:
            ratio = diff / total
            level = 1 if ratio < 0.3 else (2 if ratio < 0.7 else 3)
        results[axis] = {
            "dominant": dominant_letter,
            "level": level,
            "counts": dict(axis_counts[axis]),
        }
    return {"type_code": type_code, "axes": results}


if __name__ == "__main__":
    count = export_mbti_items()
    print(f"Exported {count} items -> {_DEFAULT_OUTPUT}")
