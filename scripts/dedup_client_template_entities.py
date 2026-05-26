"""
Удалить дубликаты сущностей клиента, появившиеся при повторном применении шаблона.

  python scripts/dedup_client_template_entities.py [--all] [--dry-run] [client_id]

Без аргументов — справка. client_id — UUID или код клиента из GET /api/clients.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from app.client_template_dedup import dedup_all_clients, dedup_client_template_entities
from app.db import SessionLocal
from app.models import Client


def _resolve_client(db, ref: str) -> Client | None:
    ref = ref.strip()
    client = db.get(Client, ref)
    if client:
        return client
    return db.scalar(select(Client).where(Client.code == ref))


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    all_clients = "--all" in args
    refs = [a for a in args if not a.startswith("--")]

    if not all_clients and not refs:
        print(__doc__.strip())
        sys.exit(1)

    db = SessionLocal()
    try:
        if all_clients:
            stats = dedup_all_clients(db, dry_run=dry_run)
            if not dry_run:
                db.commit()
            for code, item in stats.items():
                print(f"{code}: {item}")
            return

        for ref in refs:
            client = _resolve_client(db, ref)
            if not client:
                print(f"Клиент не найден: {ref}")
                sys.exit(1)
            stats = dedup_client_template_entities(db, client.id, dry_run=dry_run)
            if not dry_run:
                db.commit()
            print(f"{client.code} ({client.id}): {stats.as_dict()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
