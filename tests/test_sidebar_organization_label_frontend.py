"""Запуск frontend-тестов sidebar organization label (Stage 2E.1)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TEST = ROOT / "tests" / "js" / "test_sidebar_organization_label.mjs"


def test_sidebar_organization_label_js():
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


def test_sidebar_organization_label_markup_in_source():
    sidebar = (ROOT / "static/shared/sidebar.js").read_text(encoding="utf-8")
    assert "sidebar-organization-full-name" in sidebar
    assert "Код: " in sidebar
    assert "clientFullName" in sidebar
