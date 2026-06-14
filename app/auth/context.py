"""Resolve authenticated account context (roles, tenant scope)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Client, Employee, Role

SYSTEM_ROLE_CODES = frozenset({"system_admin", "developer"})
CLIENT_ADMIN_ROLE_CODES = frozenset({"admin"})


class AccountMisconfiguredError(Exception):
    """Account has no employee_id and no platform system role."""


@dataclass(frozen=True)
class CurrentAccount:
    account_id: str
    login: str
    roles: list[str]
    client_id: str | None
    is_system: bool
    allowed_clients: list[str]

    def can_access_client(self, client_id: str) -> bool:
        if self.is_system:
            return True
        return client_id in self.allowed_clients

    def to_me_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "login": self.login,
            "roles": self.roles,
            "client_id": self.client_id,
            "is_system": self.is_system,
            "allowed_clients": self.allowed_clients,
        }


def _role_codes_for_account(db: Session, account_id: str) -> list[str]:
    rows = db.execute(
        select(Role.code)
        .join(AccountRole, AccountRole.role_id == Role.id)
        .where(AccountRole.account_id == account_id, Role.is_active == True)
        .order_by(Role.code)
    ).scalars().all()
    return list(rows)


def _all_client_ids(db: Session) -> list[str]:
    return list(db.scalars(select(Client.id).order_by(Client.created_at.desc())).all())


def build_current_account(db: Session, account: Account) -> CurrentAccount:
    roles = _role_codes_for_account(db, account.id)
    is_system = bool(set(roles) & SYSTEM_ROLE_CODES)

    if is_system:
        return CurrentAccount(
            account_id=account.id,
            login=account.login,
            roles=roles,
            client_id=None,
            is_system=True,
            allowed_clients=_all_client_ids(db),
        )

    if account.employee_id is None:
        raise AccountMisconfiguredError("account_missing_employee")

    emp = db.get(Employee, account.employee_id)
    if not emp:
        return CurrentAccount(
            account_id=account.id,
            login=account.login,
            roles=roles,
            client_id=None,
            is_system=False,
            allowed_clients=[],
        )

    return CurrentAccount(
        account_id=account.id,
        login=account.login,
        roles=roles,
        client_id=emp.client_id,
        is_system=False,
        allowed_clients=[emp.client_id],
    )


def login_redirect_url(ctx: CurrentAccount) -> str:
    if ctx.is_system:
        return "/clients"
    if ctx.client_id:
        return f"/client/{ctx.client_id}"
    return "/login"
