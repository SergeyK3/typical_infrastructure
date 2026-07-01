"""Bootstrap platform system administrator account."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Role
from app.utils import hash_password, new_id32, verify_password

SYSTEM_ADMIN_ROLE_CODE = "system_admin"
PLATFORM_ROLE_CODES = frozenset({"system_admin", "developer"})
# Local dev convention — distinct from org admin logins like admin_mmc
DEV_SYSTEM_ADMIN_LOGIN = "gladmin"


def _role_codes_for_account(db: Session, account_id: str) -> list[str]:
    return list(
        db.execute(
            select(Role.code)
            .join(AccountRole, AccountRole.role_id == Role.id)
            .where(AccountRole.account_id == account_id, Role.is_active == True)
        )
        .scalars()
        .all()
    )


def _ensure_system_admin_role(db: Session, account: Account, role: Role) -> bool:
    changed = False
    if SYSTEM_ADMIN_ROLE_CODE not in _role_codes_for_account(db, account.id):
        db.add(AccountRole(id=new_id32(), account_id=account.id, role_id=role.id))
        changed = True

    if account.employee_id is None:
        rows = db.execute(
            select(AccountRole, Role)
            .join(Role, AccountRole.role_id == Role.id)
            .where(AccountRole.account_id == account.id)
        ).all()
        for account_role, assigned in rows:
            if assigned.code not in PLATFORM_ROLE_CODES:
                db.delete(account_role)
                changed = True
    return changed


def bootstrap_system_admin(
    db: Session,
    login: str,
    password: str,
    *,
    sync_existing: bool = False,
) -> Account:
    """Create or (optionally) reconcile platform system_admin by login."""
    login = login.strip()
    if not login:
        raise ValueError("SYSTEM_ADMIN_LOGIN is required")
    if not password:
        raise ValueError("SYSTEM_ADMIN_PASSWORD is required")

    role = db.scalar(
        select(Role).where(Role.code == SYSTEM_ADMIN_ROLE_CODE, Role.is_active == True)
    )
    if not role:
        raise RuntimeError(f"role_not_seeded:{SYSTEM_ADMIN_ROLE_CODE}")

    existing = db.scalar(select(Account).where(Account.login == login))
    if existing:
        if not sync_existing:
            return existing

        changed = False
        if existing.employee_id is not None:
            existing.employee_id = None
            changed = True
        if existing.status != "active":
            existing.status = "active"
            changed = True
        if not verify_password(password, existing.password_hash):
            existing.password_hash = hash_password(password)
            changed = True
        if _ensure_system_admin_role(db, existing, role):
            changed = True
        if changed:
            db.commit()
            db.refresh(existing)
        return existing

    account = Account(
        id=new_id32(),
        employee_id=None,
        login=login,
        password_hash=hash_password(password),
        status="active",
    )
    db.add(account)
    db.flush()
    db.add(AccountRole(id=new_id32(), account_id=account.id, role_id=role.id))
    db.commit()
    db.refresh(account)
    return account


def bootstrap_system_admin_if_configured(db: Session) -> Account | None:
    """Apply SYSTEM_ADMIN_* from settings when login and password are configured."""
    from app.settings import settings

    login = (settings.system_admin_login or "").strip()
    password = settings.system_admin_password or ""
    if not login or not password:
        return None
    return bootstrap_system_admin(
        db,
        login=login,
        password=password,
        sync_existing=settings.system_admin_sync,
    )
