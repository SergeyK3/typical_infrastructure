#!/usr/bin/env python3
"""Inject theme.js after layout.css in static HTML pages."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = '  <script src="/static/shared/theme.js?v=ui-theme-20260522"></script>\n'
PAT = re.compile(r'(<link rel="stylesheet" href="/static/shared/layout\.css[^"]*">)\n')


def main() -> int:
    count = 0
    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if "layout.css" not in text or "theme.js" in text:
            continue
        new, n = PAT.subn(r"\1\n" + SCRIPT, text, count=1)
        if n:
            path.write_text(new, encoding="utf-8")
            print(path.relative_to(ROOT))
            count += 1
    print(f"patched {count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
