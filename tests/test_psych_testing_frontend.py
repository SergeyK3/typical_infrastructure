"""Запуск frontend-тестов psych-testing-ui.js через Node."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TEST = ROOT / "tests" / "js" / "test_psych_testing_ui.mjs"


def test_psych_testing_ui_js():
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
