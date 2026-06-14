#!/usr/bin/env python3
"""Create the platform system_admin account from .env (not via onboarding).

Usage (from repo root):
    python scripts/bootstrap_system_admin.py

Requires in .env:
    SYSTEM_ADMIN_LOGIN=...
    SYSTEM_ADMIN_PASSWORD=...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import models  # noqa: F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.migrate import run_migrations  # noqa: E402
from app.seed import seed_roles  # noqa: E402
from app.system_admin import bootstrap_system_admin  # noqa: E402


def main() -> int:
    login = (os.getenv("SYSTEM_ADMIN_LOGIN") or "").strip()
    password = os.getenv("SYSTEM_ADMIN_PASSWORD") or ""
    if not login or not password:
        print("Set SYSTEM_ADMIN_LOGIN and SYSTEM_ADMIN_PASSWORD in .env", file=sys.stderr)
        return 1

    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        seed_roles(db)
        account = bootstrap_system_admin(db, login=login, password=password)
        print(f"system_admin ready: login={account.login!r} account_id={account.id}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
