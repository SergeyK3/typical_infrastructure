"""CLI: export PDF from manifest JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from psychological_testing.bootstrap import ensure_typical_infra_working_directory

ensure_typical_infra_working_directory()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export psychological testing PDF from manifest JSON")
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to pt_report_manifest JSON (or wrapper with 'manifest' key)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output PDF path",
    )
    parser.add_argument(
        "--employee",
        help="Override employee_id in manifest (optional)",
    )
    parser.add_argument(
        "--regenerate-ai",
        action="store_true",
        help="Force LLM regeneration even when ai_enrichment / ai_cache exists",
    )
    parser.add_argument(
        "--save-manifest",
        action="store_true",
        help="Write updated manifest (ai_cache) back to --manifest path",
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = raw.get("manifest") if isinstance(raw.get("manifest"), dict) else raw
    if args.employee:
        manifest["employee_id"] = args.employee

    from psychological_testing.shared_engine.pdf_export_service import export_pdf_to_path

    export_pdf_to_path(
        manifest,
        args.output,
        regenerate_ai=args.regenerate_ai,
        manifest_path=args.manifest if args.save_manifest else None,
    )
    print(f"PDF written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
