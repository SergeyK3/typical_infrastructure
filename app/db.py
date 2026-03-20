r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\db.py"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.settings import settings


def _sqlite_url(path: str) -> str:
    return f"sqlite:///{path}"


if settings.sqlite_path == ":memory:":
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        _sqlite_url(settings.sqlite_path),
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
