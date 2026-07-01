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


def test_sidebar_organization_summary_is_compact_only():
    sidebar = (ROOT / "static/shared/sidebar.js").read_text(encoding="utf-8")
    assert "sidebar-organization-name" in sidebar
    assert "clientFullName" in sidebar
    assert "sidebar-organization-full-name" not in sidebar
    assert "sidebar-organization-meta" not in sidebar
    assert "Код: " not in sidebar
    assert "window.ClientDisplay" in sidebar
    assert "global.ClientDisplay" not in sidebar


def test_workspace_loads_sidebar_with_cache_bust():
    workspace = (ROOT / "static/workspace/index.html").read_text(encoding="utf-8")
    assert "client-display.js" in workspace
    assert 'sidebar.js?v=platform-sidebar-20260705' in workspace
    idx_client_display = workspace.index("client-display.js")
    idx_sidebar = workspace.index("sidebar.js")
    assert idx_client_display < idx_sidebar, "ClientDisplay must load before sidebar.js"
