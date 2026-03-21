"""
Скопировать глобальные регламенты в справочник клиента по тем же правилам, что и «Развернуть типовую оргструктуру».

  python scripts/sync_client_regulations_from_global.py <client_id>

client_id — UUID из URL /client/… или ответа API GET /api/clients.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.client_catalog_sync import sync_global_regulations_to_client
from app.db import SessionLocal


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)
    cid = sys.argv[1].strip()
    db = SessionLocal()
    try:
        n = sync_global_regulations_to_client(db, cid)
        db.commit()
        print(f"Добавлено клиентских регламентов: {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
