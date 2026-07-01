"""Platform sidebar unification (PROJ-ACCESS-ADMIN Stage 1)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PLATFORM_PAGES = [
    "static/clients/index.html",
    "static/users/index.html",
    "static/org-admins/index.html",
    "static/wizard/index.html",
    "static/global/index.html",
    "static/global/template-org.html",
    "static/global/positions.html",
    "static/global/kpi.html",
    "static/global/skills.html",
    "static/regulations/index.html",
]

SIDEBAR_SCRIPTS = (
    "sidebar-registry.js",
    "auth-context.js",
    "sidebar.js",
    "platform-sidebar-init.js",
)


def test_platform_sidebar_renderer_exported():
    sidebar_js = (ROOT / "static/shared/sidebar.js").read_text(encoding="utf-8")
    assert "renderPlatformSidebar" in sidebar_js
    assert "function renderPlatformSidebar" in sidebar_js


def test_platform_pages_use_shared_sidebar():
    registry = (ROOT / "static/shared/sidebar-registry.js").read_text(encoding="utf-8")
    assert "Админы организаций" in registry
    assert "platform.orgAdmins" in registry

    for rel in PLATFORM_PAGES:
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert 'id="platformSidebar"' in html, rel
        assert "__platformSidebarOptions" in html, rel
        for script in SIDEBAR_SCRIPTS:
            assert script in html, f"{rel} missing {script}"
        assert '<a href="/clients" class="sidebar-item">' not in html, rel
        assert '<div class="sidebar-top">' not in html, rel


def test_workspace_sidebar_unchanged():
    workspace = (ROOT / "static/workspace/index.html").read_text(encoding="utf-8")
    assert 'id="workspaceSidebar"' in workspace
    assert "renderWorkspaceSidebar" in workspace or "SidebarRenderer" in workspace
    assert 'id="platformSidebar"' not in workspace
