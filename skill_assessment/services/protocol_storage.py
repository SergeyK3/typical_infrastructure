# route: (storage) | file: skill_assessment/services/protocol_storage.py
"""Filesystem-backed immutable artifact storage for protocol archives."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str
    path: Path


def protocol_storage_base_dir() -> Path:
    raw = (
        os.getenv("SKILL_ASSESSMENT_DATA_DIR")
        or os.getenv("DATA_DIR")
        or os.getenv("APP_DATA_DIR")
        or "data"
    )
    return Path(raw).expanduser().resolve()


def normalize_storage_key(storage_key: str) -> str:
    key = str(storage_key or "").strip().replace("\\", "/")
    if not key:
        raise ValueError("storage_key_required")
    pp = PurePosixPath(key)
    if pp.is_absolute() or ".." in pp.parts:
        raise ValueError("storage_key_must_be_relative")
    return pp.as_posix()


def artifact_path(storage_key: str) -> Path:
    key = normalize_storage_key(storage_key)
    base = protocol_storage_base_dir()
    path = (base / key).resolve()
    if base != path and base not in path.parents:
        raise ValueError("storage_key_escapes_data_dir")
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put_immutable_artifact(storage_key: str, data: bytes, *, mime_type: str) -> StoredArtifact:
    key = normalize_storage_key(storage_key)
    payload = bytes(data)
    digest = sha256_bytes(payload)
    path = artifact_path(key)
    if path.exists():
        existing = path.read_bytes()
        existing_digest = sha256_bytes(existing)
        if existing_digest != digest:
            raise FileExistsError(f"immutable_artifact_exists_with_different_checksum:{key}")
        return StoredArtifact(
            storage_key=key,
            sha256=existing_digest,
            size_bytes=len(existing),
            mime_type=mime_type,
            path=path,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)
    return StoredArtifact(
        storage_key=key,
        sha256=digest,
        size_bytes=len(payload),
        mime_type=mime_type,
        path=path,
    )


def read_artifact(storage_key: str) -> bytes:
    return artifact_path(storage_key).read_bytes()


def artifact_metadata(storage_key: str, *, mime_type: str) -> StoredArtifact:
    key = normalize_storage_key(storage_key)
    path = artifact_path(key)
    payload = path.read_bytes()
    return StoredArtifact(
        storage_key=key,
        sha256=sha256_bytes(payload),
        size_bytes=len(payload),
        mime_type=mime_type,
        path=path,
    )
