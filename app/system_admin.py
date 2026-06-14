"""Bootstrap platform system administrator account."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Role
from app.utils import hash_password, new_id32

SYSTEM_ADMIN_ROLE_CODE = "system_admin"


def bootstrap_system_admin(db: Session, login: str, password: str) -> Account:
    """Create or skip platform system_admin (no employee_id, no client_id). Idempotent by login."""
    login = login.strip()
    if not login:
        raise ValueError("SYSTEM_ADMIN_LOGIN is required")
    if not password:
        raise ValueError("SYSTEM_ADMIN_PASSWORD is required")

    existing = db.scalar(select(Account).where(Account.login == login))
    if existing:
        return existing

    role = db.scalar(
        select(Role).where(Role.code == SYSTEM_ADMIN_ROLE_CODE, Role.is_active == True)
    )
    if not role:
        raise RuntimeError(f"role_not_seeded:{SYSTEM_ADMIN_ROLE_CODE}")

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
