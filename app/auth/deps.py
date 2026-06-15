"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount, AccountMisconfiguredError, build_current_account
from app.db import get_db
from app.models import Account


def _account_from_session(request: Request, db: Session) -> Account | None:
    account_id = request.session.get("account_id")
    if not account_id:
        return None
    account = db.get(Account, account_id)
    if not account or account.status != "active":
        return None
    return account


def get_optional_account(
    request: Request,
    db: Session = Depends(get_db),
) -> CurrentAccount | None:
    account = _account_from_session(request, db)
    if not account:
        return None
    try:
        return build_current_account(db, account)
    except AccountMisconfiguredError:
        raise HTTPException(status_code=403, detail="account_misconfigured")


def get_current_account(
    ctx: CurrentAccount | None = Depends(get_optional_account),
) -> CurrentAccount:
    if ctx is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    return ctx


def require_global_admin(
    ctx: CurrentAccount = Depends(get_current_account),
) -> CurrentAccount:
    if not ctx.is_global_admin:
        raise HTTPException(status_code=403, detail="global_admin_required")
    return ctx


def require_system_admin(
    ctx: CurrentAccount = Depends(get_current_account),
) -> CurrentAccount:
    """Alias for global (platform) admin access."""
    return require_global_admin(ctx)


def require_org_admin(
    ctx: CurrentAccount = Depends(get_current_account),
) -> CurrentAccount:
    if not (ctx.is_global_admin or ctx.is_org_admin):
        raise HTTPException(status_code=403, detail="org_admin_required")
    return ctx


def require_client_access(
    client_id: str,
    ctx: CurrentAccount = Depends(get_current_account),
) -> CurrentAccount:
    if not ctx.can_access_client(client_id):
        raise HTTPException(status_code=403, detail="client_access_denied")
    return ctx
