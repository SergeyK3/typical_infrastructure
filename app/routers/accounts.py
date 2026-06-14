# route: /api/accounts | file: app/routers/accounts.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount
from app.auth.deps import get_current_account, require_system_admin
from app.auth.tenant import assert_client_access, load_account_for_ctx, require_client_query_access
from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import Account, AccountRole, Client, Employee, OrgUnit, Position, Role
from app.schemas import (
    AccountBulkCreateRequest,
    AccountBulkCreateResult,
    AccountCreate,
    AccountListItem,
    AccountOut,
    AccountPatch,
    AccountWithRolesOut,
    ListEnvelope,
)
from app.utils import generate_temp_password, hash_password, new_id32

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _assert_employee(db: Session, employee_id: str, client_id: str | None = None) -> Employee:
    emp = db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=400, detail="employee_not_found")
    if client_id and emp.client_id != client_id:
        raise HTTPException(status_code=400, detail="employee_not_in_client")
    return emp


def _assert_login_unique(db: Session, login: str, exclude_account_id: str | None = None) -> None:
    q = select(Account).where(Account.login == login)
    if exclude_account_id:
        q = q.where(Account.id != exclude_account_id)
    existing = db.scalar(q)
    if existing:
        raise HTTPException(status_code=409, detail="login_already_exists")


def _assert_role_codes(db: Session, role_codes: list[str]) -> None:
    if not role_codes:
        return
    found = set(db.scalars(select(Role.code).where(Role.code.in_(role_codes), Role.is_active == True)).all())
    missing = set(role_codes) - found
    if missing:
        raise HTTPException(status_code=400, detail=f"invalid_role_codes:{','.join(sorted(missing))}")


def _get_role_codes_for_account(db: Session, account_id: str) -> list[str]:
    rows = (
        db.execute(
            select(Role.code)
            .join(AccountRole, AccountRole.role_id == Role.id)
            .where(AccountRole.account_id == account_id)
            .order_by(Role.code)
        )
    ).scalars().all()
    return list(rows)


def _assign_roles(db: Session, account_id: str, role_codes: list[str]) -> None:
    existing = db.scalars(select(AccountRole).where(AccountRole.account_id == account_id)).all()
    role_by_ar = {ar.role_id: db.get(Role, ar.role_id) for ar in existing}
    existing_codes = {r.code for r in role_by_ar.values() if r}
    to_add = set(role_codes) - existing_codes
    to_remove = [ar for ar in existing if role_by_ar.get(ar.role_id) and role_by_ar[ar.role_id].code not in role_codes]
    roles_by_code = {r.code: r for r in db.scalars(select(Role).where(Role.code.in_(role_codes), Role.is_active == True)).all()}
    for ar in to_remove:
        db.delete(ar)
    for code in to_add:
        role = roles_by_code.get(code)
        if role:
            db.add(AccountRole(id=new_id32(), account_id=account_id, role_id=role.id))
    db.flush()


@router.get("", response_model=ListEnvelope[AccountListItem])
def list_accounts(
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_client_query_access),
    client_id: str = Query(...),
    org_unit_id: str | None = Query(None),
    position_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[AccountListItem]:
    q = select(Account).join(Employee, Account.employee_id == Employee.id).where(Employee.client_id == client_id)
    if org_unit_id:
        q = q.where(Employee.org_unit_id == org_unit_id)
    if position_id:
        q = q.where(Employee.position_id == position_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Account.created_at.desc()).limit(limit).offset(offset)).all()
    items = [
        AccountListItem(
            id=r.id,
            employee_id=r.employee_id,
            login=r.login,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return ListEnvelope[AccountListItem](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_accounts_excel(
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_client_query_access),
    client_id: str = Query(...),
    org_unit_id: str | None = Query(None),
    position_id: str | None = Query(None),
) -> Response:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    q = select(Account).join(Employee, Account.employee_id == Employee.id).where(Employee.client_id == client_id)
    if org_unit_id:
        q = q.where(Employee.org_unit_id == org_unit_id)
    if position_id:
        q = q.where(Employee.position_id == position_id)
    rows = db.scalars(q.order_by(Account.created_at.desc()).limit(5000)).all()
    headers = [
        "last_name",
        "first_name",
        "middle_name",
        "email",
        "phone",
        "telegram_id",
        "org_unit_code",
        "position_code",
        "login",
        "status",
        "role_codes",
        "employee_id",
        "account_id",
        "created_at",
        "updated_at",
    ]
    data = []
    for r in rows:
        emp = db.get(Employee, r.employee_id)
        ou = db.get(OrgUnit, emp.org_unit_id) if emp and emp.org_unit_id else None
        pos = db.get(Position, emp.position_id) if emp and emp.position_id else None
        data.append(
            [
                emp.last_name if emp else None,
                emp.first_name if emp else None,
                emp.middle_name if emp else None,
                emp.email if emp else None,
                emp.phone if emp else None,
                emp.telegram_id if emp else None,
                ou.code if ou else None,
                pos.code if pos else None,
                r.login,
                r.status,
                ",".join(_get_role_codes_for_account(db, r.id)),
                r.employee_id,
                r.id,
                r.created_at,
                r.updated_at,
            ]
        )
    return xlsx_file_response(
        download_name=f"accounts_{client_id}.xlsx",
        sheet_title="accounts",
        headers=headers,
        rows=data,
    )


@router.get("/{account_id}", response_model=AccountWithRolesOut)
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> AccountWithRolesOut:
    obj = load_account_for_ctx(db, account_id, ctx)
    role_codes = _get_role_codes_for_account(db, account_id)
    return AccountWithRolesOut(
        **AccountOut.model_validate(obj).model_dump(),
        role_codes=role_codes,
    )


class EncodePasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class EncodePasswordOut(BaseModel):
    password_hash: str


@router.post("/encode-password", response_model=EncodePasswordOut)
def encode_password(
    payload: EncodePasswordIn,
    _ctx: CurrentAccount = Depends(require_system_admin),
) -> EncodePasswordOut:
    """Encode plain password (system_admin only; prefer POST /accounts with password field)."""
    return EncodePasswordOut(password_hash=hash_password(payload.password))


@router.post("", response_model=AccountWithRolesOut)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> AccountWithRolesOut:
    emp = _assert_employee(db, payload.employee_id)
    assert_client_access(ctx, emp.client_id)
    _assert_login_unique(db, payload.login)
    _assert_role_codes(db, payload.role_codes)
    obj = Account(
        id=payload.id or new_id32(),
        employee_id=payload.employee_id,
        login=payload.login,
        password_hash=hash_password(payload.password),
        status=payload.status,
    )
    db.add(obj)
    db.flush()
    _assign_roles(db, obj.id, payload.role_codes)
    db.commit()
    db.refresh(obj)
    role_codes = _get_role_codes_for_account(db, obj.id)
    return AccountWithRolesOut(
        **AccountOut.model_validate(obj).model_dump(),
        role_codes=role_codes,
    )


@router.patch("/{account_id}", response_model=AccountWithRolesOut)
def patch_account(
    account_id: str,
    payload: AccountPatch,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> AccountWithRolesOut:
    obj = load_account_for_ctx(db, account_id, ctx)
    data = payload.model_dump(exclude_unset=True)
    role_codes = data.pop("role_codes", None)
    password = data.pop("password", None)
    if "login" in data:
        _assert_login_unique(db, data["login"], exclude_account_id=account_id)
    if role_codes is not None:
        _assert_role_codes(db, role_codes)
    if password is not None:
        obj.password_hash = hash_password(password)
    for k, v in data.items():
        setattr(obj, k, v)
    if role_codes is not None:
        _assign_roles(db, account_id, role_codes)
    db.commit()
    db.refresh(obj)
    codes = _get_role_codes_for_account(db, account_id)
    return AccountWithRolesOut(
        **AccountOut.model_validate(obj).model_dump(),
        role_codes=codes,
    )


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> Response:
    obj = load_account_for_ctx(db, account_id, ctx)
    for ar in db.scalars(select(AccountRole).where(AccountRole.account_id == account_id)).all():
        db.delete(ar)
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.post("/{account_id}/reset-password", response_model=AccountOut)
def reset_password(
    account_id: str,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> AccountOut:
    obj = load_account_for_ctx(db, account_id, ctx)
    new_password = generate_temp_password()
    obj.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(obj)
    return AccountOut.model_validate(obj)


@router.post("/bulk", response_model=AccountBulkCreateResult)
def bulk_create_accounts(
    payload: AccountBulkCreateRequest,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
) -> AccountBulkCreateResult:
    created: list[AccountOut] = []
    errors: list[dict] = []
    for i, it in enumerate(payload.items):
        try:
            emp = _assert_employee(db, it.employee_id)
            assert_client_access(ctx, emp.client_id)
            _assert_login_unique(db, it.login)
            _assert_role_codes(db, it.role_codes)
            existing = db.scalar(select(Account).where(Account.employee_id == it.employee_id))
            if existing:
                errors.append({"index": i, "employee_id": it.employee_id, "detail": "employee_already_has_account"})
                continue
            obj = Account(
                id=new_id32(),
                employee_id=it.employee_id,
                login=it.login,
                password_hash=hash_password(it.password),
                status=it.status,
            )
            db.add(obj)
            db.flush()
            _assign_roles(db, obj.id, it.role_codes)
            created.append(AccountOut.model_validate(obj))
        except HTTPException as e:
            errors.append({"index": i, "employee_id": it.employee_id, "detail": e.detail})
    db.commit()
    return AccountBulkCreateResult(created=created, errors=errors)
