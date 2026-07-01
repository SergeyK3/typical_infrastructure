"""Platform sidebar unification (PROJ-ACCESS-ADMIN Stage 1–2C)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER_HELPER = ROOT / "tests/helpers/render_platform_sidebar.mjs"

PLATFORM_PAGES = [
    "static/clients/index.html",
    "static/users/index.html",
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

SIDEBAR_CACHE_BUST = "platform-sidebar-20260703"
PLATFORM_PAGE_GUARD = "platform-page-guard.js"
USERS_NAV_PATTERN = re.compile(
    r'<a\b(?=[^>]*\bdata-nav-id="platform\.users")(?=[^>]*\bhref="/users")[^>]*>(.*?)</a>',
    re.DOTALL,
)


def render_platform_sidebar_html(*, current_path: str = "/users", is_global_admin: bool = True) -> str:
    cmd = ["node", str(RENDER_HELPER), "--path", current_path]
    if not is_global_admin:
        cmd.append("--no-global-admin")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    return result.stdout


def users_nav_match(html: str) -> re.Match[str] | None:
    return USERS_NAV_PATTERN.search(html)


def test_platform_sidebar_renderer_exported():
    sidebar_js = (ROOT / "static/shared/sidebar.js").read_text(encoding="utf-8")
    assert "renderPlatformSidebar" in sidebar_js
    assert "function renderPlatformSidebar" in sidebar_js


def test_platform_sidebar_registry_has_single_accounts_nav_item():
    registry = (ROOT / "static/shared/sidebar-registry.js").read_text(encoding="utf-8")
    assert "platform.orgAdmins" not in registry
    assert "Админы организаций" not in registry
    assert "Учётные записи" in registry
    assert "platform.users" in registry
    assert "isActive" in registry
    assert "Пользователи" not in registry
    assert "/org-admins" in registry  # compatibility redirect documented in registry comment


def test_platform_pages_use_shared_sidebar():
    test_platform_sidebar_registry_has_single_accounts_nav_item()

    for rel in PLATFORM_PAGES:
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert 'id="platformSidebar"' in html, rel
        assert "__platformSidebarOptions" in html, rel
        for script in SIDEBAR_SCRIPTS:
            assert script in html, f"{rel} missing {script}"
        assert SIDEBAR_CACHE_BUST in html, f"{rel} missing sidebar cache bust {SIDEBAR_CACHE_BUST}"
        assert '<a href="/clients" class="sidebar-item">' not in html, rel
        assert '<div class="sidebar-top">' not in html, rel

    users_html = (ROOT / "static/users/index.html").read_text(encoding="utf-8")
    assert 'data-platform-page="users"' in users_html
    assert PLATFORM_PAGE_GUARD in users_html


def users_nav_label() -> str:
    registry = (ROOT / "static/shared/sidebar-registry.js").read_text(encoding="utf-8")
    match = re.search(r"id: 'platform\.users'[^}]*label: '([^']+)'", registry, re.DOTALL)
    assert match is not None, registry
    return match.group(1)


def test_rendered_platform_sidebar_shows_users_link_for_global_admin():
    html = render_platform_sidebar_html(current_path="/users", is_global_admin=True)
    match = users_nav_match(html)
    assert match is not None, html
    assert match.group(1) == users_nav_label()
    assert 'class="' in match.group(0) and "active" in match.group(0)
    assert "Пользователи" not in html


def test_rendered_platform_sidebar_hides_org_admins_nav_item():
    html = render_platform_sidebar_html(current_path="/users", is_global_admin=True)
    assert "Админы организаций" not in html
    assert "platform.orgAdmins" not in html
    assert users_nav_match(html) is not None


def test_rendered_platform_sidebar_users_active_for_preset_pathname():
    html = render_platform_sidebar_html(current_path="/users", is_global_admin=True)
    match = users_nav_match(html)
    assert match is not None, html
    assert "active" in match.group(0)


def test_rendered_platform_sidebar_hides_global_items_without_auth():
    """Registry contains the item, but renderer must hide it without Global Admin context."""
    registry = (ROOT / "static/shared/sidebar-registry.js").read_text(encoding="utf-8")
    assert "platform.users" in registry

    html = render_platform_sidebar_html(current_path="/users", is_global_admin=False)
    assert users_nav_match(html) is None, html
    assert "Учётные записи" not in html
    assert "Пользователи" not in html


def test_platform_sidebar_init_uses_auth_helpers():
    init_js = (ROOT / "static/shared/platform-sidebar-init.js").read_text(encoding="utf-8")
    assert "AuthContext.isGlobalAdmin" in init_js
    assert "AuthContext.load().finally(boot)" in init_js or "AuthContext.load().finally(boot);" in init_js


def test_org_admins_route_redirects_to_users_preset(client):
    page = client.get("/org-admins", follow_redirects=False)
    assert page.status_code == 302
    assert page.headers["location"] == "/users?preset=org-admins"
    assert "<h1>Админы организаций</h1>" not in page.text


def test_org_admins_trailing_slash_redirects_to_users_preset(client):
    page = client.get("/org-admins/", follow_redirects=False)
    assert page.status_code == 302
    assert page.headers["location"] == "/users?preset=org-admins"


def test_org_admins_route_preserves_client_id_on_redirect(client):
    client_id = "00000000-0000-4000-8000-000000000001"
    page = client.get(f"/org-admins?client_id={client_id}", follow_redirects=False)
    assert page.status_code == 302
    assert page.headers["location"] == f"/users?client_id={client_id}&preset=org-admins"


def test_org_admins_redirect_strips_internal_role_code(client):
    page = client.get("/org-admins?role_code=admin&preset=org-admins", follow_redirects=False)
    assert page.status_code == 302
    assert "role_code=" not in page.headers["location"]
    assert page.headers["location"] == "/users?preset=org-admins"


def test_users_pages_keep_accounts_title(client):
    for path in ("/users", "/users?preset=org-admins"):
        page = client.get(path, follow_redirects=False)
        assert page.status_code == 200, path
        assert "Учётные записи" in page.text, path
        assert "<h1>Админы организаций</h1>" not in page.text, path


def test_org_admins_follow_redirect_lands_on_users_preset(client):
    page = client.get("/org-admins", follow_redirects=True)
    assert page.status_code == 200
    assert page.url.path == "/users"
    assert "preset=org-admins" in str(page.url)
    assert "Учётные записи" in page.text
    assert "<h1>Админы организаций</h1>" not in page.text


def test_workspace_html_has_route_guard():
    workspace = (ROOT / "static/workspace/index.html").read_text(encoding="utf-8")
    assert 'id="workspaceSidebar"' in workspace
    assert "renderWorkspaceSidebar" in workspace or "SidebarRenderer" in workspace
    assert 'id="platformSidebar"' not in workspace
    assert "workspace-route-guard.js" in workspace
    assert "isPlatformNavLink" in workspace
    assert "platform-sidebar-20260703" in workspace
