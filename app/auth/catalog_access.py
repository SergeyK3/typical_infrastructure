"""Access checks for catalog-copy operations."""

from __future__ import annotations

from fastapi import HTTPException

from app.auth.context import CurrentAccount

GLOBAL_ONLY_COPY_MODES = frozenset({"global_to_global", "local_to_global"})


def assert_catalog_copy_allowed(ctx: CurrentAccount, mode: str, client_id: str | None = None) -> None:
    normalized = mode.strip()
    if normalized in GLOBAL_ONLY_COPY_MODES:
        if not ctx.is_global_admin:
            raise HTTPException(status_code=403, detail="global_admin_required")
        return
    if normalized == "global_to_local":
        if not client_id:
            raise HTTPException(status_code=422, detail="client_id_required")
        if not ctx.can_access_client(client_id):
            raise HTTPException(status_code=403, detail="client_access_denied")
        return
    raise HTTPException(status_code=422, detail="invalid_copy_mode")
