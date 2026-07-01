"""Frontend tests for account create form hardening (Stage 2G)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_TEST = ROOT / "tests" / "js" / "test_account_create_form.mjs"


def test_account_create_form_js():
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


def test_workspace_add_account_modal_has_form_hints():
    workspace = (ROOT / "static/workspace/index.html").read_text(encoding="utf-8")
    assert 'id="accEmployeeHint"' in workspace
    assert 'id="accLoginHint"' in workspace
    assert "account-create-form.js" in workspace
    assert "resetAccAccountModalForm" in workspace
    assert "updateAccAccountFormHints" in workspace
    assert "renderAccAccountRolesCheckboxes" in workspace


def test_account_create_form_module_exports():
    module = (ROOT / "static/shared/account-create-form.js").read_text(encoding="utf-8")
    assert "filterRolesForAccountForm" in module
    assert "validateAccountCreateForm" in module
    assert "suggestLogin" in module
    assert "employeeHasAccount" in module
    assert "Для выбранного сотрудника уже существует учётная запись." in module
