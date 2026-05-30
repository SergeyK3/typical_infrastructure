#!/usr/bin/env python3
"""CLI: сгенерировать DOCX-регламент по названию должности (контент из интернета + шаблон HEAD_DEPT)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.regulation_from_web import analyze_template_structure, generate_regulation_from_web, resolve_template_docx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("position_title", help="Название должности, напр. «Специалист по закупкам»")
    parser.add_argument("--comment", default="", help="Дополнительный контекст для поиска")
    parser.add_argument("--template-code", default="default")
    parser.add_argument("--analyze-only", action="store_true", help="Только показать структуру шаблона DOCX")
    args = parser.parse_args()

    if args.analyze_only:
        info = analyze_template_structure(resolve_template_docx())
        print("Template:", info["template_path"])
        print("Headings:", info["headings"])
        print("Fillable paragraphs:", info["fillable_paragraphs"])
        print("Tables:", info["tables"])
        return

    path, draft = generate_regulation_from_web(
        args.position_title,
        args.comment or None,
        template_code=args.template_code,
    )
    print(f"Created: {path}")
    print(f"Regulation code: {draft.regulation_code}")
    print(f"Position code: {draft.position_code}")
    print(f"Goal: {draft.goal_summary[:120]}…")
    if draft.sources:
        print("Sources:")
        for url in draft.sources[:5]:
            print(f"  - {url}")


if __name__ == "__main__":
    main()
