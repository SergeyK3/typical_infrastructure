# route: /api/auth | file: app/routers/auth.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import AccountMisconfiguredError, build_current_account, login_redirect_url
from app.auth.deps import get_current_account, get_optional_account
from app.auth.context import CurrentAccount
from app.db import get_db
from app.models import Account
from app.utils import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    account_id: str
    login: str
    roles: list[str]
    client_id: str | None
    is_system: bool
    is_global_admin: bool
    is_org_admin: bool
    allowed_clients: list[str]
    redirect_url: str


class MeOut(BaseModel):
    account_id: str
    login: str
    roles: list[str]
    client_id: str | None
    is_system: bool
    is_global_admin: bool
    is_org_admin: bool
    allowed_clients: list[str]


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    account = db.scalar(select(Account).where(Account.login == payload.login))
    if not account or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if account.status != "active":
        raise HTTPException(status_code=403, detail="account_inactive")

    request.session["account_id"] = account.id
    try:
        ctx = build_current_account(db, account)
    except AccountMisconfiguredError:
        request.session.clear()
        raise HTTPException(status_code=403, detail="account_misconfigured")
    data = ctx.to_me_dict()
    return LoginOut(**data, redirect_url=login_redirect_url(ctx))


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
def me(ctx: CurrentAccount = Depends(get_current_account)) -> MeOut:
    return MeOut(**ctx.to_me_dict())
