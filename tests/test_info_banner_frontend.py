"""Запуск frontend-тестов info-banner.js через Node."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TEST = ROOT / "tests" / "js" / "test_info_banner.mjs"


def test_info_banner_js():
    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not installed")
    proc = subprocess.run(
        [node, str(JS_TEST)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
