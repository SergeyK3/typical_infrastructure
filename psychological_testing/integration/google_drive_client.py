"""Google Drive uploads via service account (shared folder)."""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def _service_account_info() -> dict[str, Any] | None:
    inline = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE", "").strip()
    if inline:
        return json.loads(inline)
    path_raw = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if not path_raw:
        return None
    path = Path(path_raw)
    if not path.is_file():
        raise FileNotFoundError(f"service account JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_drive_service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Google Drive enabled but google-api-python-client / google-auth "
            "are not installed. Add them to requirements.txt."
        ) from exc

    info = _service_account_info()
    if info is None:
        raise RuntimeError(
            "Google Drive enabled: set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON "
            "or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE"
        )
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=[DRIVE_SCOPE]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def root_folder_id() -> str:
    folder_id = os.getenv("PSYCH_TESTING_GDRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        raise RuntimeError(
            "Google Drive enabled: set PSYCH_TESTING_GDRIVE_FOLDER_ID "
            "(folder shared with the service account email)"
        )
    return folder_id


def _find_child_folder(service: Any, parent_id: str, name: str) -> str | None:
    q = (
        f"'{parent_id}' in parents and name = '{name}' "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    resp = (
        service.files()
        .list(q=q, spaces="drive", fields="files(id)", pageSize=1)
        .execute()
    )
    files = resp.get("files") or []
    if files:
        return str(files[0]["id"])
    return None


def _ensure_folder(service: Any, parent_id: str, name: str) -> str:
    existing = _find_child_folder(service, parent_id, name)
    if existing:
        return existing
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(body=meta, fields="id").execute()
    return str(created["id"])


def ensure_path_folder(service: Any, root_id: str, parts: list[str]) -> str:
    """Ensure nested folders under ``root_id``; return leaf folder id."""
    current = root_id
    for part in parts:
        if not part:
            continue
        current = _ensure_folder(service, current, part)
    return current


def upload_bytes(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    parent_folder_id: str,
) -> dict[str, str]:
    """Upload file; returns ``{"file_id", "web_view_link"}``."""
    from googleapiclient.http import MediaIoBaseUpload

    service = _build_drive_service()
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=False)
    body = {"name": filename, "parents": [parent_folder_id]}
    created = (
        service.files()
        .create(body=body, media_body=media, fields="id, webViewLink")
        .execute()
    )
    file_id = str(created["id"])
    link = str(created.get("webViewLink") or web_view_link(file_id))
    _log.info("psych_testing: uploaded to Drive %s (%s)", filename, file_id)
    return {"file_id": file_id, "web_view_link": link}


def download_bytes(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    service = _build_drive_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def web_view_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"
