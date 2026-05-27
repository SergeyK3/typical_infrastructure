#!/usr/bin/env python3
"""Устаревший алиас — используйте scripts/fix_hosp_skills_from_regulations.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fix_hosp_skills_from_regulations import fix_hosp_skills_and_kpis, main

if __name__ == "__main__":
    main()
