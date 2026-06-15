"""Authorization policies for role assignment and account management."""

from __future__ import annotations

from fastapi import HTTPException

from app.auth.context import (
    GLOBAL_ADMIN_ROLE_CODES,
    ORG_ADMIN_ROLE_CODES,
    CurrentAccount,
)

PLATFORM_ONLY_ROLE_CODES = GLOBAL_ADMIN_ROLE_CODES | frozenset({"developer"})
ORG_ASSIGNABLE_ROLE_CODES = frozenset({"admin", "hr", "manager", "employee"})


def assert_role_assignment_allowed(ctx: CurrentAccount, role_codes: list[str]) -> None:
    """Org admins cannot assign platform roles; global admin can assign any org role."""
    if ctx.is_global_admin:
        return
    forbidden = set(role_codes) & PLATFORM_ONLY_ROLE_CODES
    if forbidden:
        raise HTTPException(status_code=403, detail="platform_role_assignment_denied")


def assert_account_management_allowed(ctx: CurrentAccount) -> None:
    """Mutating accounts requires global admin or organization admin."""
    if ctx.is_global_admin or ctx.is_org_admin:
        return
    raise HTTPException(status_code=403, detail="org_admin_required")


def filter_roles_for_context(ctx: CurrentAccount, role_codes: list[str]) -> list[str]:
    """Hide platform roles from organization admins in role listings."""
    if ctx.is_global_admin:
        return role_codes
    return [code for code in role_codes if code in ORG_ASSIGNABLE_ROLE_CODES]
