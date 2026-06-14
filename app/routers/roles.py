# route: /api/roles | file: app/routers/roles.py
r"""Roles API — list active roles."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount
from app.auth.deps import get_current_account
from app.db import get_db
from app.models import Role
from app.schemas import RoleOut

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(get_current_account),
) -> list[RoleOut]:
    rows = db.scalars(select(Role).where(Role.is_active == True).order_by(Role.code)).all()
    return [RoleOut.model_validate(r) for r in rows]
