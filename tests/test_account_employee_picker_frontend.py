"""Frontend tests for account employee picker (Stage 2F)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TEST = ROOT / "tests" / "js" / "test_account_employee_picker.mjs"


def test_account_employee_picker_js():
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


def test_workspace_add_account_modal_has_picker_filters():
    workspace = (ROOT / "static/workspace/index.html").read_text(encoding="utf-8")
    assert 'id="accPickNameSearch"' in workspace
    assert 'id="accPickLogGroup"' in workspace
    assert 'id="accPickOrgUnit"' in workspace
    assert 'id="accPickPosition"' in workspace
    assert "account-employee-picker.js" in workspace
    assert "renderAccAccountEmployeePicker" in workspace
    idx_picker = workspace.index("account-employee-picker.js")
    idx_inline = workspace.index("<script>\n    const API = '/api';")
    assert idx_picker < idx_inline, "AccountEmployeePicker must load before inline workspace script"


def test_account_picker_module_exports_resolve_picker():
    module = (ROOT / "static/shared/account-employee-picker.js").read_text(encoding="utf-8")
    assert "resolvePicker" in module
    assert "matchesNameQuery" in module
    assert "Сотрудники не найдены" in module
    assert "PsychTestingUi is required" in module
